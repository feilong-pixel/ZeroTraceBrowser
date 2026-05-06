from .base import *
from .settings_context import get_active_image_root
from .root_workspace import ensure_root_workspace, ensure_log_file, root_log_dir, root_deleted_dir


def append_log(log_name: str, *values: str) -> None:
    root_value = values[1] if len(values) >= 2 and str(values[1]).strip() else str(get_active_image_root())
    log_dir = root_log_dir(root_value)
    ensure_root_workspace(root_value)
    ensure_log_file(log_dir, log_name)
    append_log_service(log_dir, log_name, *values)


def read_delete_log_rows() -> list[dict[str, str]]:
    root = get_active_image_root()
    rows = read_delete_log_rows_service(root_log_dir(root))
    return rows if rows else read_delete_log_rows_service(LOG_DIR)


def write_delete_log_rows(rows: list[dict[str, str]]) -> None:
    root = get_active_image_root()
    ensure_root_workspace(root)
    write_delete_log_rows_service(root_log_dir(root), rows)


def archive_delete_log() -> dict[str, Any]:
    root = get_active_image_root()
    ensure_root_workspace(root)
    return archive_delete_log_service(root_log_dir(root))


def list_recycle_items() -> list[dict[str, Any]]:
    root = get_active_image_root()
    items = list_recycle_items_service(read_delete_log_rows(), root_deleted_dir(root))
    if items:
        return items
    return list_recycle_items_service(read_delete_log_rows_service(LOG_DIR), DELETED_DIR)


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
