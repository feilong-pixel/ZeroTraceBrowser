# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from core.schemas import IphoneDeleteRequest, IphoneIndexRequest


def create_iphone_router(ctx: Any) -> APIRouter:
    router = APIRouter()

    # GET /api/iphone/devices
    @router.get("/api/iphone/devices")
    def detect_iphone_devices() -> dict[str, Any]:
        return ctx.detect_mobile_devices("iphone")

    # GET /api/iphone/probe-item-properties
    @router.get("/api/iphone/probe-item-properties")
    def probe_iphone_item_properties(device_id: str) -> dict[str, Any]:
        return ctx.probe_mobile_item_properties("iphone", device_id)

    # POST /api/iphone/index
    @router.post("/api/iphone/index")
    def build_iphone_photo_index(payload: IphoneIndexRequest) -> dict[str, Any]:
        return ctx.build_mobile_photo_index("iphone", payload.device_id, limit=payload.limit, copy_all=payload.copy_all)

    # POST /api/iphone/delete
    @router.post("/api/iphone/delete")
    def delete_iphone_photo(payload: IphoneDeleteRequest) -> dict[str, Any]:
        return ctx.delete_mobile_photo("iphone", payload.device_id, payload.target)

    async def upload_iphone_photo_from_shortcut(request: Request) -> dict[str, Any]:
        return ctx.import_iphone_shortcut_upload(request.headers, await request.body())

    # POST /api/iphone/upload
    @router.post("/api/iphone/upload")
    async def upload_iphone_photo(request: Request) -> dict[str, Any]:
        return await upload_iphone_photo_from_shortcut(request)

    # POST /upload
    @router.post("/upload")
    async def upload_iphone_photo_alias(request: Request) -> dict[str, Any]:
        return await upload_iphone_photo_from_shortcut(request)

    return router
