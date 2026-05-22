# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from core.schemas import MobileDeleteRequest, MobileIndexRequest


def create_mobile_router(ctx: Any) -> APIRouter:
    router = APIRouter()

    @router.get("/api/mobile/devices")
    def detect_mobile_devices(device_type: str = "iphone") -> dict[str, Any]:
        return ctx.detect_mobile_devices(device_type)

    @router.get("/api/mobile/probe-item-properties")
    def probe_mobile_item_properties(device_id: str, device_type: str = "iphone") -> dict[str, Any]:
        return ctx.probe_mobile_item_properties(device_type, device_id)

    @router.post("/api/mobile/index")
    def build_mobile_photo_index(payload: MobileIndexRequest) -> dict[str, Any]:
        return ctx.build_mobile_photo_index(
            payload.device_type,
            payload.device_id,
            limit=payload.limit,
            copy_all=payload.copy_all,
        )

    @router.post("/api/mobile/delete")
    def delete_mobile_photo(payload: MobileDeleteRequest) -> dict[str, Any]:
        return ctx.delete_mobile_photo(payload.device_type, payload.device_id, payload.target)

    return router
