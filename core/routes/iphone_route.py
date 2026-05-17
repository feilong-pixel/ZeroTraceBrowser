# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from core.schemas import IphoneIndexRequest


def create_iphone_router(ctx: Any) -> APIRouter:
    router = APIRouter()

    # GET /api/iphone/devices
    @router.get("/api/iphone/devices")
    def detect_iphone_devices() -> dict[str, Any]:
        return ctx.detect_iphone_devices()

    # POST /api/iphone/index
    @router.post("/api/iphone/index")
    def build_iphone_photo_index(payload: IphoneIndexRequest) -> dict[str, Any]:
        return ctx.build_iphone_photo_index(payload.device_id)

    return router
