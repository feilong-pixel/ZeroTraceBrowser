# SPDX-License-Identifier: MIT

from __future__ import annotations

from core.app_factory import create_app
from core.config import (
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
    SUPPORTED_EXTENSIONS,
    EXCLUDED_SCAN_DIRS,
    SUPPORTED_LANGUAGES,
    TASK_REGISTRY,
    DUPLICATES_PATH_CACHE_TTL_SECONDS,
    DUPLICATES_PATH_CACHE,
    DUPLICATES_ROOT_CACHE,
    ARTIFACT_INDEX_FILENAMES,
)
from core.context import *  # noqa: F403 - compatibility exports for tests and scripts

app = create_app()

class RouteContext:
    def __getattr__(self, name: str):
        return globals()[name]


def build_route_context() -> RouteContext:
    return RouteContext()
