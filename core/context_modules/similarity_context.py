from .base import *
from .settings_context import load_settings
from .image_context import iter_image_files, resolve_under_root
from .root_workspace import root_database_path
from core.domain.root_context import RootContext
from core.storage.duplicates_repository import DuplicateResultRepository
from core.storage.hash_db_repository import HashDbRepository
from core.storage.mobile_repository import MobileRepository
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


def _mobile_record_target(record: dict[str, Any]) -> str:
    album = str(record.get("album", "") or "").strip().strip("/")
    filename = str(record.get("filename", "") or "").strip()
    return f"{album}/{filename}" if album else filename


def _mobile_record_local_path(active_root: Path, record: dict[str, Any]) -> tuple[Path, str] | None:
    for key in ("local_path", "existing_local_path"):
        raw_path = str(record.get(key, "") or "").strip()
        if not raw_path:
            continue
        path = Path(raw_path).expanduser().resolve()
        if not path.is_file():
            continue
        try:
            relative_path = path.relative_to(active_root).as_posix()
        except ValueError:
            continue
        return path, relative_path
    return None


def _collect_local_mobile_records(active_root: Path, device_type: str) -> list[dict[str, Any]]:
    database_path = root_database_path(active_root)
    records = MobileRepository(database_path).list_import_records(device_type)
    local_records: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for record in records:
        local_path = _mobile_record_local_path(active_root, record)
        if local_path is None:
            continue
        path, relative_path = local_path
        phash = str(record.get("phash", "") or "").strip()
        if not phash:
            phash = compute_phash(str(path)) or ""
        if not phash:
            continue
        if relative_path in seen_paths:
            continue
        seen_paths.add(relative_path)
        local_records.append(
            {
                **record,
                "target": _mobile_record_target(record),
                "local_file_path": path,
                "relative_path": relative_path,
                "phash": phash,
            }
        )
    return local_records


def _find_mobile_query_record(
    records: list[dict[str, Any]],
    query: str,
) -> dict[str, Any]:
    normalized_query = str(query or "").strip().strip('"').replace("\\", "/").strip("/")
    if not normalized_query:
        raise HTTPException(status_code=400, detail="Image path is required")

    target_matches = [
        record
        for record in records
        if str(record.get("target", "")).replace("\\", "/").strip("/") == normalized_query
    ]
    if len(target_matches) == 1:
        return target_matches[0]
    if len(target_matches) > 1:
        raise HTTPException(
            status_code=400,
            detail=f"Multiple indexed iPhone photos matched. Use album/filename: {normalized_query}",
        )

    filename_matches = [
        record
        for record in records
        if str(record.get("filename", "") or "").strip() == normalized_query
        or str(record.get("relative_path", "") or "").replace("\\", "/").strip("/") == normalized_query
    ]
    if len(filename_matches) == 1:
        return filename_matches[0]
    if len(filename_matches) > 1:
        raise HTTPException(
            status_code=400,
            detail=f"Multiple indexed iPhone photos matched filename. Use album/filename: {normalized_query}",
        )

    raise HTTPException(status_code=404, detail=f"Indexed iPhone photo not found in local root: {normalized_query}")


def search_similar_mobile_images(
    relative_path: str,
    device_type: str = "iphone",
    method: str = "phash",
    threshold: int = 8,
    limit: int = 50,
) -> dict[str, Any]:
    method = str(method or "phash").strip().lower()
    if method != "phash":
        raise HTTPException(status_code=400, detail="Unsupported similarity method")

    normalized_device_type = str(device_type or "iphone").strip().lower()
    if normalized_device_type != "iphone":
        raise HTTPException(status_code=400, detail=f"Unsupported similarity source: {normalized_device_type}")

    settings = load_settings()
    active_root = Path(settings["active_root"]).expanduser().resolve()
    records = _collect_local_mobile_records(active_root, normalized_device_type)
    query_record = _find_mobile_query_record(records, relative_path)
    query_hash = str(query_record.get("phash", "") or "").strip()

    items: list[dict[str, Any]] = []
    query_relative_path = str(query_record.get("relative_path", ""))
    query_target = str(query_record.get("target", ""))
    for record in records:
        candidate_relative = str(record.get("relative_path", ""))
        candidate_target = str(record.get("target", ""))
        if candidate_relative == query_relative_path and candidate_target == query_target:
            continue
        try:
            distance = phash_distance(query_hash, str(record.get("phash", "")))
        except ValueError:
            continue
        if distance > threshold:
            continue
        items.append(
            {
                "relative_path": candidate_relative,
                "hash": str(record.get("phash", "")),
                "distance": distance,
                "score": round(1 - (distance / 64), 4),
                "reason": method,
                "source": normalized_device_type,
                "device_type": normalized_device_type,
                "device_id": str(record.get("device_id", "")),
                "device_name": str(record.get("device_name", "")),
                "album": str(record.get("album", "")),
                "filename": str(record.get("filename", "")),
                "mobile_target": candidate_target,
                "import_status": str(record.get("import_status", "")),
                "save_state": str(record.get("save_state", "")),
            }
        )

    items.sort(key=lambda item: (item["distance"], item["relative_path"].lower(), item["mobile_target"].lower()))
    items = items[:limit]
    return {
        "query": query_target or query_relative_path,
        "query_relative_path": query_relative_path,
        "source": normalized_device_type,
        "method": method,
        "query_hash": query_hash,
        "threshold": threshold,
        "items": items,
        "count": len(items),
    }


def search_similar_images(
    relative_path: str,
    source: str = "local",
    method: str = "phash",
    threshold: int = 8,
    limit: int = 50,
) -> dict[str, Any]:
    source = str(source or "local").strip().lower()
    if source == "iphone":
        return search_similar_mobile_images(relative_path, "iphone", method, threshold, limit)
    if source != "local":
        raise HTTPException(status_code=400, detail=f"Unsupported similarity source: {source}")

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
        "source": "local",
        "method": method,
        "query_hash": query_hash,
        "threshold": threshold,
        "items": items,
        "count": len(items),
    }
