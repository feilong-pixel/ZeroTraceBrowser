# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import json
from io import BytesIO
from pathlib import Path

import app as ztb_app
import core.app.factory as app_factory
import core.context as context
import core.context_modules.iphone_context as iphone_context
import core.context_modules.phone_sync_context as phone_sync_context
import core.context_modules.route_facade as route_facade
from core.context_modules.root_workspace import root_database_path
from core.storage.hash_db_repository import HashDbRepository
from core.storage.mobile_repository import MobileRepository
from PIL import Image


def patch_mobile_context(monkeypatch, name, value) -> None:
    for module in (iphone_context, context, route_facade, app_factory, ztb_app):
        monkeypatch.setattr(module, name, value, raising=False)


def make_jpeg_bytes(color=(64, 96, 128)) -> bytes:
    buffer = BytesIO()
    image = Image.new("RGB", (16, 16), color)
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def start_sync_with_manifest(client, item_id="asset-1", filename="IMG_0001.JPG") -> tuple[str, str]:
    pair_response = client.post(
        "/api/mobile/pair",
        json={
            "pairing_token": "pair-token",
            "device_type": "iphone",
            "device_id": "phone-1",
            "device_name": "Phone 1",
            "device_model": "iPhone",
            "platform": "ios",
            "app_id": "zerotrace-mobile",
            "app_version": "0.1.0",
            "owner_label": "User",
            "capabilities": {"asset_id": True},
        },
    )
    assert pair_response.status_code == 200
    sync_token = pair_response.json()["sync_token"]
    start_response = client.post(
        "/api/mobile/sync/start",
        json={
            "device_type": "iphone",
            "device_id": "phone-1",
            "sync_token": sync_token,
            "last_client_cursor": "",
            "battery_state": "charging",
            "network_type": "wifi",
        },
    )
    assert start_response.status_code == 200
    session_id = start_response.json()["session_id"]
    manifest_response = client.post(
        "/api/mobile/sync/manifest",
        json={
            "session_id": session_id,
            "device_type": "iphone",
            "device_id": "phone-1",
            "items": [
                {
                    "item_id": item_id,
                    "filename": filename,
                    "media_type": "image",
                    "mime_type": "image/jpeg",
                    "size": 123,
                    "created_at": "2026-05-24T10:00:00+00:00",
                    "modified_at": "2026-05-24T10:01:00+00:00",
                }
            ],
        },
    )
    assert manifest_response.status_code == 200
    assert manifest_response.json()["upload"][0]["item_id"] == item_id
    return session_id, item_id


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


def test_mobile_pair_start_manifest_and_status_flow(api_client):
    client, _, image_root, _ = api_client

    pair_response = client.post(
        "/api/mobile/pair",
        json={
            "pairing_token": "pair-token",
            "device_type": "iphone",
            "device_id": "phone-1",
            "device_name": "Phone 1",
            "device_model": "iPhone",
            "platform": "ios",
            "app_id": "zerotrace-mobile",
            "app_version": "0.1.0",
            "owner_label": "User",
            "capabilities": {"asset_id": True},
        },
    )
    assert pair_response.status_code == 200
    pair_data = pair_response.json()
    assert pair_data["status"] == "paired"
    assert pair_data["device_id"] == "phone-1"
    assert pair_data["destination_root"] == str(image_root)
    assert pair_data["sync_token"]

    start_response = client.post(
        "/api/mobile/sync/start",
        json={
            "device_type": "iphone",
            "device_id": "phone-1",
            "sync_token": pair_data["sync_token"],
            "last_client_cursor": "",
            "battery_state": "charging",
            "network_type": "wifi",
        },
    )
    assert start_response.status_code == 200
    start_data = start_response.json()
    assert start_data["status"] == "ready"
    assert start_data["root_id"] == pair_data["root_id"]
    assert start_data["session_id"]

    manifest_response = client.post(
        "/api/mobile/sync/manifest",
        json={
            "session_id": start_data["session_id"],
            "device_type": "iphone",
            "device_id": "phone-1",
            "items": [
                {
                    "item_id": "asset-1",
                    "filename": "IMG_0001.JPG",
                    "media_type": "image",
                    "mime_type": "image/jpeg",
                    "size": 123,
                    "created_at": "2026-05-24T10:00:00+00:00",
                    "modified_at": "2026-05-24T10:01:00+00:00",
                }
            ],
        },
    )
    assert manifest_response.status_code == 200
    manifest_data = manifest_response.json()
    assert manifest_data["status"] == "accepted"
    assert manifest_data["upload"][0]["item_id"] == "asset-1"

    status_response = client.get("/api/mobile/sync/status")
    assert status_response.status_code == 200
    status_data = status_response.json()
    assert status_data["destination_root"] == str(image_root)
    assert status_data["paired_devices"] == 1
    assert status_data["connected_devices"][0]["device_id"] == "phone-1"


