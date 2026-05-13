from .base import *
from .settings_context import default_settings, load_settings, save_settings, get_active_image_root, validate_language, serialize_settings, get_root_summary


def normalize_root_value(root: str | Path) -> str:
    return normalize_root_path(root)


def root_data_id(root: str | Path) -> str:
    return root_id_for(root)


def root_data_dir(root: str | Path) -> Path:
    return RootContext.from_root(root, ROOT_DATA_DIR).data_dir


def root_log_dir(root: str | Path) -> Path:
    return RootContext.from_root(root, ROOT_DATA_DIR).logs_dir


def root_task_log_dir(root: str | Path) -> Path:
    return RootContext.from_root(root, ROOT_DATA_DIR).tasks_dir


def root_thumbnail_dir(root: str | Path) -> Path:
    return RootContext.from_root(root, ROOT_DATA_DIR).thumbnails_dir


def root_image_index_dir(root: str | Path) -> Path:
    return RootContext.from_root(root, ROOT_DATA_DIR).indexes_dir


def root_deleted_dir(root: str | Path) -> Path:
    return RootContext.from_root(root, ROOT_DATA_DIR).deleted_dir


def root_workspace_metadata_path(root: str | Path) -> Path:
    return RootContext.from_root(root, ROOT_DATA_DIR).root_json_path


def root_hash_db_path(root: str | Path) -> Path:
    return RootContext.from_root(root, ROOT_DATA_DIR).hash_db_path


def root_duplicates_path(root: str | Path) -> Path:
    return RootContext.from_root(root, ROOT_DATA_DIR).duplicates_path


def root_database_path(root: str | Path) -> Path:
    return RootContext.from_root(root, ROOT_DATA_DIR).database_path


def ensure_root_workspace(root: str | Path) -> Path:
    normalized = normalize_root_value(root)
    workspace_context = RootContext.from_root(normalized, ROOT_DATA_DIR, ensure=True)
    workspace = workspace_context.data_dir
    metadata_path = workspace_context.root_json_path
    if not metadata_path.exists():
        metadata_path.write_text(
            json.dumps(
                {
                    "root": normalized,
                    "root_id": workspace_context.root_id,
                    "created_at": datetime.now().isoformat(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    return workspace


def image_index_dir_for_read(root: str | Path) -> Path:
    normalized = Path(root).expanduser().resolve()
    return root_image_index_dir(normalized)


def ensure_log_file(log_dir: Path, log_name: str) -> None:
    headers_by_name = {
        "delete_log.csv": ["timestamp", "root", "relative_path", "deleted_to", "action"],
        "copy_log.csv": ["timestamp", "root", "relative_path", "copied_to"],
    }
    headers = headers_by_name.get(log_name)
    if headers is None:
        return
    log_path = log_dir / log_name
    if not log_path.exists():
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("w", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerow(headers)


def current_root_workspace() -> Path:
    return ensure_root_workspace(get_active_image_root())


def ensure_directories() -> None:
    for path in (STATIC_DIR, DATA_DIR, ROOT_DATA_DIR, ARTIFACT_INDEX_DIR):
        path.mkdir(parents=True, exist_ok=True)

    if not SETTINGS_PATH.exists():
        save_settings(default_settings())

    for root in load_settings().get("image_roots", []):
        if str(root).strip():
            workspace = ensure_root_workspace(root)
            ensure_log_file(workspace / "logs", "delete_log.csv")
            ensure_log_file(workspace / "logs", "copy_log.csv")
