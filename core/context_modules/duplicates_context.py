from .base import *
from .settings_context import load_settings
from .image_context import resolve_under_root
from core.services.duplicate_result_service import (
    largest_strict_compatible_item_dicts,
    rebuild_duplicate_results_from_hash_db,
)
from core.services.root_read_service import RootReadService


def load_database_duplicates_payload(active_root: str) -> dict[str, Any] | None:
    result = RootReadService.from_root(active_root, ROOT_DATA_DIR).load_duplicate_result()
    if result is None:
        return None
    return result


def load_database_duplicates_page(
    active_root: str,
    *,
    offset: int,
    limit: int,
    method: str,
) -> dict[str, Any] | None:
    result = RootReadService.from_root(active_root, ROOT_DATA_DIR).load_duplicate_result_page(
        offset=offset,
        limit=limit,
        method=method,
    )
    if result is None:
        return None
    return result


def rebuild_dirty_duplicates_if_needed(active_root: str) -> None:
    root_reader = RootReadService.from_root(active_root, ROOT_DATA_DIR)
    repository = root_reader.duplicate_repository()
    summary = root_reader.load_duplicate_summary()
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
        root_reader.load_hash_db(),
        "both",
        phash_threshold,
        sqlite_db_path=str(root_reader.database_path),
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

    summary = RootReadService.from_root(active_root, ROOT_DATA_DIR).load_duplicate_summary()
    destination_root = str(summary.get("destination_root", "")) if summary.get("available") else ""
    if not destination_root:
        DUPLICATES_ROOT_CACHE = (now, active_root, None)
        return None
    root = Path(destination_root).expanduser().resolve() if destination_root else None
    DUPLICATES_ROOT_CACHE = (now, active_root, root)
    return root


def compatible_strict_duplicate_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return list(largest_strict_compatible_item_dicts(items))


def visible_duplicate_group(group: dict[str, Any], destination_root_path: Path | None) -> dict[str, Any] | None:
    group_method = str(group.get("reason", "-")).strip().lower()
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
    if group_method == "strict":
        available_items = compatible_strict_duplicate_items(available_items)
        available_paths = {item["path"] for item in available_items}
        items = [item for item in items if item["path"] in available_paths]
    if len(available_items) < 2:
        return None

    return {
        "group_id": str(group.get("group_id", "")),
        "reason": str(group.get("reason", "-")),
        "hash": str(group.get("hash", "")),
        "kept_path": str(group.get("kept_path", "")),
        "item_count": len(items),
        "available_count": len(available_items),
        "items": items,
        "preview_paths": [item["path"] for item in available_items],
    }


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

    root_reader = RootReadService.from_root(active_root, ROOT_DATA_DIR)
    database_summary = root_reader.load_duplicate_summary()
    if database_summary.get("available") and database_summary.get("dirty"):
        rebuild_dirty_duplicates_if_needed(active_root)
        database_summary = root_reader.load_duplicate_summary()
    scan_from_start = method_filter == "phash"
    initial_offset = 0 if scan_from_start else offset
    database_payload = (
        load_database_duplicates_page(
            active_root,
            offset=initial_offset,
            limit=max(limit + 1, 100) if method_filter else limit + 1,
            method=method_filter,
        )
        if is_paged_request and limit is not None
        else load_database_duplicates_payload(active_root)
    )
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
    if isinstance(database_payload.get("method_counts"), dict):
        method_counts.update(
            {
                str(key).strip().lower(): int(value)
                for key, value in database_payload["method_counts"].items()
                if str(key).strip().lower() in method_counts
            }
        )
    raw_groups = payload.get("groups", [])
    if not isinstance(raw_groups, list):
        raw_groups = []
    if "method_counts" not in database_payload:
        for group in raw_groups:
            group_method = str(group.get("reason", "-")).strip().lower()
            if group_method in method_counts:
                method_counts[group_method] += 1

    matched_group_count = 0 if scan_from_start else initial_offset
    has_more = False
    raw_offset = initial_offset
    batch_limit = max(limit + 1, 100) if limit is not None else 0
    while True:
        for group in raw_groups:
            group_method = str(group.get("reason", "-")).strip().lower()
            if method_filter and group_method != method_filter:
                continue

            visible_group = visible_duplicate_group(group, destination_root_path)
            if visible_group is None:
                continue

            if limit is not None and matched_group_count < offset:
                matched_group_count += 1
                continue

            if limit is not None and len(groups) >= limit:
                has_more = True
                break

            matched_group_count += 1
            groups.append(visible_group)

        if has_more or limit is None or not method_filter:
            break
        if len(raw_groups) < batch_limit:
            break

        raw_offset += len(raw_groups)
        database_payload = load_database_duplicates_page(
            active_root,
            offset=raw_offset,
            limit=batch_limit,
            method=method_filter,
        )
        raw_groups = database_payload.get("groups", []) if database_payload else []
        if not isinstance(raw_groups, list) or not raw_groups:
            break

    if limit is None:
        group_count = len(groups)
    elif method_filter:
        group_count = method_counts.get(method_filter, matched_group_count + len(groups) + (1 if has_more else 0))
    else:
        raw_group_count = payload.get("group_count")
        group_count = raw_group_count if isinstance(raw_group_count, int) else len(raw_groups)

    return {
        "available": True,
        "database_path": str(root_reader.database_path) if database_payload is not None else "",
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
    database_summary = RootReadService.from_root(active_root, ROOT_DATA_DIR).load_duplicate_summary()
    if database_summary.get("available"):
        return {"available": True, "group_count": database_summary.get("group_count", 0)}

    return {"available": False, "group_count": 0}
