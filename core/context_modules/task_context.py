from .base import *
from .settings_context import save_root_summary
from .root_workspace import ensure_root_workspace, root_task_log_dir, root_hash_db_path, root_duplicates_path, root_image_index_dir
from .artifact_context import get_hash_db_path
from .image_context import iter_image_files, clear_image_list_cache


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
    duplicate_json_path = ""
    hash_db_path = str(get_hash_db_path(target_root))

    if target_root and publish_duplicates:
        ensure_root_workspace(target_root)
        duplicate_json_path = str(root_duplicates_path(target_root))
        hash_db_path = str(root_hash_db_path(target_root))
    elif target_root:
        ensure_root_workspace(target_root)
        duplicate_json_path = str(log_path.with_name("duplicates.json")) if log_path else ""
        hash_db_path = str(root_hash_db_path(target_root))
    elif log_path:
        duplicate_json_path = str(log_path.with_name("duplicates.json"))

    return {
        "log_path": log_str,
        "duplicate_report_path": str(log_path.with_name("duplicate_report.csv")) if log_path else "",
        "duplicates_json_path": duplicate_json_path,
        "hash_db_path": hash_db_path,
    }


def serialize_task(task: dict[str, Any]) -> dict[str, Any]:
    return TASK_REGISTRY.serialize(task)


def run_organizer_task(task_id: str, command: list[str], workdir: Path, env: dict[str, str] | None = None) -> None:
    TASK_REGISTRY.run_subprocess_task(task_id, command, workdir, env)
    task = TASK_REGISTRY.get(task_id)
    if task and task.get("status") == "completed":
        summarize_task_root(task)


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

    if not root_value:
        return

    root = Path(root_value).expanduser().resolve()
    image_count = sum(1 for _ in iter_image_files(root)) if root.exists() else 0
    duplicate_group_count: int | None = None
    duplicates_json_path = str(task.get("outputs", {}).get("duplicates_json_path", "")).strip()
    if task.get("task_type") == "rebuild_hash_db" and duplicates_json_path:
        try:
            with Path(duplicates_json_path).open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            raw_group_count = payload.get("group_count")
            if isinstance(raw_group_count, int):
                duplicate_group_count = raw_group_count
            else:
                groups = payload.get("groups", [])
                duplicate_group_count = len(groups) if isinstance(groups, list) else None
        except (OSError, json.JSONDecodeError):
            duplicate_group_count = None

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
