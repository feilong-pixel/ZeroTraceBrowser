from .base import *
from .settings_context import save_root_summary, get_active_image_root, save_image_index_summary_metadata_service
from .root_workspace import ensure_root_workspace, root_task_log_dir, root_database_path, root_image_index_dir
from .artifact_context import get_hash_db_path
from .image_context import iter_image_files, clear_image_list_cache, list_images
from core.domain.root_context import RootContext
from core.services.image_index_service import (
    get_image_timestamp_for_sort,
    image_scan_cache_key,
    save_image_index_cache,
)
from core.services.timestamp_repair_service import repair_timestamps_from_exif
from core.storage.duplicates_repository import DuplicateResultRepository
from core.storage.database import init_root_database
from core.storage.hash_db_repository import HashDbRepository
from core.storage.task_repository import TaskRunRepository


def build_task_log_path(task_id: str, target_root: str | Path | None = None) -> Path:
    root = target_root or get_active_image_root()
    ensure_root_workspace(root)
    return root_task_log_dir(root) / task_id / "organizer.log"


def build_task_outputs(
    log_path: Path | None = None,
    target_root: str | Path | None = None,
    publish_duplicates: bool = False,
) -> dict[str, str]:
    log_str = str(log_path) if log_path else ""
    hash_db_path = str(get_hash_db_path(target_root))
    database_path = ""

    if target_root and publish_duplicates:
        ensure_root_workspace(target_root)
        database_path = str(root_database_path(target_root))
        init_root_database(database_path)
        hash_db_path = database_path
    elif target_root:
        ensure_root_workspace(target_root)
        hash_db_path = str(root_database_path(target_root))
        database_path = str(root_database_path(target_root))

    return {
        "log_path": log_str,
        "duplicate_report_path": str(log_path.with_name("duplicate_report.csv")) if log_path else "",
        "hash_db_path": hash_db_path,
        "database_path": database_path,
    }


def serialize_task(task: dict[str, Any]) -> dict[str, Any]:
    return TASK_REGISTRY.serialize(task)


def run_organizer_task(task_id: str, command: list[str], workdir: Path, env: dict[str, str] | None = None) -> None:
    TASK_REGISTRY.run_subprocess_task(task_id, command, workdir, env)
    task = TASK_REGISTRY.get(task_id)
    if task:
        persist_task_run_completion(task)
    if task and task.get("status") == "completed":
        summarize_task_root(task)


def run_timestamp_repair_task(task_id: str) -> None:
    task = TASK_REGISTRY.get(task_id)
    if not task:
        return

    params = task.get("params", {})
    if not isinstance(params, dict):
        params = {}
    outputs = task.get("outputs", {})
    if not isinstance(outputs, dict):
        outputs = {}

    output_lines: list[str] = []

    def append_output(line: str) -> None:
        output_lines.append(line)
        with TASK_REGISTRY.lock:
            task["output_lines"] = output_lines[-200:]

    try:
        root = Path(str(params.get("root", ""))).expanduser().resolve()
        log_path = Path(str(outputs.get("duplicate_report_path") or outputs.get("log_path")))
        threshold_days = int(params.get("threshold_days", 7) or 7)
        sync_modified_time = params.get("sync_modified_time", True) is not False
        rename_from_exif = params.get("rename_from_exif", False) is True
        include_videos = params.get("include_videos", False) is True

        append_output(f"EXIF timestamp repair started: {root}")
        append_output(f"Threshold days: {threshold_days}")
        append_output(f"Sync modified time: {sync_modified_time}")
        append_output(f"Rename date-formatted files: {rename_from_exif}")
        append_output(f"Include videos with embedded creation time: {include_videos}")

        def progress(stats: dict[str, int | str]) -> None:
            append_output(
                "Scanned {scanned} | fixed {modified_fixed} | renamed {renamed} | no EXIF {no_exif} | no media time {no_timestamp} | failed {failed}".format(
                    scanned=stats.get("scanned", 0),
                    modified_fixed=stats.get("modified_fixed", 0),
                    renamed=stats.get("renamed", 0),
                    no_exif=stats.get("no_exif", 0),
                    no_timestamp=stats.get("no_timestamp", 0),
                    failed=stats.get("failed", 0),
                )
            )

        stats = repair_timestamps_from_exif(
            root,
            supported_extensions=SUPPORTED_EXTENSIONS,
            excluded_scan_dirs=SKIP_SCAN_DIR_NAMES,
            threshold_days=threshold_days,
            sync_modified_time=sync_modified_time,
            rename_from_exif=rename_from_exif,
            include_videos=include_videos,
            log_path=log_path,
            progress_callback=progress,
        )
        append_output(
            "Done. Scanned {scanned} | modified fixed {modified_fixed} | renamed {renamed} | within threshold {within_threshold} | no EXIF {no_exif} | no media time {no_timestamp} | failed {failed}".format(
                **stats
            )
        )
        with TASK_REGISTRY.lock:
            task["status"] = "completed"
            task["return_code"] = 0
            task["finished_at"] = datetime.now().isoformat()
        clear_image_list_cache(root)
        summarize_task_root(task)
    except Exception as exc:
        append_output(f"Timestamp repair failed: {exc}")
        with TASK_REGISTRY.lock:
            task["status"] = "failed"
            task["return_code"] = 1
            task["finished_at"] = datetime.now().isoformat()
            task["error"] = str(exc)
        persist_task_run_completion(task)


