# SPDX-License-Identifier: MIT

from __future__ import annotations

import core.context_modules.iphone_context as iphone_context
import core.context as context
import core.context_modules.route_facade as route_facade
import core.app.factory as app_factory
import app as ztb_app
from core.context_modules.root_workspace import root_database_path
from core.storage.iphone_repository import IphoneRepository


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


def test_iphone_index_writes_import_records(api_client, monkeypatch):
    _, _, image_root, _ = api_client

    monkeypatch.setattr(iphone_context.platform, "system", lambda: "Windows")
    monkeypatch.setattr(iphone_context, "compute_phash", lambda path: "phash-demo")

    def fake_copy_iphone_media_for_index(device_id, temp_dir):
        temp_path = temp_dir / "IMG_0001.JPG"
        temp_path.write_text("same-content", encoding="utf-8")
        return [
            {
                "device_id": device_id,
                "device_name": "Apple iPhone",
                "album": "100APPLE",
                "filename": "IMG_0001.JPG",
                "temp_path": str(temp_path),
                "size": temp_path.stat().st_size,
                "modified_at": "2026-05-18 10:00:00",
            }
        ]

    monkeypatch.setattr(iphone_context, "_copy_iphone_media_for_index", fake_copy_iphone_media_for_index)

    result = iphone_context.build_iphone_photo_index("Apple iPhone")

    assert result["status"] == "indexed"
    database_path = root_database_path(image_root)
    records = IphoneRepository(database_path).list_import_records("Apple iPhone")

    assert records[0]["device_id"] == "Apple iPhone"
    assert records[0]["album"] == "100APPLE"
    assert records[0]["filename"] == "IMG_0001.JPG"
    assert records[0]["iphone_ref"] == "mtp://Apple iPhone/DCIM/100APPLE/IMG_0001.JPG"
    assert records[0]["strict_hash"] == "cae1b3faaa5e4ac7c3306bd164b36dcfdff98294b8024c9c949639b4c480bf6b"
    assert records[0]["phash"] == "phash-demo"
    assert records[0]["save_state"] == "iphone_only"
    assert records[0]["import_status"] == "indexed"
    assert records[0]["local_path"] == ""
    assert records[0]["existing_local_path"] == ""
    assert records[0]["deleted_from_iphone_at"] == ""
