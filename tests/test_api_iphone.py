# SPDX-License-Identifier: MIT

from __future__ import annotations

import core.context_modules.iphone_context as iphone_context
import core.context as context
import core.context_modules.route_facade as route_facade
import core.app.factory as app_factory
import app as ztb_app


def patch_iphone_context(monkeypatch, name, value) -> None:
    for module in (iphone_context, context, route_facade, app_factory, ztb_app):
        monkeypatch.setattr(module, name, value, raising=False)


def test_iphone_devices_api_returns_detected_devices(api_client, monkeypatch):
    client, *_ = api_client

    patch_iphone_context(
        monkeypatch,
        "detect_iphone_devices",
        lambda: {
            "supported": True,
            "devices": [
                {
                    "name": "Apple iPhone",
                    "device_id": "Apple iPhone",
                    "kind": "mtp",
                    "dcim_available": True,
                    "album_count_sample": 1,
                    "media_count_sample": 5,
                }
            ],
            "message": "ok",
        },
    )

    response = client.get("/api/iphone/devices")

    assert response.status_code == 200
    data = response.json()
    assert data["supported"] is True
    assert data["devices"][0]["name"] == "Apple iPhone"
    assert data["devices"][0]["dcim_available"] is True


def test_iphone_index_api_builds_selected_device_index(api_client, monkeypatch):
    client, *_ = api_client

    patch_iphone_context(
        monkeypatch,
        "build_iphone_photo_index",
        lambda device_id: {
            "status": "indexed",
            "device_id": device_id,
            "device_name": "Apple iPhone",
            "album_count": 2,
            "indexed": 12,
            "indexed_at": "2026-05-13T00:00:00+00:00",
            "database_path": "workspace.sqlite3",
        },
    )

    response = client.post("/api/iphone/index", json={"device_id": "Apple iPhone"})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "indexed"
    assert data["device_id"] == "Apple iPhone"
    assert data["indexed"] == 12
