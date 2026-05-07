# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from fastapi.responses import FileResponse

from core.config.app_config import VIDEO_EXTENSIONS

logger = logging.getLogger(__name__)


def thumbnail_path_for(thumbnail_dir: Path, root: Path, relative_path: str) -> Path:
    digest = hashlib.sha1(f"{root}|{relative_path}".encode("utf-8")).hexdigest()
    return thumbnail_dir / digest[:2] / digest[2:4] / f"{digest}.jpg"


def deleted_thumbnail_path_for(thumbnail_dir: Path, deleted_path: Path) -> Path:
    digest = hashlib.sha1(f"deleted|{deleted_path}".encode("utf-8")).hexdigest()
    return thumbnail_dir / "deleted" / digest[:2] / f"deleted_{digest}.jpg"


def is_video_file(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTENSIONS


def video_placeholder_response(
    video_path: Path,
    thumbnail_path: Path,
    thumbnail_size: tuple[int, int],
    image_module: Any,
) -> FileResponse:
    should_refresh = not thumbnail_path.exists() or thumbnail_path.stat().st_mtime < video_path.stat().st_mtime
    if should_refresh:
        if image_module is None:
            raise HTTPException(status_code=415, detail="Unsupported image format")
        try:
            from PIL import ImageDraw
        except ImportError as exc:
            raise HTTPException(status_code=415, detail="Unsupported image format") from exc

        thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
        width, height = thumbnail_size
        canvas = image_module.new("RGB", thumbnail_size, (28, 31, 38))
        draw = ImageDraw.Draw(canvas)
        triangle_width = max(72, width // 4)
        triangle_height = max(96, height // 3)
        center_x = width // 2
        center_y = height // 2
        draw.rounded_rectangle((16, 16, width - 16, height - 16), radius=18, outline=(88, 100, 120), width=2)
        draw.polygon(
            [
                (center_x - triangle_width // 3, center_y - triangle_height // 2),
                (center_x - triangle_width // 3, center_y + triangle_height // 2),
                (center_x + triangle_width // 2, center_y),
            ],
            fill=(226, 232, 240),
        )
        canvas.save(thumbnail_path, format="JPEG", quality=90, optimize=True)
    return FileResponse(thumbnail_path)


def image_file_response(
    image_path: Path,
    thumbnail_path: Path,
    thumbnail_size: tuple[int, int],
    image_module: Any,
    image_ops_module: Any,
) -> FileResponse:
    if is_video_file(image_path):
        return video_placeholder_response(image_path, thumbnail_path, thumbnail_size, image_module)

    should_refresh = not thumbnail_path.exists() or thumbnail_path.stat().st_mtime < image_path.stat().st_mtime
    if not should_refresh:
        try:
            with image_module.open(thumbnail_path) as existing_thumb:
                should_refresh = max(existing_thumb.size) < max(thumbnail_size)
        except Exception as exc:
            logger.debug("Failed to inspect cached thumbnail %s: %s", thumbnail_path, exc)
            should_refresh = True

    if should_refresh:
        thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with image_module.open(image_path) as img:
                if hasattr(img, "draft"):
                    img.draft("RGB", thumbnail_size)
                thumb = image_ops_module.exif_transpose(img)
                thumb.thumbnail(thumbnail_size)
                if thumb.mode != "RGB":
                    thumb = thumb.convert("RGB")
                thumb.save(thumbnail_path, format="JPEG", quality=92, optimize=True)
        except (getattr(image_module, "UnidentifiedImageError", OSError), OSError) as exc:
            raise HTTPException(status_code=415, detail="Unsupported image format") from exc

    return FileResponse(thumbnail_path)
