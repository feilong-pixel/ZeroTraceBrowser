# SPDX-License-Identifier: MIT

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from core.schemas import CopyRequest, FileActionRequest
from core.domain.root_proxy import build_root_proxy
from core.services.file_operations import resolve_under_root
from core.storage.exif_repository import ExifRepository
from core.use_cases.copy_image import CopyImageRequest, CopyImageUseCase
from core.use_cases.delete_image import DeleteImageRequest, DeleteImageUseCase


def create_images_router(ctx: Any) -> APIRouter:
    router = APIRouter()

    # GET /api/images
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

    # GET /api/timeline-index
    @router.get("/api/timeline-index")
    def get_timeline_index() -> dict[str, Any]:
        root = ctx.get_active_image_root()
        return ctx.get_timeline_index(root)

    # GET /api/images/by-group
    @router.get("/api/images/by-group")
    def get_images_by_group(group_key: str) -> dict[str, Any]:
        root = ctx.get_active_image_root()
        return ctx.get_images_for_timeline_group(root, group_key)

    # GET /api/images/timeline-group
    @router.get("/api/images/timeline-group")
    def get_images_timeline_group(group_key: str, offset: int = 0, limit: int = 300) -> dict[str, Any]:
        root = ctx.get_active_image_root()
        return ctx.get_images_for_timeline_group_page(root, group_key, offset, limit)

    # GET /api/images/timeline-neighbor
    @router.get("/api/images/timeline-neighbor")
    def get_images_timeline_neighbor(group_key: str, direction: str) -> dict[str, Any]:
        root = ctx.get_active_image_root()
        return ctx.get_timeline_neighbor_group(root, group_key, direction)

    # GET /api/image
    @router.get("/api/image")
    def get_image(relative_path: str) -> FileResponse:
        root = ctx.get_active_image_root()
        image_path = resolve_under_root(root, relative_path)
        if not image_path.exists() or not image_path.is_file():
            raise HTTPException(status_code=404, detail="Image not found")
        return FileResponse(image_path)

    # POST /api/open-image-editor
    @router.post("/api/open-image-editor")
    def open_image_editor(payload: FileActionRequest) -> dict[str, str]:
        root = ctx.get_active_image_root()
        image_path = resolve_under_root(root, payload.relative_path)
        if not image_path.exists() or not image_path.is_file():
            raise HTTPException(status_code=404, detail="Image not found")
        ctx.open_image_in_system_editor(image_path)
        return {"status": "opened", "path": str(image_path)}

    # GET /api/exif
    @router.get("/api/exif")
    def get_exif(relative_path: str) -> dict[str, Any]:
        root = ctx.get_active_image_root()
        image_path = resolve_under_root(root, relative_path)
        if not image_path.exists() or not image_path.is_file():
            raise HTTPException(status_code=404, detail="Image not found")
        if image_path.suffix.lower() in ctx.VIDEO_EXTENSIONS:
            return {
                "relative_path": relative_path,
                "media_type": "video",
                "exif": {},
            }

        stat = image_path.stat()
        repository = ExifRepository(ctx.root_database_path(root))
        cached = repository.load_exif(
            relative_path,
            file_size=stat.st_size,
            mtime_ns=stat.st_mtime_ns,
        )
        if cached is not None:
            return {
                "relative_path": relative_path,
                "exif": cached,
                "from_cache": True,
            }

        try:
            exif = ctx.read_exif_summary(image_path)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to read EXIF: {exc}") from exc
        repository.save_exif(
            relative_path,
            exif,
            file_size=stat.st_size,
            mtime_ns=stat.st_mtime_ns,
        )

        return {
            "relative_path": relative_path,
            "exif": exif,
            "from_cache": False,
        }

    # GET /api/thumbnail
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

    # POST /api/delete
    @router.post("/api/delete")
    def delete_image(payload: FileActionRequest) -> dict[str, Any]:
        active_root = ctx.get_active_image_root()
        root_context = build_root_proxy(ctx, active_root)
        use_case = DeleteImageUseCase(
            root_context=root_context,
            thumbnails_dir=root_context.thumbnails_dir,
            thumbnail_size=ctx.THUMBNAIL_SIZE,
        )
        req = DeleteImageRequest(relative_path=payload.relative_path)
        return use_case.execute(req)

    # POST /api/copy
    @router.post("/api/copy")
    def copy_image(payload: CopyRequest) -> dict[str, Any]:
        settings = ctx.load_settings()
        active_root = Path(settings["active_root"])
        root_context = build_root_proxy(ctx, active_root)
        use_case = CopyImageUseCase(
            root_context=root_context,
            default_copy_target=settings.get("default_copy_target", ""),
        )
        req = CopyImageRequest(
            relative_path=payload.relative_path,
            target_dir=payload.target_dir,
        )
        return use_case.execute(req)
    return router

