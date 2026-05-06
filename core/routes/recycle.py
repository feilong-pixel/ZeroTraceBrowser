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


def create_recycle_router(ctx: Any) -> APIRouter:
    router = APIRouter()

    @router.get("/api/recycle-bin")
    def get_recycle_bin(
        offset: int = Query(0, ge=0),
        limit: int | None = Query(None, ge=1, le=200),
    ) -> dict[str, Any]:
        items = ctx.list_recycle_items()
        total = len(items)
        if limit is not None:
            items = items[offset:offset + limit]
        return {
            "items": items,
            "count": total,
            "page_offset": offset,
            "page_limit": limit,
            "has_more": limit is not None and offset + limit < total,
        }

    @router.get("/api/recycle-bin/logs")
    def get_recycle_logs() -> dict[str, Any]:
        rows = sorted(ctx.read_delete_log_rows(), key=lambda row: row["timestamp"], reverse=True)
        return {
            "items": rows,
            "count": len(rows),
        }

    @router.get("/api/recycle-bin/thumbnail")
    def get_recycle_thumbnail(deleted_to: str) -> FileResponse:
        deleted_path = ctx.resolve_deleted_file(deleted_to)
        if not deleted_path.exists() or not deleted_path.is_file():
            raise HTTPException(status_code=404, detail="Deleted file not found")

        thumb_path = ctx.deleted_thumbnail_path_for(deleted_path)
        return ctx.image_file_response(deleted_path, thumb_path, ctx.THUMBNAIL_SIZE, ctx.Image, ctx.ImageOps)

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

    @router.post("/api/recycle-bin/logs/archive")
    def archive_recycle_logs(payload: ClearDeletedRequest) -> dict[str, Any]:
        if not payload.confirm:
            raise HTTPException(status_code=400, detail="Confirmation required")

        result = ctx.archive_delete_log()
        return {
            "status": "archived_logs",
            **result,
        }

    @router.post("/api/recycle-bin/logs/clear")
    def clear_recycle_logs(payload: ClearRecycleLogsRequest) -> dict[str, Any]:
        if not payload.confirm:
            raise HTTPException(status_code=400, detail="Confirmation required")

        allowed_actions = {"restored", "purged"}
        actions = set(payload.actions)
        if not actions or not actions.issubset(allowed_actions):
            raise HTTPException(status_code=400, detail="Unsupported log cleanup action")

        rows = ctx.read_delete_log_rows()
        remaining_rows = [row for row in rows if row.get("action") not in actions]
        removed_count = len(rows) - len(remaining_rows)
        ctx.write_delete_log_rows(remaining_rows)
        return {
            "status": "cleared_logs",
            "removed_count": removed_count,
            "actions": sorted(actions),
        }

    @router.post("/api/recycle-bin/logs/purged/clear")
    def clear_purged_recycle_logs(payload: ClearDeletedRequest) -> dict[str, Any]:
        return clear_recycle_logs(ClearRecycleLogsRequest(confirm=payload.confirm, actions=["purged"]))

    return router
