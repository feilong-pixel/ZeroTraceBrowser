from .base import *
from .settings_context import load_settings
from .root_workspace import root_duplicates_path
from .artifact_context import load_artifact_index
from .image_context import resolve_under_root
from core.domain.root_context import RootContext
from core.storage.duplicates_repository import DuplicateResultRepository


def iter_duplicates_result_paths() -> list[Path]:
    latest_dir_path = TASK_LOG_DIR / "latest" / "duplicates.json"
    candidates: list[Path] = []
    if latest_dir_path.exists():
        candidates.append(latest_dir_path)

    candidates.extend(
        path for path in ROOT_DATA_DIR.glob("*/duplicates.json")
        if path.exists()
    )

    candidates.extend(
        path for path in TASK_LOG_DIR.rglob("duplicates.json")
        if path != latest_dir_path
    )
    return sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)


def read_duplicates_destination_root(json_path: Path) -> str:
    try:
        with json_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return ""

    destination_root = payload.get("destination_root", "")
    return str(Path(destination_root).expanduser().resolve()) if destination_root else ""


def get_latest_duplicates_path(active_root: str | None = None) -> Path | None:
    global DUPLICATES_PATH_CACHE

    now = time.monotonic()
    cached_at, cached_path = DUPLICATES_PATH_CACHE
    if active_root is None and now - cached_at <= DUPLICATES_PATH_CACHE_TTL_SECONDS:
        if cached_path is None or cached_path.exists():
            return cached_path

    if active_root:
        root_scoped_path = root_duplicates_path(active_root)
        if root_scoped_path.exists():
            return root_scoped_path

        indexed_path = load_artifact_index("duplicates").get(str(Path(active_root).expanduser().resolve()), "").strip()
        if indexed_path:
            indexed_candidate = Path(indexed_path).expanduser().resolve()
            if indexed_candidate.exists():
                root_scoped_path.parent.mkdir(parents=True, exist_ok=True)
                if not root_scoped_path.exists():
                    shutil.copy2(indexed_candidate, root_scoped_path)
                return root_scoped_path

    candidates = iter_duplicates_result_paths()
    if active_root:
        normalized_active_root = str(Path(active_root).expanduser().resolve())
        for candidate in candidates:
            if read_duplicates_destination_root(candidate) == normalized_active_root:
                return candidate
        return None

    latest = candidates[0] if candidates else None
    if active_root is None:
        DUPLICATES_PATH_CACHE = (now, latest)
    return latest


def load_database_duplicates_payload(active_root: str) -> dict[str, Any] | None:
    database_path = RootContext.from_root(active_root, ROOT_DATA_DIR, ensure=True).database_path
    result = DuplicateResultRepository(database_path).load_result()
    if result is None:
        return None
    return result


def clear_duplicates_path_cache() -> None:
    global DUPLICATES_PATH_CACHE, DUPLICATES_ROOT_CACHE
    DUPLICATES_PATH_CACHE = (0.0, None)
    DUPLICATES_ROOT_CACHE = (0.0, "", None)


def get_duplicates_root_from_payload(payload: dict[str, Any]) -> Path | None:
    destination_root = payload.get("destination_root", "")
    if not destination_root:
        return None
    return Path(destination_root).expanduser().resolve()


def get_latest_duplicates_result_root() -> Path | None:
    global DUPLICATES_ROOT_CACHE

    settings = load_settings()
    active_root = str(Path(settings["active_root"]).resolve())
    now = time.monotonic()
    cached_at, cached_active_root, cached_root = DUPLICATES_ROOT_CACHE
    if cached_active_root == active_root and now - cached_at <= DUPLICATES_PATH_CACHE_TTL_SECONDS:
        if cached_root is None or cached_root.exists():
            return cached_root

    target = get_latest_duplicates_path(active_root)
    if target is not None and target.exists():
        destination_root = read_duplicates_destination_root(target)
    else:
        payload = load_database_duplicates_payload(active_root)
        destination_root = str(payload.get("destination_root", "")) if payload else ""
    if not destination_root:
        DUPLICATES_ROOT_CACHE = (now, active_root, None)
        return None
    root = Path(destination_root).expanduser().resolve() if destination_root else None
    DUPLICATES_ROOT_CACHE = (now, active_root, root)
    return root