def test_mobile_sync_pairing_code_uses_lan_address(api_client, monkeypatch):
    client, _, image_root, _ = api_client
    monkeypatch.setattr(phone_sync_context, "_local_lan_ip", lambda: "192.168.1.25")

    response = client.get("/api/mobile/sync/pairing-code")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["base_url"] == "http://192.168.1.25:8000"
    assert data["destination_root"] == str(image_root)
    assert data["payload"]["base_url"] == data["base_url"]
    assert data["payload"]["pair_url"] == "http://192.168.1.25:8000/api/mobile/pair"
    assert data["payload"]["upload_url"] == "http://192.168.1.25:8000/api/mobile/sync/upload"
    assert data["pairing_token"].startswith("pair-")
    assert data["pairing_token"] in data["payload_text"]


def test_mobile_sync_start_rejects_unpaired_token(api_client):
    client, *_ = api_client

    response = client.post(
        "/api/mobile/sync/start",
        json={
            "device_type": "iphone",
            "device_id": "phone-1",
            "sync_token": "wrong-token",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid sync token"


def test_mobile_sync_upload_imports_bytes_into_active_root(api_client):
    client, _, image_root, _ = api_client
    session_id, item_id = start_sync_with_manifest(client)
    body = make_jpeg_bytes()

    response = client.post(
        "/api/mobile/sync/upload",
        headers={
            "X-ZTB-Mobile-Metadata": json.dumps(
                {
                    "session_id": session_id,
                    "device_type": "iphone",
                    "device_id": "phone-1",
                    "item_id": item_id,
                    "filename": "IMG_0001.JPG",
                    "created_at": "2026-05-24T10:00:00+00:00",
                    "modified_at": "2026-05-24T10:01:00+00:00",
                }
            )
        },
        content=body,
    )

    assert response.status_code == 200
    data = response.json()
    imported_path = Path(data["local_path"])
    assert data["status"] == "success"
    assert data["sha256"] == hashlib.sha256(body).hexdigest()
    assert imported_path.is_file()
    assert imported_path.resolve().is_relative_to(image_root.resolve())

    status_response = client.get("/api/mobile/sync/status")
    assert status_response.status_code == 200
    assert status_response.json()["summary"]["imported"] == 1


def test_mobile_sync_upload_skips_existing_strict_duplicate(api_client):
    client, _, image_root, _ = api_client
    session_id, item_id = start_sync_with_manifest(client, item_id="asset-duplicate", filename="DUP.JPG")
    body = make_jpeg_bytes(color=(220, 40, 80))
    existing = image_root / "existing.jpg"
    existing.write_bytes(body)
    strict_hash = hashlib.sha256(body).hexdigest()
    HashDbRepository(root_database_path(image_root)).add_hash_record("strict", strict_hash, existing)

    response = client.post(
        "/api/mobile/sync/upload",
        headers={
            "X-ZTB-Mobile-Metadata": json.dumps(
                {
                    "session_id": session_id,
                    "device_type": "iphone",
                    "device_id": "phone-1",
                    "item_id": item_id,
                    "filename": "DUP.JPG",
                }
            )
        },
        content=body,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "skipped_duplicate"
    assert data["sha256"] == strict_hash
    assert data["existing_local_path"] == str(existing)

    status_response = client.get("/api/mobile/sync/status")
    assert status_response.status_code == 200
    summary = status_response.json()["summary"]
    assert summary["imported"] == 0
    assert summary["skipped_duplicate"] == 1


def test_mobile_sync_upload_skips_deleted_local_marker(api_client):
    client, _, image_root, _ = api_client
    session_id, item_id = start_sync_with_manifest(client, item_id="asset-deleted", filename="DELETED.JPG")
    body = make_jpeg_bytes(color=(12, 180, 90))
    strict_hash = hashlib.sha256(body).hexdigest()
    MobileRepository(root_database_path(image_root)).mark_deleted_locally(
        strict_hash=strict_hash,
        relative_path="2026/05/24/DELETED.JPG",
        original_path=image_root / "2026" / "05" / "24" / "DELETED.JPG",
        deleted_to=image_root / ".ztb-deleted" / "DELETED.JPG",
        deleted_at="2026-05-24T10:02:00+00:00",
    )

    response = client.post(
        "/api/mobile/sync/upload",
        headers={
            "X-ZTB-Mobile-Metadata": json.dumps(
                {
                    "session_id": session_id,
                    "device_type": "iphone",
                    "device_id": "phone-1",
                    "item_id": item_id,
                    "filename": "DELETED.JPG",
                }
            )
        },
        content=body,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "skipped_deleted_locally"
    assert data["sha256"] == strict_hash
    assert data["deleted_relative_path"] == "2026/05/24/DELETED.JPG"

    status_response = client.get("/api/mobile/sync/status")
    assert status_response.status_code == 200
    summary = status_response.json()["summary"]
    assert summary["imported"] == 0
    assert summary["skipped_deleted_locally"] == 1
