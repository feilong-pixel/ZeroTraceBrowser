# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from core.services.file_operations import resolve_under_root


def create_duplicates_router(ctx: Any) -> APIRouter:
    router = APIRouter()

    # GET /api/duplicates
    @router.get("/api/duplicates")
    def get_duplicates(
        offset: int = Query(0, ge=0),
        limit: int | None = Query(None, ge=1, le=200),
        method: str | None = Query(None),
    ) -> dict[str, Any]:
        return ctx.load_duplicates_payload(offset=offset, limit=limit, method=method)

    # POST /api/duplicates/open-result-root
    @router.post("/api/duplicates/open-result-root")
    def open_duplicates_result_root() -> dict[str, str]:
        payload = ctx.load_duplicates_payload()
        destination_root = payload.get("destination_root", "")
        if not destination_root:
            raise HTTPException(status_code=404, detail="Result root not found")

        root = Path(destination_root).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            raise HTTPException(status_code=404, detail="Result root not found")

        ctx.open_path_in_file_manager(root)
        return {"status": "opened", "path": str(root)}

    # GET /api/duplicates/thumbnail
    @router.get("/api/duplicates/thumbnail")
    def get_duplicates_thumbnail(relative_path: str) -> FileResponse:
        root = ctx.get_latest_duplicates_result_root()
        if root is None:
            raise HTTPException(status_code=404, detail="Duplicate result root not found")

        image_path = resolve_under_root(root, relative_path)
        if not image_path.exists() or not image_path.is_file():
            raise HTTPException(status_code=404, detail="Image not found")

        thumb_path = ctx.thumbnail_path_for(root, relative_path)
        return ctx.image_file_response(image_path, thumb_path, ctx.THUMBNAIL_SIZE, ctx.Image, ctx.ImageOps)

    return router
