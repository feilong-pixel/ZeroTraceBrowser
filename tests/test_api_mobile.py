# SPDX-License-Identifier: MIT

from __future__ import annotations

import app as ztb_app
import core.app.factory as app_factory
import core.context as context
import core.context_modules.iphone_context as iphone_context
import core.context_modules.route_facade as route_facade


def patch_mobile_context(monkeypatch, name, value) -> None:
    for module in (iphone_context, context, route_facade, app_factory, ztb_app):
        monkeypatch.setattr(module, name, value, raising=False)


def test_mobile_devices_api_returns_detected_iphone_devices(api_client, monkeypatch):
    client, *_ = api_client

    patch_mobile_context(
        monkeypatch,
        "detect_mobile_devices",
        lambda device_type="iphone": {
            "supported": True,
            "device_type": device_type,
            "devices": [
                {
                    "name": "Apple iPhone",
                    "device_id": "Apple iPhone",
                    "kind": "mtp",
                    "dcim_available": True,
                }
            ],
            "message": "ok",
        },
    )

    response = client.get("/api/mobile/devices", params={"device_type": "iphone"})

    assert response.status_code == 200
    data = response.json()
    assert data["device_type"] == "iphone"
    assert data["devices"][0]["name"] == "Apple iPhone"


def test_mobile_index_api_builds_selected_device_index(api_client, monkeypatch):
    client, *_ = api_client

    patch_mobile_context(
        monkeypatch,
        "build_mobile_photo_index",
        lambda device_type, device_id, limit=1, copy_all=False: {
            "status": "indexed",
            "device_type": device_type,
            "device_id": device_id,
            "device_name": "Apple iPhone",
            "album_count": 2,
            "indexed": 12,
            "limit": limit,
            "copy_all": copy_all,
            "indexed_at": "2026-05-22T00:00:00+00:00",
            "database_path": "workspace.sqlite3",
        },
    )

    response = client.post(
        "/api/mobile/index",
        json={"device_type": "iphone", "device_id": "Apple iPhone", "limit": 5, "copy_all": False},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["device_type"] == "iphone"
    assert data["device_id"] == "Apple iPhone"
    assert data["indexed"] == 12
    assert data["limit"] == 5


def test_mobile_delete_api_deletes_selected_photo(api_client, monkeypatch):
    client, *_ = api_client

    patch_mobile_context(
        monkeypatch,
        "delete_mobile_photo",
        lambda device_type, device_id, target: {
            "status": "deleted",
            "deleted": True,
            "device_type": device_type,
            "device_id": device_id,
            "album": "100APPLE",
            "filename": target.split("/")[-1],
            "deleted_at": "2026-05-22T00:00:00+00:00",
        },
    )

    response = client.post(
        "/api/mobile/delete",
        json={"device_type": "iphone", "device_id": "Apple iPhone", "target": "100APPLE/IMG_0001.JPG"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["device_type"] == "iphone"
    assert data["filename"] == "IMG_0001.JPG"
