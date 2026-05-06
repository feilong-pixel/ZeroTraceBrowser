# SPDX-License-Identifier: MIT

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from core.schemas import CopyRequest, FileActionRequest
from core.services.file_service import (
    clear_image_list_cache,
    copy_file_preserve_times,
    move_file_preserve_times,
    resolve_under_root,
)


def create_images_router(ctx: Any) -> APIRouter:
    router = APIRouter()

    @router.get("/api/images")
    def get_images(
        offset: int = 0,
        limit: int | None = None,
        include_exif: bool = True,
        async_scan: bool = False,
        refresh_scan: bool = True,
        include_total: bool = False,
    ) -> dict[str, Any]:
        started_at = time.perf_counter()
        root = ctx.get_active_image_root()
        if async_scan:
            page = ctx.list_images_cached_page(root, offset, limit or 48, refresh_scan, include_total)
        else:
            page = ctx.list_images_page(root, offset, limit, include_exif)
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        if elapsed_ms >= 100:
            print(
                f"[perf] /api/images {elapsed_ms:.1f}ms "
                f"offset={offset} limit={limit} include_exif={include_exif} async_scan={async_scan} "
                f"refresh_scan={refresh_scan} include_total={include_total} items={page.get('count')}"
            )
        return {"root": str(root), **page}

    @router.get("/api/timeline-index")
    def get_timeline_index() -> dict[str, Any]:
        root = ctx.get_active_image_root()
        return ctx.get_timeline_index(root)

    @router.get("/api/images/by-group")
    def get_images_by_group(group_key: str) -> dict[str, Any]:
        root = ctx.get_active_image_root()
        return ctx.get_images_for_timeline_group(root, group_key)

    @router.get("/api/image")
    def get_image(relative_path: str) -> FileResponse:
        root = ctx.get_active_image_root()
        image_path = resolve_under_root(root, relative_path)
        if not image_path.exists() or not image_path.is_file():
            raise HTTPException(status_code=404, detail="Image not found")
        return FileResponse(image_path)

    @router.post("/api/open-image-editor")
    def open_image_editor(payload: FileActionRequest) -> dict[str, str]:
        root = ctx.get_active_image_root()
        image_path = resolve_under_root(root, payload.relative_path)
        if not image_path.exists() or not image_path.is_file():
            raise HTTPException(status_code=404, detail="Image not found")
        ctx.open_image_in_system_editor(image_path)
        return {"status": "opened", "path": str(image_path)}

    @router.get("/api/exif")
    def get_exif(relative_path: str) -> dict[str, Any]:
        root = ctx.get_active_image_root()
        image_path = resolve_under_root(root, relative_path)
        if not image_path.exists() or not image_path.is_file():
            raise HTTPException(status_code=404, detail="Image not found")

        try:
            exif = ctx.read_exif_summary(image_path)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to read EXIF: {exc}") from exc

        return {
            "relative_path": relative_path,
            "exif": exif,
        }

    @router.get("/api/thumbnail")
    def get_thumbnail(relative_path: str) -> FileResponse:
        started_at = time.perf_counter()
        root = ctx.get_active_image_root()
        image_path = resolve_under_root(root, relative_path)
        if not image_path.exists() or not image_path.is_file():
            raise HTTPException(status_code=404, detail="Image not found")

        thumb_path = ctx.thumbnail_path_for(root, relative_path)
        response = ctx.image_file_response(image_path, thumb_path, ctx.THUMBNAIL_SIZE, ctx.Image, ctx.ImageOps)
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        if elapsed_ms >= 100:
            print(f"[perf] /api/thumbnail {elapsed_ms:.1f}ms path={relative_path}")
        return response

    @router.post("/api/delete")
    def delete_image(payload: FileActionRequest) -> dict[str, Any]:
        root = ctx.get_active_image_root()
        image_path = resolve_under_root(root, payload.relative_path)
        if not image_path.exists() or not image_path.is_file():
            clear_image_list_cache(root)
            stale_thumb = ctx.thumbnail_path_for(root, payload.relative_path)
            if stale_thumb.exists():
                stale_thumb.unlink()
            return {"status": "missing", "relative_path": payload.relative_path}

        deleted_path = ctx.build_deleted_path(root, payload.relative_path)
        deleted_path.parent.mkdir(parents=True, exist_ok=True)
        move_file_preserve_times(image_path, deleted_path)
        clear_image_list_cache(root)
        ctx.append_log(
            "delete_log.csv",
            datetime.now().isoformat(),
            str(root),
            payload.relative_path,
            str(deleted_path),
            "deleted",
        )

        stale_thumb = ctx.thumbnail_path_for(root, payload.relative_path)
        if stale_thumb.exists():
            stale_thumb.unlink()

        return {"status": "deleted", "deleted_to": str(deleted_path)}

    @router.post("/api/copy")
    def copy_image(payload: CopyRequest) -> dict[str, Any]:
        settings = ctx.load_settings()
        root = Path(settings["active_root"])
        image_path = resolve_under_root(root, payload.relative_path)
        if not image_path.exists() or not image_path.is_file():
            raise HTTPException(status_code=404, detail="Image not found")

        target_root_value = payload.target_dir.strip() or settings["default_copy_target"]
        if not target_root_value:
            raise HTTPException(status_code=400, detail="No copy target configured")

        target_root = Path(target_root_value).expanduser().resolve()
        target_root.mkdir(parents=True, exist_ok=True)
        target_path = target_root / image_path.name

        if target_path.exists():
            stem = target_path.stem
            suffix = target_path.suffix
            counter = 1
            while True:
                candidate = target_root / f"{stem}_{counter}{suffix}"
                if not candidate.exists():
                    target_path = candidate
                    break
                counter += 1

        copy_file_preserve_times(image_path, target_path)
        clear_image_list_cache(root)
        ctx.append_log("copy_log.csv", datetime.now().isoformat(), str(root), payload.relative_path, str(target_path))
        return {"status": "copied", "copied_to": str(target_path)}

    return router
