# SPDX-License-Identifier: MIT

from __future__ import annotations

from core.app.factory import create_app
from core.config.app_config import (
    BASE_DIR,
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
    EXCLUDED_SCAN_DIRS,
    SUPPORTED_LANGUAGES,
    TASK_REGISTRY,
    DUPLICATES_PATH_CACHE_TTL_SECONDS,
    DUPLICATES_ROOT_CACHE,
    ARTIFACT_INDEX_FILENAMES,
)
from core.context import *  # noqa: F403 - compatibility exports for tests and scripts

app = create_app()
