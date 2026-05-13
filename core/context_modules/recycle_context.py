from .base import *
from .settings_context import get_active_image_root
from .root_workspace import ensure_root_workspace, ensure_log_file, root_log_dir, root_deleted_dir, root_database_path
from .system_context import is_windows, move_to_system_recycle_bin
from core.storage.recycle_repository import RecycleRepository
from core.services.recycle_service import list_recycle_items_from_records


def migrate_delete_log_rows_to_database(root: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    repository = RecycleRepository(root_database_path(root))
    for row in rows:
        deleted_to = str(row.get("deleted_to", "")).strip()
        if not deleted_to:
            continue
        repository.append_record(
            timestamp=str(row.get("timestamp", "")),
            root=str(row.get("root", "") or root),
            relative_path=str(row.get("relative_path", "")),
            deleted_to=deleted_to,
            action=str(row.get("action", "deleted") or "deleted"),
        )


def read_recycle_records_from_database(root: Path, *, include_terminal: bool = True) -> list[dict[str, Any]]:
    repository = RecycleRepository(root_database_path(root))
    rows = repository.list_records(include_terminal=include_terminal)
    if rows:
        return rows
    legacy_rows = read_delete_log_rows_service(root_log_dir(root))
    if legacy_rows:
        migrate_delete_log_rows_to_database(root, legacy_rows)
        return repository.list_records(include_terminal=include_terminal)
    return []


def ensure_recycle_records_in_database(root: Path) -> RecycleRepository:
    repository = RecycleRepository(root_database_path(root))
    if repository.count_records() == 0:
        legacy_rows = read_delete_log_rows_service(root_log_dir(root))
        if legacy_rows:
            migrate_delete_log_rows_to_database(root, legacy_rows)
    return repository

def prepare_system_recycle_path(deleted_path: Path, log_row: dict[str, str] | None) -> tuple[Path, Path]:
    thumb_path = deleted_thumbnail_path_for(deleted_path)
    original_name = Path(log_row.get("relative_path", "")).name if log_row else ""
    if not original_name or deleted_path.name == original_name:
        return deleted_path, thumb_path

    restored_name_path = deleted_path.parent / original_name
    if restored_name_path.exists():
        return deleted_path, thumb_path

    move_file_preserve_times_service(deleted_path, restored_name_path)
    return restored_name_path, thumb_path


def dispose_recycle_file(path: Path) -> None:
    if is_windows():
        move_to_system_recycle_bin(path)
        return

    path.unlink()


def append_log(log_name: str, *values: str) -> None:
    root_value = values[1] if len(values) >= 2 and str(values[1]).strip() else str(get_active_image_root())
    log_dir = root_log_dir(root_value)
    ensure_root_workspace(root_value)
    ensure_log_file(log_dir, log_name)
    append_log_service(log_dir, log_name, *values)
    if log_name == "delete_log.csv" and len(values) >= 5:
        RecycleRepository(root_database_path(root_value)).append_record(
            timestamp=str(values[0]),
            root=str(values[1] or root_value),
            relative_path=str(values[2]),
            deleted_to=str(values[3]),
            action=str(values[4] or "deleted"),
        )


def read_delete_log_rows() -> list[dict[str, str]]:
    root = get_active_image_root()
    rows = read_delete_log_rows_service(root_log_dir(root))
    if rows:
        migrate_delete_log_rows_to_database(root, rows)
        return rows
    db_rows = read_recycle_records_from_database(root)
    return db_rows if db_rows else read_delete_log_rows_service(LOG_DIR)


def read_delete_log_rows_page(offset: int = 0, limit: int | None = None) -> dict[str, Any]:
    root = get_active_image_root()
    rows = read_delete_log_rows_service(root_log_dir(root))
    if not rows:
        rows = read_recycle_records_from_database(root)
    if not rows:
        rows = read_delete_log_rows_service(LOG_DIR)
    rows = sorted(rows, key=lambda row: row["timestamp"], reverse=True)
    total = len(rows)
    if limit is not None:
        rows = rows[offset:offset + limit]
    return {"items": rows, "count": total}


def write_delete_log_rows(rows: list[dict[str, str]]) -> None:
    root = get_active_image_root()
    ensure_root_workspace(root)
    write_delete_log_rows_service(root_log_dir(root), rows)
    repository = RecycleRepository(root_database_path(root))
    repository.clear_records()
    migrate_delete_log_rows_to_database(root, rows)


def archive_delete_log() -> dict[str, Any]:
    root = get_active_image_root()
    ensure_root_workspace(root)
    return archive_delete_log_service(root_log_dir(root))


def list_recycle_items() -> list[dict[str, Any]]:
    root = get_active_image_root()
    items = list_recycle_items_service(read_recycle_records_from_database(root, include_terminal=False), root_deleted_dir(root))
    if items:
        return items
    return list_recycle_items_service(read_delete_log_rows_service(LOG_DIR), DELETED_DIR)


def list_recycle_items_page(offset: int = 0, limit: int | None = None) -> dict[str, Any]:
    root = get_active_image_root()
    repository = RecycleRepository(root_database_path(root))
    total = repository.count_records(include_terminal=False)
    if total:
        rows = repository.list_records(include_terminal=False, offset=offset, limit=limit)
        items = list_recycle_items_from_records(rows)
        return {"items": items, "count": total}

    deleted_dir = root_deleted_dir(root)
    root_deleted_empty = not deleted_dir.exists() or not any(deleted_dir.iterdir())
    legacy_deleted_empty = not DELETED_DIR.exists() or not any(DELETED_DIR.iterdir())
    if repository.count_records() > 0 or (root_deleted_empty and legacy_deleted_empty):
        return {"items": [], "count": 0}

    repository = ensure_recycle_records_in_database(root)
    total = repository.count_records(include_terminal=False)
    if total:
        rows = repository.list_records(include_terminal=False, offset=offset, limit=limit)
        items = list_recycle_items_from_records(rows)
        return {"items": items, "count": total}

    legacy_items = list_recycle_items_service(read_delete_log_rows_service(LOG_DIR), DELETED_DIR)
    legacy_total = len(legacy_items)
    if limit is not None:
        legacy_items = legacy_items[offset:offset + limit]
    return {"items": legacy_items, "count": legacy_total}


def build_deleted_path(root: Path, relative_path: str) -> Path:
    ensure_root_workspace(root)
    return build_deleted_path_for_service(root_deleted_dir(root), root, relative_path)


def resolve_deleted_file(candidate: str) -> Path:
    deleted_path = Path(candidate).expanduser().resolve()
    active_deleted_dir = root_deleted_dir(get_active_image_root()).resolve()
    for allowed_root in (active_deleted_dir, DELETED_DIR.resolve(), ROOT_DATA_DIR.resolve()):
        try:
            deleted_path.relative_to(allowed_root)
            return deleted_path
        except ValueError:
            continue
    raise HTTPException(status_code=400, detail="Invalid deleted file path")


def remove_empty_deleted_parent(deleted_path: Path) -> None:
    if deleted_path.resolve().is_relative_to(ROOT_DATA_DIR.resolve()):
        parts = deleted_path.resolve().relative_to(ROOT_DATA_DIR.resolve()).parts
        if parts:
            remove_empty_deleted_parent_service(ROOT_DATA_DIR / parts[0] / "deleted", deleted_path)
            return
    for deleted_dir in (root_deleted_dir(get_active_image_root()), DELETED_DIR):
        try:
            deleted_path.resolve().relative_to(deleted_dir.resolve())
        except ValueError:
            continue
        remove_empty_deleted_parent_service(deleted_dir, deleted_path)
        return


def deleted_thumbnail_path_for(deleted_path: Path) -> Path:
    try:
        relative = deleted_path.resolve().relative_to(ROOT_DATA_DIR.resolve())
    except ValueError:
        return deleted_thumbnail_path_for_service(THUMBNAIL_DIR, deleted_path)
    root_id = relative.parts[0] if relative.parts else ""
    if root_id:
        return deleted_thumbnail_path_for_service(ROOT_DATA_DIR / root_id / "thumbnails", deleted_path)
    return deleted_thumbnail_path_for_service(THUMBNAIL_DIR, deleted_path)
