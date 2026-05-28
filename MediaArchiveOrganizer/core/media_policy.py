# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v", ".avi", ".mkv"}
SUPPORTED_MEDIA_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
SIDECAR_EXTENSIONS = {".aae", ".xmp"}
STRICT_DUPLICATE_EXTENSION_ALIASES = {
    ".jpeg": ".jpg",
}


def media_suffix(path_or_name: str | Path) -> str:
    return Path(str(path_or_name or "")).suffix.lower()


def is_sidecar_filename(path_or_name: str | Path) -> bool:
    return media_suffix(path_or_name) in SIDECAR_EXTENSIONS


def is_supported_media_filename(path_or_name: str | Path) -> bool:
    suffix = media_suffix(path_or_name)
    return suffix in SUPPORTED_MEDIA_EXTENSIONS and suffix not in SIDECAR_EXTENSIONS


def strict_extension_key(path_or_name: str | Path) -> str:
    suffix = media_suffix(path_or_name)
    return STRICT_DUPLICATE_EXTENSION_ALIASES.get(suffix, suffix)


def strict_extensions_compatible(left: str | Path, right: str | Path) -> bool:
    left_key = strict_extension_key(left)
    right_key = strict_extension_key(right)
    return bool(left_key) and left_key == right_key and left_key in SUPPORTED_MEDIA_EXTENSIONS


def phash_eligible(path_or_name: str | Path) -> bool:
    return media_suffix(path_or_name) in IMAGE_EXTENSIONS
