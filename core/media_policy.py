# SPDX-License-Identifier: MIT

from __future__ import annotations

from MediaArchiveOrganizer.core.media_policy import (
    IMAGE_EXTENSIONS,
    SIDECAR_EXTENSIONS,
    STRICT_DUPLICATE_EXTENSION_ALIASES,
    SUPPORTED_MEDIA_EXTENSIONS,
    VIDEO_EXTENSIONS,
    is_sidecar_filename,
    is_supported_media_filename,
    media_suffix,
    phash_eligible,
    strict_extension_key,
    strict_extensions_compatible,
)

__all__ = [
    "IMAGE_EXTENSIONS",
    "SIDECAR_EXTENSIONS",
    "STRICT_DUPLICATE_EXTENSION_ALIASES",
    "SUPPORTED_MEDIA_EXTENSIONS",
    "VIDEO_EXTENSIONS",
    "is_sidecar_filename",
    "is_supported_media_filename",
    "media_suffix",
    "phash_eligible",
    "strict_extension_key",
    "strict_extensions_compatible",
]
