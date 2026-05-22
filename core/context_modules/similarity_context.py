from .base import *
from .settings_context import load_settings
from .image_context import iter_image_files, resolve_under_root
from .root_workspace import root_database_path
from core.domain.root_context import RootContext
from core.storage.duplicates_repository import DuplicateResultRepository
from core.storage.hash_db_repository import HashDbRepository
from MediaArchiveOrganizer.core.duplicate_detector import compute_phash, phash_distance

FULL_ROOT_SUPPLEMENTAL_SCAN_LIMIT = 1000


def _resolve_similarity_query_path(active_root: Path, candidate: str) -> tuple[Path, str]:
    raw_candidate = str(candidate or "").strip().strip('"')
    if not raw_candidate:
        raise HTTPException(status_code=400, detail="Image path is required")

    candidate_path = Path(raw_candidate).expanduser()
    if candidate_path.is_absolute():
        query_path = candidate_path.resolve()
        try:
            relative_path = query_path.relative_to(active_root).as_posix()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Path escapes configured root") from exc
        return query_path, relative_path

    query_path = resolve_under_root(active_root, raw_candidate)
    try:
        relative_path = query_path.relative_to(active_root).as_posix()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Path escapes configured root") from exc
    if not query_path.exists() and Path(raw_candidate).name == raw_candidate:
        matches: list[Path] = []
        for matched_path in active_root.rglob(raw_candidate):
            if matched_path.is_file():
                matches.append(matched_path.resolve())
                if len(matches) > 1:
                    break
        if len(matches) == 1:
            matched_path = matches[0]
            return matched_path, matched_path.relative_to(active_root).as_posix()
        if len(matches) > 1:
            raise HTTPException(
                status_code=400,
                detail=f"Multiple images matched filename. Use a relative path: {raw_candidate}",
            )
    return query_path, relative_path


def _iter_query_directory_images(query_path: Path) -> Iterable[Path]:
    if not query_path.parent.exists():
        return []
    return (
        path
        for path in query_path.parent.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def _collect_similarity_candidates(
    active_root: Path,
    query_path: Path,
    hash_db: dict[str, dict[str, list[str]]],
) -> dict[str, list[Path]]:
    candidates: dict[str, list[Path]] = {}
    seen_paths: set[Path] = set()

    def add_candidate(path: Path, hash_value: str | None = None) -> None:
        candidate_path = path.expanduser().resolve()
        if candidate_path == query_path or candidate_path in seen_paths:
            return
        if not candidate_path.exists() or not candidate_path.is_file():
            return
        try:
            candidate_path.relative_to(active_root)
        except ValueError:
            return

        candidate_hash = hash_value or compute_phash(str(candidate_path))
        if not candidate_hash:
            return
        seen_paths.add(candidate_path)
        candidates.setdefault(candidate_hash, []).append(candidate_path)

    for hash_value, paths in hash_db.get("phash", {}).items():
        for path in paths:
            add_candidate(Path(path), str(hash_value))

    for path in _iter_query_directory_images(query_path):
        add_candidate(path)

    root_file_count = 0
    root_files: list[Path] = []
    for path in iter_image_files(active_root):
        root_file_count += 1
        if root_file_count > FULL_ROOT_SUPPLEMENTAL_SCAN_LIMIT:
            break
        root_files.append(path)
    if root_file_count <= FULL_ROOT_SUPPLEMENTAL_SCAN_LIMIT:
        for path in root_files:
            add_candidate(path)

    return candidates


def _collect_duplicate_group_matches(active_root: Path, query_relative_path: str) -> dict[str, dict[str, Any]]:
    payload = DuplicateResultRepository(
        RootContext.from_root(active_root, ROOT_DATA_DIR, ensure=True).database_path
    ).load_result()
    if payload is None:
        return {}

    destination_root = str(payload.get("destination_root", "")).strip()
    if not destination_root or Path(destination_root).expanduser().resolve() != active_root:
        return {}

    matches: dict[str, dict[str, Any]] = {}
    for group in payload.get("groups", []):
        if not isinstance(group, dict):
            continue
        items = group.get("items", [])
        if not isinstance(items, list):
            continue
        group_paths = [
            str(item.get("path", "")).strip()
            for item in items
            if isinstance(item, dict) and str(item.get("path", "")).strip()
        ]
        if query_relative_path not in group_paths:
            continue

        reason = str(group.get("reason", "duplicates") or "duplicates")
        for item_path in group_paths:
            if item_path == query_relative_path:
                continue
            try:
                candidate_path = resolve_under_root(active_root, item_path)
            except HTTPException:
                continue
            if not candidate_path.exists() or not candidate_path.is_file():
                continue
            matches[item_path] = {
                "relative_path": item_path,
                "hash": str(group.get("hash", "")),
                "distance": 0,
                "score": 1,
                "reason": f"duplicates:{reason}",
                "source": "duplicates",
            }
    return matches


def search_similar_images(
    relative_path: str,
    method: str = "phash",
    threshold: int = 8,
    limit: int = 50,
) -> dict[str, Any]:
    method = str(method or "phash").strip().lower()
    if method != "phash":
        raise HTTPException(status_code=400, detail="Unsupported similarity method")

    settings = load_settings()
    active_root = Path(settings["active_root"]).expanduser().resolve()
    query_path, normalized_relative_path = _resolve_similarity_query_path(active_root, relative_path)
    if not query_path.exists() or not query_path.is_file():
        raise HTTPException(status_code=404, detail=f"Image not found in current root: {normalized_relative_path}")

    query_hash = compute_phash(str(query_path))
    if not query_hash:
        return {
            "query": normalized_relative_path,
            "method": method,
            "query_hash": "",
            "items": [],
            "count": 0,
        }

    database_path = root_database_path(active_root)
    hash_db = HashDbRepository(database_path).load_hash_db()
    records = _collect_similarity_candidates(active_root, query_path, hash_db)
    items_by_path = _collect_duplicate_group_matches(active_root, normalized_relative_path)

    for candidate_hash, paths in records.items():
        try:
            distance = phash_distance(query_hash, str(candidate_hash))
        except ValueError:
            continue
        if distance > threshold:
            continue

        for candidate_path in paths:
            try:
                candidate_relative = candidate_path.relative_to(active_root).as_posix()
            except ValueError:
                continue
            current = items_by_path.get(candidate_relative)
            item = {
                "relative_path": candidate_relative,
                "hash": str(candidate_hash),
                "distance": distance,
                "score": round(1 - (distance / 64), 4),
                "reason": method,
                "source": "phash",
            }
            if current is None or item["distance"] < current["distance"]:
                items_by_path[candidate_relative] = item

    items = list(items_by_path.values())
    items.sort(key=lambda item: (item["distance"], item["relative_path"].lower()))
    items = items[:limit]
    return {
        "query": normalized_relative_path,
        "method": method,
        "query_hash": query_hash,
        "threshold": threshold,
        "items": items,
        "count": len(items),
    }
