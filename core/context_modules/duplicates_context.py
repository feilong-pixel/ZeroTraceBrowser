from .base import *
from .settings_context import load_settings
from .image_context import resolve_under_root
from core.domain.root_context import RootContext
from core.storage.duplicates_repository import DuplicateResultRepository
from core.storage.hash_db_repository import HashDbRepository
from MediaArchiveOrganizer.services.organizer import rebuild_duplicate_results_from_hash_db


def load_database_duplicates_payload(active_root: str) -> dict[str, Any] | None:
    database_path = RootContext.from_root(active_root, ROOT_DATA_DIR, ensure=True).database_path
    result = DuplicateResultRepository(database_path).load_result()
    if result is None:
        return None
    return result


def rebuild_dirty_duplicates_if_needed(active_root: str) -> None:
    database_path = RootContext.from_root(active_root, ROOT_DATA_DIR, ensure=True).database_path
    repository = DuplicateResultRepository(database_path)
    summary = repository.load_summary()
    if not summary.get("dirty"):
        return

    settings = load_settings()
    task_defaults = settings.get("task_defaults", {})
    if not isinstance(task_defaults, dict):
        task_defaults = {}
    try:
        phash_threshold = max(0, int(task_defaults.get("rebuild_phash_threshold", task_defaults.get("phash_threshold", 4))))
    except (TypeError, ValueError):
        phash_threshold = 4

    rebuild_duplicate_results_from_hash_db(
        active_root,
        "",
        HashDbRepository(database_path).load_hash_db(),
        "both",
        phash_threshold,
        sqlite_db_path=str(database_path),
    )
    repository.clear_dirty()
    clear_duplicates_path_cache()


def clear_duplicates_path_cache() -> None:
    global DUPLICATES_ROOT_CACHE
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

    payload = load_database_duplicates_payload(active_root)
    if payload is not None:
        destination_root = str(payload.get("destination_root", ""))
    else:
        destination_root = ""
    if not destination_root:
        DUPLICATES_ROOT_CACHE = (now, active_root, None)
        return None
    root = Path(destination_root).expanduser().resolve() if destination_root else None
    DUPLICATES_ROOT_CACHE = (now, active_root, root)
    return root


def load_duplicates_payload(
    offset: int = 0,
    limit: int | None = None,
    method: str | None = None,
) -> dict[str, Any]:
    settings = load_settings()
    active_root = str(Path(settings["active_root"]).resolve())
    offset = max(0, offset)
    limit = max(1, limit) if limit is not None else None
    method_filter = str(method or "").strip().lower()
    is_paged_request = offset != 0 or limit is not None or bool(method_filter)

    database_payload = load_database_duplicates_payload(active_root)
    if database_payload is not None and database_payload.get("dirty"):
        rebuild_dirty_duplicates_if_needed(active_root)
        database_payload = load_database_duplicates_payload(active_root)
    if database_payload is None:
        result = {
            "available": False,
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

    payload = database_payload
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
        "database_path": str(RootContext.from_root(active_root, ROOT_DATA_DIR, ensure=True).database_path) if database_payload is not None else "",
        "generated_at": payload.get("generated_at"),
        "destination_root": destination_root,
        "active_root": active_root,
        "active_root_matches": destination_root == active_root,
        "dirty": bool(payload.get("dirty")),
        "dirty_reason": str(payload.get("dirty_reason", "")),
        "dirty_at": payload.get("dirty_at"),
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
    database_summary = DuplicateResultRepository(
        RootContext.from_root(active_root, ROOT_DATA_DIR, ensure=True).database_path
    ).load_summary()
    if database_summary.get("available"):
        return {"available": True, "group_count": database_summary.get("group_count", 0)}

    return {"available": False, "group_count": 0}
