from .base import *


def get_settings_store() -> SettingsStore:
    return SettingsStore(
        SETTINGS_PATH,
        DEFAULT_IMAGE_ROOT,
        DEFAULT_COPY_TARGET,
        SUPPORTED_LANGUAGES,
    )


def default_settings() -> dict[str, Any]:
    return get_settings_store().default_settings()


def load_settings() -> dict[str, Any]:
    return get_settings_store().load()


def save_settings(settings: dict[str, Any]) -> None:
    get_settings_store().save(settings)


def get_active_image_root() -> Path:
    return get_settings_store().active_root()


def validate_language(language: str) -> str:
    return get_settings_store().validate_language(language)


def validate_display_style(display_style: str) -> str:
    return get_settings_store().validate_display_style(display_style)


def serialize_settings(settings: dict[str, Any]) -> dict[str, Any]:
    return get_settings_store().serialize(settings)


def get_root_summary(root: str | Path) -> dict[str, Any]:
    from .root_workspace import root_image_index_dir
    normalized_root = Path(root).expanduser().resolve()
    cache_key = image_scan_cache_key(normalized_root, SUPPORTED_EXTENSIONS, SKIP_SCAN_DIR_NAMES)
    metadata = load_image_index_summary_metadata_service(root_image_index_dir(normalized_root), cache_key)
    if (
        isinstance(metadata.get("total"), int)
        or isinstance(metadata.get("duplicate_group_count"), int)
        or str(metadata.get("generated_at", "")).strip()
    ):
        return {
            "image_count": metadata.get("total") if isinstance(metadata.get("total"), int) else None,
            "duplicate_group_count": metadata.get("duplicate_group_count") if isinstance(metadata.get("duplicate_group_count"), int) else None,
            "updated_at": str(metadata.get("generated_at", "")).strip(),
        }

    settings = load_settings()
    normalized_root_str = str(normalized_root)
    summaries = settings.get("root_summaries", {})
    if not isinstance(summaries, dict):
        return {"image_count": None, "duplicate_group_count": None, "updated_at": ""}
    summary = summaries.get(normalized_root_str, {})
    if not isinstance(summary, dict):
        return {"image_count": None, "duplicate_group_count": None, "updated_at": ""}
    return {
        "image_count": summary.get("image_count") if isinstance(summary.get("image_count"), int) else None,
        "duplicate_group_count": summary.get("duplicate_group_count") if isinstance(summary.get("duplicate_group_count"), int) else None,
        "updated_at": str(summary.get("updated_at", "")).strip(),
    }


def get_safe_open_roots(settings: dict[str, Any] | None = None) -> list[Path]:
    from .artifact_context import get_hash_db_path
    from .root_workspace import root_data_dir
    settings = settings or load_settings()
    roots = [DATA_DIR, ROOT_DATA_DIR, LOG_DIR, THUMBNAIL_DIR, DELETED_DIR, ORGANIZER_DIR]

    for value in settings.get("image_roots", []):
        if str(value).strip():
            roots.append(resolve_path(str(value)))

    default_copy_target = str(settings.get("default_copy_target", "")).strip()
    if default_copy_target:
        roots.append(resolve_path(default_copy_target))

    task_defaults = settings.get("task_defaults", {})
    if isinstance(task_defaults, dict):
        for key in ("src", "dst", "rebuild_root"):
            value = str(task_defaults.get(key, "")).strip()
            if value:
                roots.append(resolve_path(value))

    active_root = settings.get("active_root", "") if isinstance(settings, dict) else ""
    hash_db_path = get_hash_db_path(active_root if active_root else None)
    roots.append(hash_db_path if hash_db_path.is_dir() else hash_db_path.parent)
    if active_root:
        roots.append(root_data_dir(active_root))
    return list(dict.fromkeys(roots))


def remember_task_defaults(payload: OrganizerTaskRequest) -> None:
    get_settings_store().remember_task_defaults(
        payload.src,
        payload.dst,
        payload.mode,
        payload.duplicate_detection,
        payload.phash_threshold,
    )


def remember_rebuild_root(root: str) -> None:
    get_settings_store().remember_rebuild_root(root)


def save_root_summary(
    root: str,
    image_count: int | None = None,
    duplicate_group_count: int | None = None,
    updated_at: str = "",
) -> None:
    get_settings_store().save_root_summary(root, image_count, duplicate_group_count, updated_at)