def load_duplicates_payload(
    json_path: Path | None = None,
    offset: int = 0,
    limit: int | None = None,
    method: str | None = None,
) -> dict[str, Any]:
    settings = load_settings()
    active_root = str(Path(settings["active_root"]).resolve())
    target = json_path or get_latest_duplicates_path(active_root)
    offset = max(0, offset)
    limit = max(1, limit) if limit is not None else None
    method_filter = str(method or "").strip().lower()
    is_paged_request = offset != 0 or limit is not None or bool(method_filter)

    database_payload = None
    if target is None or not target.exists():
        database_payload = load_database_duplicates_payload(active_root)
    if (target is None or not target.exists()) and database_payload is None:
        result = {
            "available": False,
            "json_path": "",
            "generated_at": None,
            "destination_root": "",
            "active_root": active_root,
            "active_root_matches": False,
            "groups": [],
            "group_count": 0,
        }
        if is_paged_request:
            result.update(
                {
                    "method_counts": {"phash": 0, "strict": 0},
                    "page_offset": offset,
                    "page_limit": limit,
                    "method_filter": method_filter,
                    "has_more": False,
                }
            )
        return result

    if database_payload is not None:
        payload = database_payload
        result_path = ""
    else:
        with target.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        result_path = str(target)

    destination_root_path = get_duplicates_root_from_payload(payload)
    destination_root = str(destination_root_path) if destination_root_path else ""
    groups = []
    method_counts = {"phash": 0, "strict": 0}
    raw_groups = payload.get("groups", [])
    if not isinstance(raw_groups, list):
        raw_groups = []
    for group in raw_groups:
        group_method = str(group.get("reason", "-")).strip().lower()
        if group_method in method_counts:
            method_counts[group_method] += 1

    matched_group_count = 0
    has_more = False
    for group in raw_groups:
        group_method = str(group.get("reason", "-")).strip().lower()
        if method_filter and group_method != method_filter:
            continue

        items = []
        for item in group.get("items", []):
            if not isinstance(item, dict) or not item.get("path"):
                continue
            path_value = str(item["path"])
            exists = False
            if destination_root_path is not None:
                try:
                    candidate = resolve_under_root(destination_root_path, path_value)
                    exists = candidate.exists() and candidate.is_file()
                except HTTPException:
                    exists = False
            items.append(
                {
                    "role": str(item.get("role", "")),
                    "path": path_value,
                    "exists": exists,
                }
            )

        available_items = [item for item in items if item["exists"]]
        if len(available_items) < 2:
            continue

        if limit is not None and matched_group_count < offset:
            matched_group_count += 1
            continue

        if limit is not None and len(groups) >= limit:
            has_more = True
            break

        matched_group_count += 1
        preview_paths = [item["path"] for item in available_items]
        groups.append(
            {
                "group_id": str(group.get("group_id", "")),
                "reason": str(group.get("reason", "-")),
                "hash": str(group.get("hash", "")),
                "kept_path": str(group.get("kept_path", "")),
                "item_count": len(items),
                "available_count": len(available_items),
                "items": items,
                "preview_paths": preview_paths,
            }
        )

    if limit is None:
        group_count = len(groups)
    elif method_filter:
        group_count = method_counts.get(method_filter, matched_group_count + len(groups) + (1 if has_more else 0))
    else:
        raw_group_count = payload.get("group_count")
        group_count = raw_group_count if isinstance(raw_group_count, int) else len(raw_groups)

    return {
        "available": True,
        "json_path": result_path,
        "database_path": str(RootContext.from_root(active_root, ROOT_DATA_DIR, ensure=True).database_path) if database_payload is not None else "",
        "generated_at": payload.get("generated_at"),
        "destination_root": destination_root,
        "active_root": active_root,
        "active_root_matches": destination_root == active_root,
        "groups": groups,
        "group_count": group_count,
        "method_counts": method_counts,
        "page_offset": offset,
        "page_limit": limit,
        "method_filter": method_filter,
        "has_more": has_more,
    }


def load_duplicates_summary() -> dict[str, Any]:
    settings = load_settings()
    active_root = str(Path(settings["active_root"]).resolve())
    target = get_latest_duplicates_path(active_root)
    if target is None or not target.exists():
        database_summary = DuplicateResultRepository(
            RootContext.from_root(active_root, ROOT_DATA_DIR, ensure=True).database_path
        ).load_summary()
        if database_summary.get("available"):
            return {"available": True, "group_count": database_summary.get("group_count", 0)}
        return {"available": False, "group_count": 0}

    try:
        with target.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {"available": False, "group_count": 0}

    group_count = payload.get("group_count")
    if not isinstance(group_count, int):
        groups = payload.get("groups", [])
        group_count = len(groups) if isinstance(groups, list) else 0

    return {"available": True, "group_count": group_count}
