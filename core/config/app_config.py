from pathlib import Path
import os

from core.services.task_service import TaskRegistry

BASE_DIR = Path(__file__).resolve().parent.parent.parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
ROOT_DATA_DIR = DATA_DIR / "roots"

SETTINGS_PATH = BASE_DIR / "settings.json"
ORGANIZER_DIR = BASE_DIR / "MediaArchiveOrganizer"
ORGANIZER_MAIN = ORGANIZER_DIR / "main.py"

DEFAULT_IMAGE_ROOT = str(Path(os.getenv("ZTB_IMAGE_ROOT", BASE_DIR)).resolve())
DEFAULT_COPY_TARGET = os.getenv("ZTB_DEFAULT_COPY_TARGET", "")

THUMBNAIL_SIZE = (384, 384)
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v", ".avi", ".mkv"}
FRONTEND_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov"}
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
SKIP_SCAN_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    "tests_runtime",
    "venv",
    ".venv",
    "env",
    "ENV",
    "static",
    "data",
    "deleted",
    "thumbnails",
    "logs",
}
EXCLUDED_SCAN_DIRS = SKIP_SCAN_DIR_NAMES
SUPPORTED_LANGUAGES = {"zh", "en", "ja"}

# Legacy paths are read only for migration/compatibility. New runtime data must
# live under data/roots/<root_id>/.
THUMBNAIL_DIR = DATA_DIR / "thumbnails"
IMAGE_INDEX_DIR = THUMBNAIL_DIR / "_indexes"
DELETED_DIR = DATA_DIR / "deleted"
LOG_DIR = DATA_DIR / "logs"

# Legacy task-log root kept only for discovering older duplicates results.
TASK_LOG_DIR = LOG_DIR / "tasks"
ARTIFACT_INDEX_DIR = ROOT_DATA_DIR / "_indexes"

TASK_REGISTRY = TaskRegistry()
DUPLICATES_PATH_CACHE_TTL_SECONDS = 10.0
DUPLICATES_PATH_CACHE: tuple[float, Path | None] = (0.0, None)
DUPLICATES_ROOT_CACHE: tuple[float, str, Path | None] = (0.0, "", None)
ARTIFACT_INDEX_FILENAMES = {
    "duplicates": "duplicates_by_root.json",
    "hash_db": "hash_db_by_root.json",
}
