# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Any

from fastapi import APIRouter


def create_iphone_router(ctx: Any) -> APIRouter:
    router = APIRouter()

    # GET /api/iphone/devices
    @router.get("/api/iphone/devices")
    def detect_iphone_devices() -> dict[str, Any]:
        return ctx.detect_iphone_devices()

    return router
