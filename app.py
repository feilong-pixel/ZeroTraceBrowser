# SPDX-License-Identifier: MIT

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL.ExifTags import GPSTAGS
from ztb.security import (
    cors_origins_from_env,
    resolve_path,
    trusted_hosts_from_env,
)
from ztb.file_service import (
    build_deleted_path as build_deleted_path_for_service,
    clear_image_list_cache as clear_image_list_cache_service,
    copy_file_preserve_times as copy_file_preserve_times_service,
    deleted_thumbnail_path_for as deleted_thumbnail_path_for_service,
    exif_map_from_raw,
    get_images_for_timeline_group as get_images_for_timeline_group_service,
    get_timeline_index as get_timeline_index_service,
    image_index_cache_path as image_index_cache_path_service,
    image_index_summary_path as image_index_summary_path_service,
    image_file_response,
    image_scan_cache_key,
    iter_image_files as iter_image_files_service,
    list_images_cached_page as list_images_cached_page_service,
    list_images as list_images_service,
    list_images_page as list_images_page_service,
    load_full_image_index_cache as load_full_image_index_cache_service,
    load_image_index_summary_metadata as load_image_index_summary_metadata_service,
    move_file_preserve_times as move_file_preserve_times_service,
    preferred_exif_datetime_from_map,
    remove_empty_deleted_parent as remove_empty_deleted_parent_service,
    resolve_deleted_file as resolve_deleted_file_service,
    resolve_under_root as resolve_under_root_service,
    save_image_index_summary_metadata as save_image_index_summary_metadata_service,
    timeline_index_cache_path as timeline_index_cache_path_service,
    thumbnail_path_for as thumbnail_path_for_service,
)
from ztb.recycle_service import (
    append_log as append_log_service,
    archive_delete_log as archive_delete_log_service,
    list_recycle_items as list_recycle_items_service,
    read_delete_log_rows as read_delete_log_rows_service,
    write_delete_log_rows as write_delete_log_rows_service,
)
from ztb.settings_service import (
    SettingsStore,
    normalize_duplicate_detection,
    normalize_phash_threshold,
    normalize_task_mode,
)
from ztb.task_service import TaskRegistry
from ztb.routes.duplicates import create_duplicates_router
from ztb.routes.images import create_images_router
from ztb.routes.recycle import create_recycle_router
from ztb.routes.settings import create_settings_router
from ztb.routes.tasks import create_tasks_router
from ztb.schemas import OrganizerTaskRequest

try:
    from PIL import Image, ImageOps
except ImportError:  # pragma: no cover - startup makes the requirement explicit
    Image = None
    ImageOps = None

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
ROOT_DATA_DIR = DATA_DIR / "roots"
THUMBNAIL_DIR = BASE_DIR / "thumbnails"
IMAGE_INDEX_DIR = THUMBNAIL_DIR / "_indexes"
DELETED_DIR = BASE_DIR / "deleted"
LOG_DIR = BASE_DIR / "logs"
SETTINGS_PATH = BASE_DIR / "settings.json"
TASK_LOG_DIR = LOG_DIR / "tasks"
ORGANIZER_DIR = BASE_DIR / "MediaArchiveOrganizer"
ORGANIZER_MAIN = ORGANIZER_DIR / "main.py"

DEFAULT_IMAGE_ROOT = str(Path(os.getenv("ZTB_IMAGE_ROOT", BASE_DIR)).resolve())
DEFAULT_COPY_TARGET = os.getenv("ZTB_DEFAULT_COPY_TARGET", "")
THUMBNAIL_SIZE = (384, 384)
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff"}
EXCLUDED_SCAN_DIRS = {"static", "templates", "thumbnails", "deleted", "logs", "__pycache__", "venv"}
SUPPORTED_LANGUAGES = {"zh", "en", "ja"}
TASK_REGISTRY = TaskRegistry()
DUPLICATES_PATH_CACHE_TTL_SECONDS = 10.0
DUPLICATES_PATH_CACHE: tuple[float, Path | None] = (0.0, None)
DUPLICATES_ROOT_CACHE: tuple[float, str, Path | None] = (0.0, "", None)
ARTIFACT_INDEX_FILENAMES = {
    "duplicates": "duplicates_by_root.json",
    "hash_db": "hash_db_by_root.json",
}


