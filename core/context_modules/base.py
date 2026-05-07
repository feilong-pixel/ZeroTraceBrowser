import csv
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from fastapi import HTTPException

from core.app.security import resolve_path
from core.domain.root_context import RootContext, normalize_root_path, root_id_for
from core.services.file_operations import (
    copy_file_preserve_times as copy_file_preserve_times_service,
    move_file_preserve_times as move_file_preserve_times_service,
    resolve_under_root as resolve_under_root_service,
)
from core.services.image_scan_service import (
    clear_image_list_cache as clear_image_list_cache_service,
    get_images_for_timeline_group as get_images_for_timeline_group_service,
    get_timeline_index as get_timeline_index_service,
    iter_image_files as iter_image_files_service,
    list_images_cached_page as list_images_cached_page_service,
    list_images as list_images_service,
    list_images_page as list_images_page_service,
)
from core.services.image_index_service import (
    image_index_cache_path as image_index_cache_path_service,
    image_index_summary_path as image_index_summary_path_service,
    image_scan_cache_key,
    load_full_image_index_cache as load_full_image_index_cache_service,
    load_image_index_summary_metadata as load_image_index_summary_metadata_service,
    save_image_index_summary_metadata as save_image_index_summary_metadata_service,
    timeline_index_cache_path as timeline_index_cache_path_service,
)
from core.services.recycle_paths import (
    build_deleted_path as build_deleted_path_for_service,
    remove_empty_deleted_parent as remove_empty_deleted_parent_service,
)
from core.services.thumbnail_service import (
    deleted_thumbnail_path_for as deleted_thumbnail_path_for_service,
    image_file_response,
    thumbnail_path_for as thumbnail_path_for_service,
)
from core.services.recycle_service import (
    append_log as append_log_service,
    archive_delete_log as archive_delete_log_service,
    list_recycle_items as list_recycle_items_service,
    read_delete_log_rows as read_delete_log_rows_service,
    write_delete_log_rows as write_delete_log_rows_service,
)
from core.services.settings_service import SettingsStore
from core.schemas import OrganizerTaskRequest
from core.config.app_config import (
    DATA_DIR,
    STATIC_DIR,
    ROOT_DATA_DIR,
    THUMBNAIL_DIR,
    IMAGE_INDEX_DIR,
    DELETED_DIR,
    LOG_DIR,
    TASK_LOG_DIR,
    ARTIFACT_INDEX_DIR,
    SETTINGS_PATH,
    ORGANIZER_DIR,
    ORGANIZER_MAIN,
    DEFAULT_IMAGE_ROOT,
    DEFAULT_COPY_TARGET,
    THUMBNAIL_SIZE,
    IMAGE_EXTENSIONS,
    VIDEO_EXTENSIONS,
    FRONTEND_VIDEO_EXTENSIONS,
    SUPPORTED_EXTENSIONS,
    SKIP_SCAN_DIR_NAMES,
    EXCLUDED_SCAN_DIRS,
    SUPPORTED_LANGUAGES,
    TASK_REGISTRY,
    DUPLICATES_PATH_CACHE_TTL_SECONDS,
    DUPLICATES_PATH_CACHE,
    DUPLICATES_ROOT_CACHE,
    ARTIFACT_INDEX_FILENAMES,
)

try:
    from PIL import Image, ImageOps
except ImportError:
    Image = None
    ImageOps = None
