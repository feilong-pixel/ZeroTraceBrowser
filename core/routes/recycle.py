# SPDX-License-Identifier: MIT

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from core.schemas import ClearDeletedRequest, ClearRecycleLogsRequest, PurgeDeletedRequest, RestoreDeletedRequest
from core.services.file_operations import move_file_preserve_times
from core.services.image_scan_service import clear_image_list_cache


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
        deleted_path = ctx.resolve_deleted_file(payload.deleted_to)
        if not deleted_path.exists() or not deleted_path.is_file():
            raise HTTPException(status_code=404, detail="Deleted file not found")

        log_row = next((row for row in reversed(ctx.read_delete_log_rows()) if row["deleted_to"] == str(deleted_path)), None)
        if not log_row or not log_row.get("root") or not log_row.get("relative_path"):
            raise HTTPException(status_code=400, detail="No restore target found in delete log")

        restore_root = Path(log_row["root"]).expanduser().resolve()
        restore_path = (restore_root / log_row["relative_path"]).resolve()
        try:
            restore_path.relative_to(restore_root)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Restore path escapes original root") from exc

        if restore_path.exists():
            raise HTTPException(status_code=409, detail="Original path already exists")

        restore_path.parent.mkdir(parents=True, exist_ok=True)
        move_file_preserve_times(deleted_path, restore_path)
        clear_image_list_cache(restore_root)
        thumb_path = ctx.deleted_thumbnail_path_for(deleted_path)
        if thumb_path.exists():
            thumb_path.unlink()
        ctx.remove_empty_deleted_parent(deleted_path)
        ctx.append_log(
            "delete_log.csv",
            datetime.now().isoformat(),
            str(restore_root),
            log_row["relative_path"],
            str(deleted_path),
            "restored",
        )
        return {
            "status": "restored",
            "restored_to": str(restore_path),
        }

    @router.post("/api/recycle-bin/purge")
    def purge_deleted_item(payload: PurgeDeletedRequest) -> dict[str, Any]:
        deleted_path = ctx.resolve_deleted_file(payload.deleted_to)
        if not deleted_path.exists() or not deleted_path.is_file():
            raise HTTPException(status_code=404, detail="Deleted file not found")

        log_row = next((row for row in reversed(ctx.read_delete_log_rows()) if row["deleted_to"] == str(deleted_path)), None)
        recycle_path, thumb_path = ctx.prepare_system_recycle_path(deleted_path, log_row)
        ctx.dispose_recycle_file(recycle_path)
        if thumb_path.exists():
            thumb_path.unlink()
        ctx.remove_empty_deleted_parent(recycle_path)
        ctx.append_log(
            "delete_log.csv",
            datetime.now().isoformat(),
            log_row["root"] if log_row else "",
            log_row["relative_path"] if log_row else "",
            str(deleted_path),
            "purged",
        )
        return {
            "status": "purged",
            "deleted_to": str(deleted_path),
        }

    @router.post("/api/recycle-bin/clear")
    def clear_recycle_bin(payload: ClearDeletedRequest) -> dict[str, Any]:
        if not payload.confirm:
            raise HTTPException(status_code=400, detail="Confirmation required")

        removed = 0
        for item in list(ctx.list_recycle_items()):
            file_path = ctx.resolve_deleted_file(item["deleted_to"])
            if not file_path.exists() or not file_path.is_file() or file_path.name == ".gitkeep":
                continue
            log_row = next((row for row in reversed(ctx.read_delete_log_rows()) if row["deleted_to"] == str(file_path)), None)
            recycle_path, thumb_path = ctx.prepare_system_recycle_path(file_path, log_row)
            ctx.dispose_recycle_file(recycle_path)
            if thumb_path.exists():
                thumb_path.unlink()
            ctx.remove_empty_deleted_parent(recycle_path)
            ctx.append_log(
                "delete_log.csv",
                datetime.now().isoformat(),
                log_row["root"] if log_row else "",
                log_row["relative_path"] if log_row else "",
                str(file_path),
                "purged",
            )
            removed += 1

        archive_result = ctx.archive_delete_log() if removed > 0 else {
            "archived": False,
            "archive_path": "",
            "archived_count": 0,
        }

        return {
            "status": "cleared",
            "removed_count": removed,
            "log_archive": archive_result,
        }

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
