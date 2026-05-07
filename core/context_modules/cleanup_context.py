from .base import *
from .settings_context import load_settings, save_settings
from .root_workspace import root_image_index_dir, root_thumbnail_dir, root_duplicates_path, root_hash_db_path, root_log_dir, root_data_dir
from .image_context import thumbnail_path_for, clear_image_list_cache
from .recycle_context import resolve_deleted_file, deleted_thumbnail_path_for, remove_empty_deleted_parent
from .artifact_context import load_artifact_index, save_artifact_index
from .duplicates_context import clear_duplicates_path_cache
from .system_context import move_to_system_recycle_bin


def path_is_inside_data_roots(path: Path) -> bool:
    target = path.resolve()
    for root in (DATA_DIR, ROOT_DATA_DIR, ARTIFACT_INDEX_DIR, ORGANIZER_DIR):
        try:
            target.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False


def unlink_local_file(path: Path) -> bool:
    target = path.expanduser().resolve()
    if not path_is_inside_data_roots(target) or not target.exists() or not target.is_file():
        return False
    target.unlink()
    return True


def cleanup_empty_parents_until(path: Path, stop_dir: Path) -> None:
    stop = stop_dir.resolve()
    parent = path.resolve().parent
    while parent != stop:
        try:
            parent.rmdir()
        except OSError:
            break
        parent = parent.parent


def cleanup_root_related_data(root: str | Path) -> dict[str, Any]:
    normalized_root = str(Path(root).expanduser().resolve())
    removed: dict[str, int] = {
        "artifact_index_entries": 0,
        "artifact_files": 0,
        "image_index_files": 0,
        "thumbnail_files": 0,
        "delete_log_rows": 0,
        "recycle_files": 0,
        "root_summaries": 0,
        "root_workspace_dirs": 0,
    }

    cache_key = image_scan_cache_key(Path(normalized_root), SUPPORTED_EXTENSIONS, SKIP_SCAN_DIR_NAMES)
    root_index_dir = root_image_index_dir(normalized_root)
    thumbnail_relative_paths = {
        str(item.get("relative_path", "")).strip()
        for item in [
            *load_full_image_index_cache_service(root_index_dir, cache_key),
            *load_image_index_summary_metadata_service(root_index_dir, cache_key).get("items", []),
        ]
        if isinstance(item, dict) and str(item.get("relative_path", "")).strip()
    }
    for relative_path in thumbnail_relative_paths:
        thumbnail_path = thumbnail_path_for(Path(normalized_root), relative_path)
        if unlink_local_file(thumbnail_path):
            cleanup_empty_parents_until(thumbnail_path, root_thumbnail_dir(normalized_root))
            removed["thumbnail_files"] += 1

    for cache_path in (
        image_index_cache_path_service(root_index_dir, cache_key),
        image_index_summary_path_service(root_index_dir, cache_key),
        timeline_index_cache_path_service(root_index_dir, cache_key),
    ):
        if unlink_local_file(cache_path):
            removed["image_index_files"] += 1

    settings = load_settings()
    root_summaries = settings.get("root_summaries", {})
    if isinstance(root_summaries, dict) and normalized_root in root_summaries:
        root_summaries.pop(normalized_root, None)
        settings["root_summaries"] = root_summaries
        removed["root_summaries"] = 1
        save_settings(settings)

    for kind in ARTIFACT_INDEX_FILENAMES:
        mapping = load_artifact_index(kind)
        artifact_path_value = mapping.pop(normalized_root, "").strip()
        if artifact_path_value:
            removed["artifact_index_entries"] += 1
            if unlink_local_file(Path(artifact_path_value)):
                removed["artifact_files"] += 1
            save_artifact_index(kind, mapping)

    for artifact_path in (root_duplicates_path(normalized_root), root_hash_db_path(normalized_root)):
        if artifact_path.exists() and artifact_path.is_file():
            removed["artifact_files"] += 1

    rows = read_delete_log_rows_service(root_log_dir(normalized_root))
    if not rows:
        rows = [
            row
            for row in read_delete_log_rows_service(LOG_DIR)
            if str(row.get("root", "")).strip()
            and str(Path(str(row.get("root", ""))).expanduser().resolve()) == normalized_root
        ]
    remaining_rows = []
    for row in rows:
        row_root = str(row.get("root", "")).strip()
        if row_root and str(Path(row_root).expanduser().resolve()) == normalized_root:
            removed["delete_log_rows"] += 1
            deleted_to = str(row.get("deleted_to", "")).strip()
            if deleted_to:
                try:
                    deleted_path = resolve_deleted_file(deleted_to)
                    deleted_thumb_path = deleted_thumbnail_path_for(deleted_path)
                    if unlink_local_file(deleted_thumb_path):
                        cleanup_empty_parents_until(deleted_thumb_path, root_thumbnail_dir(normalized_root))
                        removed["thumbnail_files"] += 1
                    if deleted_path.exists() and deleted_path.is_file():
                        move_to_system_recycle_bin(deleted_path)
                        remove_empty_deleted_parent(deleted_path)
                        removed["recycle_files"] += 1
                except Exception as exc:
                    print(f"[cleanup] failed to clear recycle file for {normalized_root}: {exc}")
            continue
        remaining_rows.append(row)
    if removed["delete_log_rows"]:
        write_delete_log_rows_service(root_log_dir(normalized_root), remaining_rows)

    workspace = root_data_dir(normalized_root)
    if workspace.exists():
        shutil.rmtree(workspace)
        removed["root_workspace_dirs"] = 1

    clear_image_list_cache(Path(normalized_root))
    clear_duplicates_path_cache()
    return {"root": normalized_root, "removed": removed}
