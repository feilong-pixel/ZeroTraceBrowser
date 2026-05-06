# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from fastapi.responses import FileResponse


def thumbnail_path_for(thumbnail_dir: Path, root: Path, relative_path: str) -> Path:
    digest = hashlib.sha1(f"{root}|{relative_path}".encode("utf-8")).hexdigest()
    return thumbnail_dir / digest[:2] / digest[2:4] / f"{digest}.jpg"


def deleted_thumbnail_path_for(thumbnail_dir: Path, deleted_path: Path) -> Path:
    digest = hashlib.sha1(f"deleted|{deleted_path}".encode("utf-8")).hexdigest()
    return thumbnail_dir / "deleted" / digest[:2] / f"deleted_{digest}.jpg"


def image_file_response(
    image_path: Path,
    thumbnail_path: Path,
    thumbnail_size: tuple[int, int],
    image_module: Any,
    image_ops_module: Any,
) -> FileResponse:
    should_refresh = not thumbnail_path.exists() or thumbnail_path.stat().st_mtime < image_path.stat().st_mtime
    if not should_refresh:
        try:
            with image_module.open(thumbnail_path) as existing_thumb:
                should_refresh = max(existing_thumb.size) < max(thumbnail_size)
        except Exception:
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
