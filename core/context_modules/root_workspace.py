from .base import *
from .settings_context import default_settings, load_settings, save_settings


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


def migrate_legacy_image_indexes(root: str | Path) -> None:
    normalized = Path(root).expanduser().resolve()
    cache_key = image_scan_cache_key(normalized, SUPPORTED_EXTENSIONS, EXCLUDED_SCAN_DIRS)
    legacy_dir = IMAGE_INDEX_DIR
    scoped_dir = root_image_index_dir(normalized)
    if legacy_dir.resolve() == scoped_dir.resolve() or not legacy_dir.exists():
        return

    for legacy_path in (
        image_index_cache_path_service(legacy_dir, cache_key),
        image_index_summary_path_service(legacy_dir, cache_key),
        timeline_index_cache_path_service(legacy_dir, cache_key),
    ):
        if not legacy_path.exists() or not legacy_path.is_file():
            continue
        target_path = scoped_dir / legacy_path.name
        if target_path.exists():
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(legacy_path), str(target_path))

    for candidate in (legacy_dir, legacy_dir.parent):
        try:
            candidate.rmdir()
        except OSError:
            break


def cache_digest_from_index_path(path: Path) -> str:
    name = path.name
    for suffix in (".summary.json", ".timeline.json", ".json"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return path.stem


def read_index_summary_root(summary_path: Path) -> tuple[str, int | None, int | None, str]:
    try:
        with summary_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return "", None, None, ""

    root = str(payload.get("root", "")).strip()
    total = payload.get("total")
    duplicate_group_count = payload.get("duplicate_group_count")
    generated_at = str(payload.get("generated_at", "")).strip()
    return (
        normalize_root_value(root) if root else "",
        total if isinstance(total, int) else None,
        duplicate_group_count if isinstance(duplicate_group_count, int) else None,
        generated_at,
    )


def canonicalize_root_image_indexes(root: str | Path) -> None:
    normalized = normalize_root_value(root)
    index_dir = root_image_index_dir(normalized)
    if not index_dir.exists():
        return

    cache_key = image_scan_cache_key(Path(normalized), SUPPORTED_EXTENSIONS, EXCLUDED_SCAN_DIRS)
    current_paths = {
        "full": image_index_cache_path_service(index_dir, cache_key),
        "summary": image_index_summary_path_service(index_dir, cache_key),
        "timeline": timeline_index_cache_path_service(index_dir, cache_key),
    }
    current_digest = cache_digest_from_index_path(current_paths["summary"])

    candidates: list[tuple[tuple[int, int, str], str]] = []
    for summary_path in index_dir.glob("*.summary.json"):
        summary_root, total, duplicate_group_count, generated_at = read_index_summary_root(summary_path)
        if summary_root != normalized:
            continue
        digest = cache_digest_from_index_path(summary_path)
        score = (
            1 if isinstance(duplicate_group_count, int) else 0,
            total if isinstance(total, int) else -1,
            generated_at,
        )
        candidates.append((score, digest))

    if not candidates:
        return

    _, selected_digest = max(candidates, key=lambda item: item[0])
    selected_paths = {
        "full": index_dir / f"{selected_digest}.json",
        "summary": index_dir / f"{selected_digest}.summary.json",
        "timeline": index_dir / f"{selected_digest}.timeline.json",
    }

    for kind, selected_path in selected_paths.items():
        if not selected_path.exists():
            continue
        target_path = current_paths[kind]
        if selected_path.resolve() == target_path.resolve():
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(selected_path, target_path)

    for _, digest in candidates:
        if digest == current_digest:
            continue
        for path in (
            index_dir / f"{digest}.json",
            index_dir / f"{digest}.summary.json",
            index_dir / f"{digest}.timeline.json",
        ):
            if path.exists() and path.is_file():
                path.unlink()


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
    migrate_legacy_image_indexes(normalized)
    canonicalize_root_image_indexes(normalized)
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
