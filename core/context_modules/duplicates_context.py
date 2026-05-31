from .base import *
from .settings_context import load_settings
from .image_context import resolve_under_root
from core.services.duplicate_result_service import (
    largest_strict_compatible_item_dicts,
    rebuild_duplicate_results_from_hash_db,
)
from core.services.root_read_service import RootReadService
from core.storage.recycle_repository import RecycleRepository

RECYCLE_DUPLICATE_SYNC_CACHE: dict[str, tuple[int, str, str]] = {}


def load_database_duplicates_payload(active_root: str) -> dict[str, Any] | None:
    result = RootReadService.from_root(active_root, ROOT_DATA_DIR).load_duplicate_result()
    if result is None:
        return None
    return result


def load_database_remaining_duplicates_page(
    active_root: str,
    *,
    offset: int,
    limit: int,
    method: str,
) -> dict[str, Any] | None:
    result = RootReadService.from_root(active_root, ROOT_DATA_DIR).load_remaining_duplicate_result_page(
        offset=offset,
        limit=limit,
        method=method,
    )
    if result is None:
        return None
    return result


def reconcile_duplicate_page_availability(
    active_root: str,
    groups: list[dict[str, Any]],
    destination_root_path: Path | None,
) -> int:
    if destination_root_path is None:
        return 0

    missing_paths: set[str] = set()
    for group in groups:
        for item in group.get("items", []):
            if not isinstance(item, dict) or not item.get("path") or item.get("exists") is False:
                continue
            path_value = str(item["path"])
            try:
                candidate = resolve_under_root(destination_root_path, path_value)
                if not candidate.exists() or not candidate.is_file():
                    missing_paths.add(path_value)
            except HTTPException:
                missing_paths.add(path_value)

    if not missing_paths:
        return 0

    repository = RootReadService.from_root(active_root, ROOT_DATA_DIR).duplicate_repository()
    return repository.mark_items_missing(list(missing_paths))


def sync_duplicates_availability_from_recycle(active_root: str) -> None:
    root_reader = RootReadService.from_root(active_root, ROOT_DATA_DIR)
    repository = root_reader.duplicate_repository()
    recycle_repository = RecycleRepository(root_reader.database_path)
    duplicate_updated_at = str(root_reader.load_duplicate_summary().get("updated_at", ""))
    recycle_count, recycle_updated_at = recycle_repository.sync_signature()
    cache_key = str(root_reader.database_path)
    signature = (recycle_count, recycle_updated_at, duplicate_updated_at)
    if RECYCLE_DUPLICATE_SYNC_CACHE.get(cache_key) == signature:
        return

    missing_paths: set[str] = set()
    available_paths: set[str] = set()

    try:
        records = recycle_repository.list_records()
    except Exception:
        return

    for record in reversed(records):
        if str(Path(record.get("root", "")).expanduser().resolve()) != active_root:
            continue
        relative_path = str(record.get("relative_path", "")).strip()
        if not relative_path:
            continue
        action = str(record.get("action", "")).strip().lower()
        if action in {"deleted", "purged"}:
            missing_paths.add(relative_path)
            available_paths.discard(relative_path)
        elif action == "restored":
            available_paths.add(relative_path)
            missing_paths.discard(relative_path)

    if missing_paths:
        repository.mark_items_missing(list(missing_paths))
    if available_paths:
        repository.mark_items_available(list(available_paths))
    RECYCLE_DUPLICATE_SYNC_CACHE[cache_key] = signature


def load_reconciled_remaining_duplicates_page(
    active_root: str,
    *,
    offset: int,
    limit: int,
    method: str,
) -> dict[str, Any] | None:
    payload = None
    for _ in range(2):
        payload = load_database_remaining_duplicates_page(
            active_root,
            offset=offset,
            limit=limit,
            method=method,
        )
        if payload is None:
            return None
        destination_root_path = get_duplicates_root_from_payload(payload)
        raw_groups = payload.get("groups", [])
        if not isinstance(raw_groups, list) or not raw_groups:
            return payload
        if reconcile_duplicate_page_availability(active_root, raw_groups, destination_root_path) == 0:
            break

    return load_database_remaining_duplicates_page(
        active_root,
        offset=offset,
        limit=limit,
        method=method,
    )


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


def visible_duplicate_group(
    group: dict[str, Any],
    destination_root_path: Path | None,
    *,
    trust_database_exists: bool = False,
) -> dict[str, Any] | None:
    group_method = str(group.get("reason", "-")).strip().lower()
    items = []
    for item in group.get("items", []):
        if not isinstance(item, dict) or not item.get("path"):
            continue
        path_value = str(item["path"])
        if trust_database_exists and item.get("exists") is False:
            exists = False
        elif trust_database_exists and item.get("exists") is True:
            exists = True
        elif destination_root_path is not None:
            try:
                candidate = resolve_under_root(destination_root_path, path_value)
                exists = candidate.exists() and candidate.is_file()
            except HTTPException:
                exists = False
        else:
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
    if database_summary.get("available"):
        sync_duplicates_availability_from_recycle(active_root)
        database_summary = root_reader.load_duplicate_summary()
    database_payload = (
        load_reconciled_remaining_duplicates_page(
            active_root,
            offset=offset,
            limit=limit,
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

    if limit is not None and method_filter:
        raw_group_count = int(method_counts.get(method_filter, 0))
        for group in raw_groups:
            visible_group = visible_duplicate_group(group, destination_root_path, trust_database_exists=True)
            if visible_group is not None:
                groups.append(visible_group)
        group_count = raw_group_count
        has_more = offset + limit < group_count
        method_counts[method_filter] = group_count
    else:
        has_more = False
        for group in raw_groups:
            group_method = str(group.get("reason", "-")).strip().lower()
            if method_filter and group_method != method_filter:
                continue
            visible_group = visible_duplicate_group(group, destination_root_path)
            if visible_group is None:
                continue
            groups.append(visible_group)
            if group_method in method_counts:
                method_counts[group_method] += 1
        group_count = len(groups)

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
        method_counts = {"phash": 0, "strict": 0}
        if isinstance(database_summary.get("method_counts"), dict):
            method_counts.update(
                {
                    str(key).strip().lower(): int(value)
                    for key, value in database_summary["method_counts"].items()
                    if str(key).strip().lower() in method_counts
                }
            )
        return {
            "available": True,
            "group_count": method_counts["phash"] + method_counts["strict"],
            "method_counts": method_counts,
            "generated_at": database_summary.get("generated_at"),
        }

    return {"available": False, "group_count": 0, "method_counts": {"phash": 0, "strict": 0}}
