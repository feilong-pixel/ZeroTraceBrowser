from .base import *
from .settings_context import load_settings
from .root_workspace import ensure_root_workspace, root_hash_db_path


def get_artifact_index_dir() -> Path:
    return ARTIFACT_INDEX_DIR


def get_artifact_index_path(kind: str) -> Path:
    filename = ARTIFACT_INDEX_FILENAMES[kind]
    return get_artifact_index_dir() / filename


def load_artifact_index(kind: str) -> dict[str, str]:
    index_path = get_artifact_index_path(kind)
    if not index_path.exists():
        return {}

    try:
        with index_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}

    return payload if isinstance(payload, dict) else {}


def save_artifact_index(kind: str, payload: dict[str, str]) -> None:
    index_path = get_artifact_index_path(kind)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with index_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def normalize_target_root(target_root: str | Path | None) -> str:
    if target_root is None:
        return ""
    return str(Path(target_root).expanduser().resolve())


def resolve_indexed_artifact_path(
    kind: str,
    target_root: str | Path | None,
    default_path: Path | None = None,
    create_mapping: bool = False,
) -> Path:
    normalized_root = normalize_target_root(target_root)
    if not normalized_root:
        if default_path is None:
            raise ValueError(f"{kind} artifact path requires a default path when target root is empty")
        return default_path.resolve()

    mapping = load_artifact_index(kind)
    existing = mapping.get(normalized_root, "").strip()
    if existing:
        existing_path = Path(existing).expanduser().resolve()
        if existing_path.exists() or create_mapping:
            return existing_path

    if default_path is None:
        if kind == "hash_db":
            return (ORGANIZER_DIR / "data" / "hash_db.json").resolve()
        raise ValueError(f"{kind} artifact path for {normalized_root} is not mapped")

    resolved_default = default_path.resolve()
    mapping[normalized_root] = str(resolved_default)
    save_artifact_index(kind, mapping)
    return resolved_default


def get_hash_db_path(target_root: str | Path | None = None) -> Path:
    configured = os.getenv("IMAGE_ORGANIZER_HASH_DB", "")
    if configured.strip():
        return Path(configured).expanduser().resolve()
    if target_root:
        ensure_root_workspace(target_root)
        target_path = root_hash_db_path(target_root)
        if not target_path.exists():
            legacy_path_value = load_artifact_index("hash_db").get(normalize_target_root(target_root), "").strip()
            if legacy_path_value:
                legacy_path = Path(legacy_path_value).expanduser().resolve()
                if legacy_path.exists() and legacy_path.is_file():
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(legacy_path, target_path)
        return target_path

    settings = load_settings()
    active_root = str(settings.get("active_root", "")).strip()
    if active_root:
        try:
            return resolve_indexed_artifact_path("hash_db", active_root)
        except ValueError:
            pass

    return (ORGANIZER_DIR / "data" / "hash_db.json").resolve()
