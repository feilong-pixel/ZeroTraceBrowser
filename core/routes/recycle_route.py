# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from core.schemas import ClearDeletedRequest, ClearRecycleLogsRequest, PurgeDeletedRequest, RestoreDeletedRequest
from core.domain.root_proxy import build_root_proxy
from core.use_cases.restore_image import RestoreImageRequest, RestoreImageUseCase
from core.use_cases.purge_image import PurgeImageRequest, PurgeImageUseCase
from core.use_cases.clear_recycle import ClearRecycleRequest, ClearRecycleUseCase
from core.use_cases.clear_delete_logs import ClearDeleteLogsRequest, ClearDeleteLogsUseCase
from core.use_cases.archive_delete_logs import ArchiveDeleteLogsRequest, ArchiveDeleteLogsUseCase


def create_recycle_router(ctx: Any) -> APIRouter:
    router = APIRouter()

    # GET /api/recycle-bin
    @router.get("/api/recycle-bin")
    def get_recycle_bin(
        offset: int = Query(0, ge=0),
        limit: int | None = Query(None, ge=1, le=200),
    ) -> dict[str, Any]:
        payload = ctx.list_recycle_items_page(offset=offset, limit=limit)
        items = payload["items"]
        total = payload["count"]
        return {
            "items": items,
            "count": total,
            "page_offset": offset,
            "page_limit": limit,
            "has_more": limit is not None and offset + limit < total,
        }

    # GET /api/recycle-bin/logs
    @router.get("/api/recycle-bin/logs")
    def get_recycle_logs(
        offset: int = Query(0, ge=0),
        limit: int | None = Query(None, ge=1, le=200),
    ) -> dict[str, Any]:
        payload = ctx.read_delete_log_rows_page(offset=offset, limit=limit)
        rows = payload["items"]
        total = payload["count"]
        return {
            "items": rows,
            "count": total,
            "page_offset": offset,
            "page_limit": limit,
            "has_more": limit is not None and offset + limit < total,
        }

    # GET /api/recycle-bin/thumbnail
    @router.get("/api/recycle-bin/thumbnail")
    def get_recycle_thumbnail(deleted_to: str) -> FileResponse:
        deleted_path = ctx.resolve_deleted_file(deleted_to)
        if not deleted_path.exists() or not deleted_path.is_file():
            raise HTTPException(status_code=404, detail="Deleted file not found")

        thumb_path = ctx.deleted_thumbnail_path_for(deleted_path)
        return ctx.image_file_response(deleted_path, thumb_path, ctx.THUMBNAIL_SIZE, ctx.Image, ctx.ImageOps)

    # POST /api/recycle-bin/restore
    @router.post("/api/recycle-bin/restore")
    def restore_deleted_item(payload: RestoreDeletedRequest) -> dict[str, Any]:
        active_root = ctx.get_active_image_root()
        root_context = build_root_proxy(ctx, active_root)
        use_case = RestoreImageUseCase(
            root_context=root_context,
            thumbnails_dir=root_context.thumbnails_dir,
            resolve_fn=ctx.resolve_deleted_file,
        )
        req = RestoreImageRequest(deleted_to=payload.deleted_to)
        return use_case.execute(req)

    # POST /api/recycle-bin/purge
    @router.post("/api/recycle-bin/purge")
    def purge_deleted_item(payload: PurgeDeletedRequest) -> dict[str, Any]:
        active_root = ctx.get_active_image_root()
        root_context = build_root_proxy(ctx, active_root)
        use_case = PurgeImageUseCase(
            root_context=root_context,
            thumbnails_dir=root_context.thumbnails_dir,
            resolve_fn=ctx.resolve_deleted_file,
            dispose_fn=ctx.dispose_recycle_file,
        )
        req = PurgeImageRequest(deleted_to=payload.deleted_to)
        return use_case.execute(req)

    # POST /api/recycle-bin/clear
    @router.post("/api/recycle-bin/clear")
    def clear_recycle_bin(payload: ClearDeletedRequest) -> dict[str, Any]:
        active_root = ctx.get_active_image_root()
        root_context = build_root_proxy(ctx, active_root)
        use_case = ClearRecycleUseCase(
            root_context=root_context,
            thumbnails_dir=root_context.thumbnails_dir,
            resolve_fn=ctx.resolve_deleted_file,
            dispose_fn=ctx.dispose_recycle_file,
        )
        req = ClearRecycleRequest(confirm=payload.confirm)
        return use_case.execute(req)

    # POST /api/recycle-bin/logs/archive
    @router.post("/api/recycle-bin/logs/archive")
    def archive_recycle_logs(payload: ClearDeletedRequest) -> dict[str, Any]:
        logs_dir = ctx.root_log_dir(ctx.get_active_image_root())
        use_case = ArchiveDeleteLogsUseCase(logs_dir=logs_dir)
        req = ArchiveDeleteLogsRequest(confirm=payload.confirm)
        return use_case.execute(req)

    # POST /api/recycle-bin/logs/clear
    @router.post("/api/recycle-bin/logs/clear")
    def clear_recycle_logs(payload: ClearRecycleLogsRequest) -> dict[str, Any]:
        logs_dir = ctx.root_log_dir(ctx.get_active_image_root())
        use_case = ClearDeleteLogsUseCase(logs_dir=logs_dir)
        req = ClearDeleteLogsRequest(
            confirm=payload.confirm,
            actions=payload.actions,
        )
        return use_case.execute(req)

    # Deprecated endpoints for backward compatibility
    # These can be removed in a future major release
    # POST /api/recycle-bin/logs/purged/clear
    @router.post("/api/recycle-bin/logs/purged/clear")
    def clear_purged_recycle_logs(payload: ClearDeletedRequest) -> dict[str, Any]:
        return clear_recycle_logs(ClearRecycleLogsRequest(confirm=payload.confirm, actions=["purged"]))

    return router