def get_settings_store() -> SettingsStore:
    return SettingsStore(
        SETTINGS_PATH,
        DEFAULT_IMAGE_ROOT,
        DEFAULT_COPY_TARGET,
        SUPPORTED_LANGUAGES,
    )


def open_path_in_file_manager(path: Path) -> None:
    if sys.platform.startswith("win"):
        os.startfile(str(path))  # type: ignore[attr-defined]
        return

    command = ["open", str(path)] if sys.platform == "darwin" else ["xdg-open", str(path)]
    subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def open_image_in_system_editor(path: Path) -> None:
    if not sys.platform.startswith("win"):
        raise HTTPException(status_code=501, detail="Image editor opening is only supported on Windows")

    try:
        os.startfile(str(path), "edit")  # type: ignore[attr-defined]
    except OSError:
        subprocess.Popen(["mspaint.exe", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def move_to_system_recycle_bin(path: Path) -> None:
    target = path.expanduser().resolve()
    if not sys.platform.startswith("win"):
        raise HTTPException(status_code=501, detail="System recycle bin is only supported on Windows")

    import ctypes
    from ctypes import wintypes

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("wFunc", wintypes.UINT),
            ("pFrom", wintypes.LPCWSTR),
            ("pTo", wintypes.LPCWSTR),
            ("fFlags", wintypes.WORD),
            ("fAnyOperationsAborted", wintypes.BOOL),
            ("hNameMappings", wintypes.LPVOID),
            ("lpszProgressTitle", wintypes.LPCWSTR),
        ]

    FO_DELETE = 0x0003
    FOF_SILENT = 0x0004
    FOF_NOCONFIRMATION = 0x0010
    FOF_ALLOWUNDO = 0x0040
    FOF_NOERRORUI = 0x0400

    operation = SHFILEOPSTRUCTW()
    operation.hwnd = None
    operation.wFunc = FO_DELETE
    operation.pFrom = f"{target}\0\0"
    operation.pTo = None
    operation.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_NOERRORUI | FOF_SILENT

    result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(operation))
    if result != 0 or operation.fAnyOperationsAborted:
        raise HTTPException(status_code=500, detail=f"Failed to move file to system recycle bin: {result}")


def is_windows() -> bool:
    return sys.platform.startswith("win")


def default_settings() -> dict[str, Any]:
    return get_settings_store().default_settings()


def load_settings() -> dict[str, Any]:
    return get_settings_store().load()


def save_settings(settings: dict[str, Any]) -> None:
    get_settings_store().save(settings)


def get_active_image_root() -> Path:
    return get_settings_store().active_root()


def normalize_root_value(root: str | Path) -> str:
    return str(Path(root).expanduser().resolve())


def root_data_id(root: str | Path) -> str:
    normalized = normalize_root_value(root)
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def root_data_dir(root: str | Path) -> Path:
    return ROOT_DATA_DIR / root_data_id(root)


def root_log_dir(root: str | Path) -> Path:
    return root_data_dir(root) / "logs"


def root_task_log_dir(root: str | Path) -> Path:
    return root_data_dir(root) / "tasks"


def root_thumbnail_dir(root: str | Path) -> Path:
    return root_data_dir(root) / "thumbnails"


def root_image_index_dir(root: str | Path) -> Path:
    return root_data_dir(root) / "indexes"


def root_deleted_dir(root: str | Path) -> Path:
    return root_data_dir(root) / "deleted"


def root_workspace_metadata_path(root: str | Path) -> Path:
    return root_data_dir(root) / "root.json"


def root_hash_db_path(root: str | Path) -> Path:
    return root_data_dir(root) / "hash_db.json"


def root_duplicates_path(root: str | Path) -> Path:
    return root_data_dir(root) / "duplicates.json"


