# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from core.schemas import (
    MobileDeleteRequest,
    MobileIndexRequest,
    MobilePairRequest,
    MobileSyncManifestRequest,
    MobileSyncStartRequest,
)


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

    @router.get("/api/mobile/sync/pairing-code")
    def get_mobile_sync_pairing_code(request: Request) -> dict[str, Any]:
        return ctx.get_mobile_sync_pairing_code(str(request.url))

    @router.post("/api/mobile/pair")
    def pair_mobile_device(payload: MobilePairRequest) -> dict[str, Any]:
        return ctx.pair_mobile_device(payload)

    @router.post("/api/mobile/sync/start")
    def start_mobile_sync(payload: MobileSyncStartRequest) -> dict[str, Any]:
        return ctx.start_mobile_sync(payload)

    @router.post("/api/mobile/sync/manifest")
    def save_mobile_sync_manifest(payload: MobileSyncManifestRequest) -> dict[str, Any]:
        return ctx.save_mobile_sync_manifest(payload)

    @router.post("/api/mobile/sync/upload")
    async def upload_mobile_sync_item(request: Request) -> dict[str, Any]:
        metadata_header = request.headers.get("X-ZTB-Mobile-Metadata", "")
        if not metadata_header:
            raise HTTPException(status_code=400, detail="X-ZTB-Mobile-Metadata is required")
        try:
            metadata = json.loads(metadata_header)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="Invalid X-ZTB-Mobile-Metadata JSON") from exc
        if not isinstance(metadata, dict):
            raise HTTPException(status_code=400, detail="X-ZTB-Mobile-Metadata must be an object")
        return ctx.upload_mobile_sync_item(metadata, await request.body())

    @router.get("/api/mobile/sync/status")
    def get_mobile_sync_status() -> dict[str, Any]:
        return ctx.get_mobile_sync_status()

    return router