def run_image_index_rebuild_task(task_id: str) -> None:
    task = TASK_REGISTRY.get(task_id)
    if not task:
        return

    params = task.get("params", {})
    if not isinstance(params, dict):
        params = {}

    output_lines: list[str] = []

    def append_output(line: str) -> None:
        output_lines.append(line)
        with TASK_REGISTRY.lock:
            task["output_lines"] = output_lines[-200:]

    try:
        root = Path(str(params.get("root", ""))).expanduser().resolve()
        append_output(f"Gallery index rebuild started: {root}")
        items = list_images(root)
        append_output(f"Scanned media files: {len(items)}")
        items.sort(
            key=lambda item: (
                (get_image_timestamp_for_sort(item) or 0) * -1,
                str(item.get("relative_path", "")).lower(),
            )
        )
        append_output("Sorted gallery index by timeline.")
        cache_key = image_scan_cache_key(root, SUPPORTED_EXTENSIONS, SKIP_SCAN_DIR_NAMES)
        save_image_index_cache(root_image_index_dir(root), cache_key, items)
        generated_at = datetime.now().isoformat()
        duplicate_summary = DuplicateResultRepository(RootContext.from_root(root, ROOT_DATA_DIR, ensure=True).database_path).load_summary()
        raw_group_count = duplicate_summary.get("group_count")
        duplicate_group_count = raw_group_count if isinstance(raw_group_count, int) else None
        save_root_summary(str(root), len(items), duplicate_group_count, generated_at)
        clear_image_list_cache(root)
        append_output(f"Timeline entries rebuilt from image index.")
        append_output(f"Done. Indexed media files: {len(items)}")
        with TASK_REGISTRY.lock:
            task["status"] = "completed"
            task["return_code"] = 0
            task["finished_at"] = generated_at
        persist_task_run_completion(task, scanned_count=len(items), saved_count=len(items), similar_group_count=duplicate_group_count)
    except Exception as exc:
        append_output(f"Gallery index rebuild failed: {exc}")
        with TASK_REGISTRY.lock:
            task["status"] = "failed"
            task["return_code"] = 1
            task["finished_at"] = datetime.now().isoformat()
            task["error"] = str(exc)
        persist_task_run_completion(task)


def has_running_task() -> bool:
    return TASK_REGISTRY.has_running_task()


def get_running_task() -> dict[str, Any] | None:
    return TASK_REGISTRY.get_running_task()


def summarize_task_root(task: dict[str, Any]) -> None:
    params = task.get("params", {})
    if not isinstance(params, dict):
        params = {}

    root_value = ""
    if task.get("task_type") == "organizer":
        root_value = str(params.get("dst", "")).strip()
    elif task.get("task_type") == "rebuild_hash_db":
        root_value = str(params.get("root", "")).strip()
    elif task.get("task_type") == "rebuild_image_index":
        root_value = str(params.get("root", "")).strip()
    elif task.get("task_type") == "timestamp_repair":
        root_value = str(params.get("root", "")).strip()

    if not root_value:
        return

    root = Path(root_value).expanduser().resolve()
    persist_task_outputs_to_database(task, root)
    image_count = sum(1 for _ in iter_image_files(root)) if root.exists() else 0
    duplicate_group_count: int | None = None
    if duplicate_group_count is None and task.get("task_type") in {"organizer", "rebuild_hash_db"}:
        summary = DuplicateResultRepository(RootContext.from_root(root, ROOT_DATA_DIR, ensure=True).database_path).load_summary()
        raw_group_count = summary.get("group_count")
        duplicate_group_count = raw_group_count if isinstance(raw_group_count, int) else None

    generated_at = datetime.now().isoformat()
    save_image_index_summary_metadata_service(
        root_image_index_dir(root),
        root,
        SUPPORTED_EXTENSIONS,
        SKIP_SCAN_DIR_NAMES,
        image_count,
        duplicate_group_count,
        generated_at,
    )
    clear_image_list_cache(root)
    save_root_summary(str(root), image_count, duplicate_group_count, generated_at)
    persist_task_run_completion(task, similar_group_count=duplicate_group_count)


def persist_task_run_started(task: dict[str, Any]) -> None:
    outputs = task.get("outputs", {})
    if not isinstance(outputs, dict):
        return
    database_path = str(outputs.get("database_path", "")).strip()
    if not database_path:
        return
    TaskRunRepository(database_path).save_task_started(task)


def persist_task_run_completion(
    task: dict[str, Any],
    similar_group_count: int | None = None,
    scanned_count: int | None = None,
    saved_count: int | None = None,
) -> None:
    outputs = task.get("outputs", {})
    if not isinstance(outputs, dict):
        return
    database_path = str(outputs.get("database_path", "")).strip()
    if not database_path:
        return
    TaskRunRepository(database_path).update_task_finished(
        task,
        scanned_count=scanned_count,
        saved_count=saved_count,
        similar_group_count=similar_group_count,
    )


def persist_task_outputs_to_database(task: dict[str, Any], root: Path) -> None:
    outputs = task.get("outputs", {})
    if not isinstance(outputs, dict):
        return

    database_path = RootContext.from_root(root, ROOT_DATA_DIR, ensure=True).database_path

    hash_db_path = str(outputs.get("hash_db_path", "")).strip()
    if hash_db_path:
        path = Path(hash_db_path)
        if path.suffix.lower() == ".sqlite3":
            return
        if path.exists() and path.is_file():
            try:
                with path.open("r", encoding="utf-8") as handle:
                    payload = json.load(handle)
                if isinstance(payload, dict):
                    HashDbRepository(database_path).save_hash_db(payload, source_path=path)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                pass