def ensure_root_workspace(root: str | Path) -> Path:
    normalized = normalize_root_value(root)
    workspace = root_data_dir(normalized)
    for path in (
        workspace,
        root_log_dir(normalized),
        root_task_log_dir(normalized),
        root_thumbnail_dir(normalized),
        root_image_index_dir(normalized),
        root_deleted_dir(normalized),
    ):
        path.mkdir(parents=True, exist_ok=True)
    metadata_path = root_workspace_metadata_path(normalized)
    if not metadata_path.exists():
        metadata_path.write_text(
            json.dumps(
                {
                    "root": normalized,
                    "root_id": root_data_id(normalized),
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
    cache_key = image_scan_cache_key(normalized, SUPPORTED_EXTENSIONS, EXCLUDED_SCAN_DIRS)
    scoped_dir = root_image_index_dir(normalized)
    for path in (
        image_index_cache_path_service(scoped_dir, cache_key),
        image_index_summary_path_service(scoped_dir, cache_key),
        timeline_index_cache_path_service(scoped_dir, cache_key),
    ):
        if path.exists():
            return scoped_dir
    return IMAGE_INDEX_DIR


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


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_directories()
    if Image is None or ImageOps is None:
        raise RuntimeError("Pillow is required. Install dependencies with: pip install -r requirements.txt")
    yield


app = FastAPI(title="ZeroTraceBrowser", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=trusted_hosts_from_env(),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins_from_env(),
    allow_methods=["*"],
    allow_headers=["*"],
)


class StaticNoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any) -> Response:
        response = await call_next(request)
        path = request.url.path
        if path.endswith((".html", ".js", ".css")) or path in {"/", "/index.html"}:
            response.headers["Cache-Control"] = "no-store, max-age=0"
            response.headers["Pragma"] = "no-cache"
        return response


app.add_middleware(StaticNoCacheMiddleware)

@app.get("/favicon.ico")
async def favicon():
    return FileResponse("favicon.ico")

def ensure_directories() -> None:
    for path in (STATIC_DIR, DATA_DIR, ROOT_DATA_DIR, THUMBNAIL_DIR, IMAGE_INDEX_DIR, DELETED_DIR, LOG_DIR, TASK_LOG_DIR):
        path.mkdir(parents=True, exist_ok=True)

    for log_path, headers in (
        (LOG_DIR / "delete_log.csv", ["timestamp", "root", "relative_path", "deleted_to", "action"]),
        (LOG_DIR / "copy_log.csv", ["timestamp", "root", "relative_path", "copied_to"]),
    ):
        if not log_path.exists():
            with log_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(headers)

    if not SETTINGS_PATH.exists():
        save_settings(default_settings())

    for root in load_settings().get("image_roots", []):
        if str(root).strip():
            workspace = ensure_root_workspace(root)
            ensure_log_file(workspace / "logs", "delete_log.csv")
            ensure_log_file(workspace / "logs", "copy_log.csv")


def resolve_under_root(root: Path, candidate: str) -> Path:
    return resolve_under_root_service(root, candidate)


def list_images(root: Path) -> list[dict[str, Any]]:
    return list_images_service(root, SUPPORTED_EXTENSIONS, EXCLUDED_SCAN_DIRS)


def list_images_page(root: Path, offset: int = 0, limit: int | None = None, include_exif: bool = True) -> dict[str, Any]:
    return list_images_page_service(root, SUPPORTED_EXTENSIONS, EXCLUDED_SCAN_DIRS, offset, limit, include_exif)


def list_images_cached_page(root: Path, offset: int = 0, limit: int = 48, refresh: bool = True, include_total: bool = False) -> dict[str, Any]:
    ensure_root_workspace(root)
    index_dir = root_image_index_dir(root) if refresh else image_index_dir_for_read(root)
    return list_images_cached_page_service(index_dir, root, SUPPORTED_EXTENSIONS, EXCLUDED_SCAN_DIRS, offset, limit, refresh, include_total)


def get_timeline_index(root: Path) -> dict[str, Any]:
    ensure_root_workspace(root)
    return get_timeline_index_service(image_index_dir_for_read(root), root, SUPPORTED_EXTENSIONS, EXCLUDED_SCAN_DIRS)


def get_images_for_timeline_group(root: Path, group_key: str) -> dict[str, Any]:
    ensure_root_workspace(root)
    return get_images_for_timeline_group_service(
        image_index_dir_for_read(root),
        root,
        SUPPORTED_EXTENSIONS,
        EXCLUDED_SCAN_DIRS,
        group_key,
    )


def clear_image_list_cache(root: Path | None = None) -> None:
    clear_image_list_cache_service(root)


def copy_file_preserve_times(src: Path, dst: Path) -> None:
    copy_file_preserve_times_service(src, dst)


def move_file_preserve_times(src: Path, dst: Path) -> None:
    move_file_preserve_times_service(src, dst)


def iter_image_files(root: Path) -> Iterable[Path]:
    return iter_image_files_service(root, SUPPORTED_EXTENSIONS, EXCLUDED_SCAN_DIRS)


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


def thumbnail_path_for(root: Path, relative_path: str) -> Path:
    ensure_root_workspace(root)
    return thumbnail_path_for_service(root_thumbnail_dir(root), root, relative_path)


def deleted_thumbnail_path_for(deleted_path: Path) -> Path:
    try:
        relative = deleted_path.resolve().relative_to(ROOT_DATA_DIR.resolve())
    except ValueError:
        return deleted_thumbnail_path_for_service(THUMBNAIL_DIR, deleted_path)
    root_id = relative.parts[0] if relative.parts else ""
    if root_id:
        return deleted_thumbnail_path_for_service(ROOT_DATA_DIR / root_id / "thumbnails", deleted_path)
    return deleted_thumbnail_path_for_service(THUMBNAIL_DIR, deleted_path)


def format_exif_value(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore").strip("\x00 ") or "-"
    if isinstance(value, tuple) and len(value) == 2 and all(isinstance(item, int) for item in value) and value[1] != 0:
        return f"{value[0]}/{value[1]}"
    if isinstance(value, tuple):
        return ", ".join(format_exif_value(item) for item in value)
    if hasattr(value, "numerator") and hasattr(value, "denominator"):
        denominator = getattr(value, "denominator", 1) or 1
        numerator = getattr(value, "numerator", value)
        if denominator == 1:
            return str(numerator)
        return f"{numerator}/{denominator}"
    return str(value)


def rational_to_float(value: Any) -> float | None:
    if value is None:
        return None
    if hasattr(value, "numerator") and hasattr(value, "denominator"):
        d = value.denominator or 1
        return float(value.numerator) / float(d)
    if isinstance(value, tuple) and len(value) == 2 and value[1]:
        return float(value[0]) / float(value[1])
    try:
        return float(value)
    except Exception:
        return None


def gps_dms_to_decimal(value: Any, ref: Any) -> float | None:
    if not value or len(value) < 3:
        return None

    degrees = rational_to_float(value[0])
    minutes = rational_to_float(value[1])
    seconds = rational_to_float(value[2])
    if degrees is None or minutes is None or seconds is None:
        return None

    decimal = degrees + minutes / 60 + seconds / 3600
    if str(ref).upper() in {"S", "W"}:
        decimal *= -1
    return decimal


def read_gps_summary(tags):
    gps_lat = tags.get("GPS GPSLatitude")
    gps_lat_ref = tags.get("GPS GPSLatitudeRef")
    gps_lon = tags.get("GPS GPSLongitude")
    gps_lon_ref = tags.get("GPS GPSLongitudeRef")
    gps_alt = tags.get("GPS GPSAltitude")
    gps_alt_ref = tags.get("GPS GPSAltitudeRef")

    result = {}

    lat = gps_dms_to_decimal(gps_lat.values if hasattr(gps_lat, "values") else None,
                             gps_lat_ref.values[0] if hasattr(gps_lat_ref, "values") else None)
    lon = gps_dms_to_decimal(gps_lon.values if hasattr(gps_lon, "values") else None,
                             gps_lon_ref.values[0] if hasattr(gps_lon_ref, "values") else None)

    if lat is not None and lon is not None:
        result["gps_coordinates"] = f"{lat:.6f}, {lon:.6f}"

    if gps_alt:
        alt = rational_to_float(gps_alt.values[0])
        if alt is not None:
            ref = rational_to_float(gps_alt_ref.values[0]) if gps_alt_ref else 0
            if ref == 1:
                alt *= -1
            result["gps_altitude"] = f"{alt:.1f} m"

    return result

import exifread
from pathlib import Path
from MediaArchiveOrganizer.core.date_classifier import get_target_date

def read_exif_tags(path: Path):
    with open(path, "rb") as f:
        return exifread.process_file(f, details=True, strict=False)

def read_exif_summary(image_path: Path) -> dict[str, str]:
    from PIL import Image
    with Image.open(image_path) as img:
        width, height = img.size

    tags = read_exif_tags(image_path)
    gps_summary = read_gps_summary(tags)
    captured_at = get_target_date(image_path)

    summary = {
        "width": str(width),
        "height": str(height),
        "datetime": captured_at.isoformat(sep=" ") if captured_at else "-",
        "camera": format_exif_value(
            f"{tags.get('Image Make', '')} {tags.get('Image Model', '')}".strip()
        ) or "-",
        "lens": format_exif_value(tags.get("EXIF LensModel") or "-"),
        "focal_length": format_exif_value(tags.get("EXIF FocalLength") or "-"),
        "aperture": format_exif_value(tags.get("EXIF FNumber") or "-"),
        "shutter": format_exif_value(tags.get("EXIF ExposureTime") or "-"),
        "iso": format_exif_value(
            tags.get("EXIF ISOSpeedRatings")
            or tags.get("EXIF PhotographicSensitivity")
            or "-"
        ),
    }

    summary.update(gps_summary)
    return summary


def validate_language(language: str) -> str:
    return get_settings_store().validate_language(language)


def serialize_settings(settings: dict[str, Any]) -> dict[str, Any]:
    return get_settings_store().serialize(settings)


def get_root_summary(root: str | Path) -> dict[str, Any]:
    normalized_root = Path(root).expanduser().resolve()
    cache_key = image_scan_cache_key(normalized_root, SUPPORTED_EXTENSIONS, EXCLUDED_SCAN_DIRS)
    metadata = load_image_index_summary_metadata_service(root_image_index_dir(normalized_root), cache_key)
    if not (
        isinstance(metadata.get("total"), int)
        or isinstance(metadata.get("duplicate_group_count"), int)
        or str(metadata.get("generated_at", "")).strip()
    ):
        metadata = load_image_index_summary_metadata_service(IMAGE_INDEX_DIR, cache_key)
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


def build_task_log_path(task_id: str, target_root: str | Path | None = None) -> Path:
    root = target_root or get_active_image_root()
    ensure_root_workspace(root)
    return root_task_log_dir(root) / task_id / "organizer.log"


def get_artifact_index_dir() -> Path:
    return TASK_LOG_DIR / "_indexes"


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


def iter_duplicates_result_paths() -> list[Path]:
    latest_dir_path = TASK_LOG_DIR / "latest" / "duplicates.json"
    candidates: list[Path] = []
    if latest_dir_path.exists():
        candidates.append(latest_dir_path)

    candidates.extend(
        path for path in ROOT_DATA_DIR.glob("*/duplicates.json")
        if path.exists()
    )

    candidates.extend(
        path for path in TASK_LOG_DIR.rglob("duplicates.json")
        if path != latest_dir_path
    )
    return sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)


def read_duplicates_destination_root(json_path: Path) -> str:
    try:
        with json_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return ""

    destination_root = payload.get("destination_root", "")
    return str(Path(destination_root).expanduser().resolve()) if destination_root else ""


def get_latest_duplicates_path(active_root: str | None = None) -> Path | None:
    global DUPLICATES_PATH_CACHE

    now = time.monotonic()
    cached_at, cached_path = DUPLICATES_PATH_CACHE
    if active_root is None and now - cached_at <= DUPLICATES_PATH_CACHE_TTL_SECONDS:
        if cached_path is None or cached_path.exists():
            return cached_path

    if active_root:
        root_scoped_path = root_duplicates_path(active_root)
        if root_scoped_path.exists():
            return root_scoped_path

        indexed_path = load_artifact_index("duplicates").get(str(Path(active_root).expanduser().resolve()), "").strip()
        if indexed_path:
            indexed_candidate = Path(indexed_path).expanduser().resolve()
            if indexed_candidate.exists():
                root_scoped_path.parent.mkdir(parents=True, exist_ok=True)
                if not root_scoped_path.exists():
                    shutil.copy2(indexed_candidate, root_scoped_path)
                return root_scoped_path

    candidates = iter_duplicates_result_paths()
    if active_root:
        normalized_active_root = str(Path(active_root).expanduser().resolve())
        for candidate in candidates:
            if read_duplicates_destination_root(candidate) == normalized_active_root:
                return candidate
        return None

    latest = candidates[0] if candidates else None
    if active_root is None:
        DUPLICATES_PATH_CACHE = (now, latest)
    return latest


def clear_duplicates_path_cache() -> None:
    global DUPLICATES_PATH_CACHE, DUPLICATES_ROOT_CACHE
    DUPLICATES_PATH_CACHE = (0.0, None)
    DUPLICATES_ROOT_CACHE = (0.0, "", None)


def get_duplicates_root_from_payload(payload: dict[str, Any]) -> Path | None:
    destination_root = payload.get("destination_root", "")
    if not destination_root:
        return None
    return Path(destination_root).expanduser().resolve()


def get_latest_duplicates_result_root() -> Path | None:
    global DUPLICATES_ROOT_CACHE

    settings = load_settings()
    active_root = str(Path(settings["active_root"]).resolve())
    now = time.monotonic()
    cached_at, cached_active_root, cached_root = DUPLICATES_ROOT_CACHE
    if cached_active_root == active_root and now - cached_at <= DUPLICATES_PATH_CACHE_TTL_SECONDS:
        if cached_root is None or cached_root.exists():
            return cached_root

    target = get_latest_duplicates_path(active_root)
    if target is None or not target.exists():
        DUPLICATES_ROOT_CACHE = (now, active_root, None)
        return None

    destination_root = read_duplicates_destination_root(target)
    root = Path(destination_root).expanduser().resolve() if destination_root else None
    DUPLICATES_ROOT_CACHE = (now, active_root, root)
    return root


def load_duplicates_payload(
    json_path: Path | None = None,
    offset: int = 0,
    limit: int | None = None,
    method: str | None = None,
) -> dict[str, Any]:
    settings = load_settings()
    active_root = str(Path(settings["active_root"]).resolve())
    target = json_path or get_latest_duplicates_path(active_root)
    offset = max(0, offset)
    limit = max(1, limit) if limit is not None else None
    method_filter = str(method or "").strip().lower()
    is_paged_request = offset != 0 or limit is not None or bool(method_filter)

    if target is None or not target.exists():
        result = {
            "available": False,
            "json_path": "",
            "generated_at": None,
            "destination_root": "",
            "active_root": active_root,
            "active_root_matches": False,
            "groups": [],
            "group_count": 0,
        }
        if is_paged_request:
            result.update(
                {
                    "method_counts": {"phash": 0, "strict": 0},
                    "page_offset": offset,
                    "page_limit": limit,
                    "method_filter": method_filter,
                    "has_more": False,
                }
            )
        return result

    with target.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    destination_root_path = get_duplicates_root_from_payload(payload)
    destination_root = str(destination_root_path) if destination_root_path else ""
    groups = []
    method_counts = {"phash": 0, "strict": 0}
    raw_groups = payload.get("groups", [])
    if not isinstance(raw_groups, list):
        raw_groups = []
    for group in raw_groups:
        group_method = str(group.get("reason", "-")).strip().lower()
        if group_method in method_counts:
            method_counts[group_method] += 1

    matched_group_count = 0
    has_more = False
    for group in raw_groups:
        group_method = str(group.get("reason", "-")).strip().lower()
        if method_filter and group_method != method_filter:
            continue

        items = []
        for item in group.get("items", []):
            if not isinstance(item, dict) or not item.get("path"):
                continue
            path_value = str(item["path"])
            exists = False
            if destination_root_path is not None:
                try:
                    candidate = resolve_under_root(destination_root_path, path_value)
                    exists = candidate.exists() and candidate.is_file()
                except HTTPException:
                    exists = False
            items.append(
                {
                    "role": str(item.get("role", "")),
                    "path": path_value,
                    "exists": exists,
                }
            )

        available_items = [item for item in items if item["exists"]]
        if len(available_items) < 2:
            continue

        if limit is not None and matched_group_count < offset:
            matched_group_count += 1
            continue

        if limit is not None and len(groups) >= limit:
            has_more = True
            break

        matched_group_count += 1
        preview_paths = [item["path"] for item in available_items]
        groups.append(
            {
                "group_id": str(group.get("group_id", "")),
                "reason": str(group.get("reason", "-")),
                "hash": str(group.get("hash", "")),
                "kept_path": str(group.get("kept_path", "")),
                "item_count": len(items),
                "available_count": len(available_items),
                "items": items,
                "preview_paths": preview_paths,
            }
        )

    if limit is None:
        group_count = len(groups)
    elif method_filter:
        group_count = method_counts.get(method_filter, matched_group_count + len(groups) + (1 if has_more else 0))
    else:
        raw_group_count = payload.get("group_count")
        group_count = raw_group_count if isinstance(raw_group_count, int) else len(raw_groups)

    return {
        "available": True,
        "json_path": str(target),
        "generated_at": payload.get("generated_at"),
        "destination_root": destination_root,
        "active_root": active_root,
        "active_root_matches": destination_root == active_root,
        "groups": groups,
        "group_count": group_count,
        "method_counts": method_counts,
        "page_offset": offset,
        "page_limit": limit,
        "method_filter": method_filter,
        "has_more": has_more,
    }


def load_duplicates_summary() -> dict[str, Any]:
    settings = load_settings()
    active_root = str(Path(settings["active_root"]).resolve())
    target = get_latest_duplicates_path(active_root)
    if target is None or not target.exists():
        return {"available": False, "group_count": 0}

    try:
        with target.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {"available": False, "group_count": 0}

    group_count = payload.get("group_count")
    if not isinstance(group_count, int):
        groups = payload.get("groups", [])
        group_count = len(groups) if isinstance(groups, list) else 0

    return {"available": True, "group_count": group_count}


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


def path_is_inside_data_roots(path: Path) -> bool:
    target = path.resolve()
    for root in (BASE_DIR, DATA_DIR, ROOT_DATA_DIR, LOG_DIR, THUMBNAIL_DIR, DELETED_DIR, ORGANIZER_DIR):
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

    cache_key = image_scan_cache_key(Path(normalized_root), SUPPORTED_EXTENSIONS, EXCLUDED_SCAN_DIRS)
    thumbnail_relative_paths = {
        str(item.get("relative_path", "")).strip()
        for item in [
            *load_full_image_index_cache_service(IMAGE_INDEX_DIR, cache_key),
            *load_image_index_summary_metadata_service(IMAGE_INDEX_DIR, cache_key).get("items", []),
        ]
        if isinstance(item, dict) and str(item.get("relative_path", "")).strip()
    }
    for relative_path in thumbnail_relative_paths:
        thumbnail_path = thumbnail_path_for(Path(normalized_root), relative_path)
        if unlink_local_file(thumbnail_path):
            cleanup_empty_parents_until(thumbnail_path, THUMBNAIL_DIR)
            removed["thumbnail_files"] += 1

    for cache_path in (
        image_index_cache_path_service(IMAGE_INDEX_DIR, cache_key),
        image_index_summary_path_service(IMAGE_INDEX_DIR, cache_key),
        timeline_index_cache_path_service(IMAGE_INDEX_DIR, cache_key),
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
                        cleanup_empty_parents_until(deleted_thumb_path, THUMBNAIL_DIR)
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
        EXCLUDED_SCAN_DIRS,
        image_count,
        duplicate_group_count,
        generated_at,
    )
    clear_image_list_cache(root)
    save_root_summary(str(root), image_count, duplicate_group_count, generated_at)


class RouteContext:
    def __getattr__(self, name: str) -> Any:
        return globals()[name]


def build_route_context() -> RouteContext:
    return RouteContext()


route_context = build_route_context()
app.include_router(create_settings_router(route_context))
app.include_router(create_tasks_router(route_context))
app.include_router(create_duplicates_router(route_context))
app.include_router(create_recycle_router(route_context))
app.include_router(create_images_router(route_context))
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
