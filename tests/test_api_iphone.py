# SPDX-License-Identifier: MIT

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

import pytest

import core.context_modules.iphone_context as iphone_context
import core.context as context
import core.context_modules.route_facade as route_facade
import core.app.factory as app_factory
import app as ztb_app
from core.context_modules.root_workspace import root_database_path
from core.config.app_config import SKIP_SCAN_DIR_NAMES, SUPPORTED_EXTENSIONS
from core.services.image_index_service import digest_for_cache_key, image_scan_cache_key
from core.storage.hash_db_repository import HashDbRepository
from core.storage.image_index_repository import ImageIndexRepository
from core.storage.mobile_repository import MobileRepository


def patch_iphone_context(monkeypatch, name, value) -> None:
    for module in (iphone_context, context, route_facade, app_factory, ztb_app):
        monkeypatch.setattr(module, name, value, raising=False)


def test_iphone_devices_api_returns_detected_devices(api_client, monkeypatch):
    client, *_ = api_client

    patch_iphone_context(
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


def test_iphone_probe_item_properties_api_returns_first_item_properties(api_client, monkeypatch):
    client, *_ = api_client

    patch_iphone_context(
        monkeypatch,
        "probe_mobile_item_properties",
        lambda device_type, device_id: {
            "supported": True,
            "device_type": device_type,
            "device_id": device_id,
            "album": "100APPLE",
            "filename": "IMG_0001.JPG",
            "properties": {"System.ItemPathDisplay": "Apple iPhone\\DCIM\\100APPLE\\IMG_0001.JPG"},
            "details": [{"index": 0, "label": "Name", "value": "IMG_0001.JPG"}],
        },
    )

    response = client.get("/api/iphone/probe-item-properties", params={"device_id": "Apple iPhone"})

    assert response.status_code == 200
    data = response.json()
    assert data["device_id"] == "Apple iPhone"
    assert data["album"] == "100APPLE"
    assert data["properties"]["System.ItemPathDisplay"].endswith("IMG_0001.JPG")


def test_iphone_index_api_builds_selected_device_index(api_client, monkeypatch):
    client, *_ = api_client

    patch_iphone_context(
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
            "indexed_at": "2026-05-13T00:00:00+00:00",
            "database_path": "workspace.sqlite3",
        },
    )

    response = client.post("/api/iphone/index", json={"device_id": "Apple iPhone", "limit": 5, "copy_all": False})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "indexed"
    assert data["device_id"] == "Apple iPhone"
    assert data["indexed"] == 12
    assert data["limit"] == 5
    assert data["copy_all"] is False


def test_iphone_delete_api_deletes_selected_photo(api_client, monkeypatch):
    client, *_ = api_client

    patch_iphone_context(
        monkeypatch,
        "delete_mobile_photo",
        lambda device_type, device_id, target: {
            "status": "deleted",
            "deleted": True,
            "device_type": device_type,
            "device_id": device_id,
            "album": "100APPLE",
            "filename": target.split("/")[-1],
            "deleted_at": "2026-05-21T00:00:00+00:00",
        },
    )

    response = client.post(
        "/api/iphone/delete",
        json={"device_id": "Apple iPhone", "target": "100APPLE/IMG_0001.JPG"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "deleted"
    assert data["filename"] == "IMG_0001.JPG"


def test_iphone_shortcut_upload_imports_header_image(api_client, monkeypatch):
    client, _, image_root, _ = api_client

    monkeypatch.setattr(iphone_context, "compute_phash", lambda path: "phash-upload")

    response = client.post(
        "/api/iphone/upload",
        content=b"shortcut-image",
        headers={
            "X-Original-Filename": "IMG_0948.jpeg",
            "X-Original-CreateDate": "2026/05/17 10:26:47 JST",
            "X-Original-UpdateDate": "2026/05/17 11:42:31 JST",
            "X-Original-FileSize": "2.5 MB",
            "X-Original-FileType": "jpeg",
            "X-ZTB-Uploader": "User Name",
            "X-Original-DeviceName": "User Name s iPhone 13",
            "X-Original-DeviceModel": "iPhone",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["device_id"] == "User Name::User Name s iPhone 13"
    assert data["uploader"] == "User Name"
    imported = Path(data["local_path"])
    assert imported.is_relative_to(image_root)
    assert imported.parts[-4:] == ("2026", "05", "17", "IMG_0948.jpeg")
    assert imported.read_bytes() == b"shortcut-image"
    assert data["declared_size"] == int(2.5 * 1024 * 1024)

    records = MobileRepository(root_database_path(image_root)).list_import_records(
        "iphone",
        "User Name::User Name s iPhone 13",
    )
    assert records[0]["album"] == "ShortcutUpload"
    assert records[0]["filename"] == "IMG_0948.jpeg"
    assert records[0]["local_path"] == str(imported)
    assert records[0]["import_status"] == "imported"


def test_iphone_shortcut_upload_separates_people_with_same_device_name(api_client, monkeypatch):
    client, _, image_root, _ = api_client
    monkeypatch.setattr(iphone_context, "compute_phash", lambda path: f"phash-{Path(path).read_text(encoding='utf-8')}")

    for owner, content, filename in (
        ("User Name", b"person-a", "IMG_1001.jpeg"),
        ("Family Member", b"person-b", "IMG_1002.jpeg"),
    ):
        response = client.post(
            "/api/iphone/upload",
            content=content,
            headers={
                "X-Original-Filename": filename,
                "X-ZTB-Uploader": owner,
                "X-Original-DeviceName": "iPhone 13",
            },
        )
        assert response.status_code == 200

    repository = MobileRepository(root_database_path(image_root))
    owner_a_records = repository.list_import_records("iphone", "User Name::iPhone 13")
    owner_b_records = repository.list_import_records("iphone", "Family Member::iPhone 13")

    assert [record["filename"] for record in owner_a_records] == ["IMG_1001.jpeg"]
    assert [record["filename"] for record in owner_b_records] == ["IMG_1002.jpeg"]


def test_iphone_shortcut_upload_accepts_explicit_device_id(api_client, monkeypatch):
    client, _, image_root, _ = api_client
    monkeypatch.setattr(iphone_context, "compute_phash", lambda path: "phash-explicit")

    response = client.post(
        "/api/iphone/upload",
        content=b"explicit-device",
        headers={
            "X-Original-Filename": "IMG_2001.jpeg",
            "X-ZTB-Uploader": "User Name",
            "X-ZTB-DeviceId": "user-iphone-13-main",
            "X-Original-DeviceName": "iPhone",
        },
    )

    assert response.status_code == 200
    assert response.json()["device_id"] == "user-iphone-13-main"
    records = MobileRepository(root_database_path(image_root)).list_import_records("iphone", "user-iphone-13-main")
    assert records[0]["filename"] == "IMG_2001.jpeg"


def test_iphone_shortcut_upload_rejects_path_filename(api_client):
    client, *_ = api_client

    response = client.post(
        "/api/iphone/upload",
        content=b"bad",
        headers={"X-Original-Filename": "../IMG_0948.jpeg"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid upload filename"


def test_iphone_shortcut_upload_alias_skips_existing_duplicate(api_client, monkeypatch):
    client, _, image_root, _ = api_client
    existing = image_root / "existing.jpeg"
    existing.write_bytes(b"shortcut-image")
    strict_hash = "6ab7af8533feae986ea1d5358b7f8504fe2b129f138cdc7c5ae293233e24bcb0"
    HashDbRepository(root_database_path(image_root)).save_hash_db(
        {"phash": {}, "strict": {strict_hash: [str(existing)]}},
        source_path=root_database_path(image_root),
    )
    monkeypatch.setattr(iphone_context, "compute_phash", lambda path: "phash-upload")

    response = client.post(
        "/upload",
        content=b"shortcut-image",
        headers={
            "X-Original-Filename": "IMG_0948.jpeg",
            "X-Original-DeviceName": "User Name s iPhone 13",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "skipped_duplicate"
    assert data["existing_local_path"] == str(existing.resolve())


def test_iphone_shortcut_upload_skips_photo_deleted_by_system(api_client, monkeypatch):
    client, _, image_root, _ = api_client
    original = image_root / "album" / "deleted.jpeg"
    original.parent.mkdir(parents=True)
    original.write_bytes(b"deleted-by-system")
    monkeypatch.setattr(iphone_context, "compute_phash", lambda path: "phash-deleted")

    delete_response = client.post("/api/delete", json={"relative_path": "album/deleted.jpeg"})
    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "deleted"

    response = client.post(
        "/api/iphone/upload",
        content=b"deleted-by-system",
        headers={
            "X-Original-Filename": "IMG_3001.jpeg",
            "X-ZTB-DeviceId": "user-iphone-13-main",
            "X-Original-DeviceName": "iPhone",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "skipped_deleted_locally"
    assert data["imported"] is False
    assert data["deleted_relative_path"] == "album/deleted.jpeg"
    assert not (image_root / "IMG_3001.jpeg").exists()

    records = MobileRepository(root_database_path(image_root)).list_import_records("iphone", "user-iphone-13-main")
    assert records[0]["filename"] == "IMG_3001.jpeg"
    assert records[0]["import_status"] == "skipped_deleted_locally"


def test_iphone_index_writes_import_records(api_client, monkeypatch):
    _, _, image_root, _ = api_client

    monkeypatch.setattr(iphone_context.platform, "system", lambda: "Windows")
    monkeypatch.setattr(iphone_context, "compute_phash", lambda path: "phash-demo")

    def fake_copy_iphone_media_for_index(device_id, temp_dir, cutoff_modified_at="", skip_refs=None, limit=1):
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

    assert result["status"] == "imported"
    assert result["imported"] == 1
    assert result["imported_items"][0]["target"] == "100APPLE/IMG_0001.JPG"
    database_path = root_database_path(image_root)
    records = MobileRepository(database_path).list_import_records("iphone", "Apple iPhone")

    assert records[0]["device_type"] == "iphone"
    assert records[0]["device_id"] == "Apple iPhone"
    assert records[0]["album"] == "100APPLE"
    assert records[0]["filename"] == "IMG_0001.JPG"
    assert records[0]["mobile_ref"] == "mobile://iphone/Apple iPhone/DCIM/100APPLE/IMG_0001.JPG"
    assert records[0]["strict_hash"] == "cae1b3faaa5e4ac7c3306bd164b36dcfdff98294b8024c9c949639b4c480bf6b"
    assert records[0]["phash"] == "phash-demo"
    assert records[0]["save_state"] == "both"
    assert records[0]["import_status"] == "imported"
    assert records[0]["local_path"]
    assert records[0]["local_path"].endswith("IMG_0001.JPG")
    assert records[0]["existing_local_path"] == ""
    assert records[0]["deleted_from_device_at"] == ""
    assert HashDbRepository(database_path).load_hash_db()["strict"][
        "cae1b3faaa5e4ac7c3306bd164b36dcfdff98294b8024c9c949639b4c480bf6b"
    ] == [records[0]["local_path"]]


def test_iphone_index_uses_requested_limit_and_imports_batch(api_client, monkeypatch):
    _, _, image_root, _ = api_client

    monkeypatch.setattr(iphone_context.platform, "system", lambda: "Windows")
    monkeypatch.setattr(iphone_context, "compute_phash", lambda path: f"phash-{Path(path).name}")
    captured_limits = []

    def fake_copy_iphone_media_for_index(device_id, temp_dir, cutoff_modified_at="", skip_refs=None, limit=1):
        captured_limits.append(limit)
        records = []
        for index in range(limit):
            filename = f"IMG_{index + 1:04d}.JPG"
            temp_path = temp_dir / filename
            temp_path.write_text(f"content-{index}", encoding="utf-8")
            records.append(
                {
                    "device_id": device_id,
                    "device_name": "Apple iPhone",
                    "album": "100APPLE",
                    "filename": filename,
                    "temp_path": str(temp_path),
                    "size": temp_path.stat().st_size,
                    "modified_at": "2026-05-18 10:00:00",
                }
            )
        return records

    monkeypatch.setattr(iphone_context, "_copy_iphone_media_for_index", fake_copy_iphone_media_for_index)

    result = iphone_context.build_iphone_photo_index("Apple iPhone", limit=3)

    assert captured_limits == [3]
    assert result["status"] == "imported"
    assert result["indexed"] == 3
    assert result["imported"] == 3
    assert result["limit"] == 3
    records = MobileRepository(root_database_path(image_root)).list_import_records("iphone", "Apple iPhone")
    assert [record["filename"] for record in records] == ["IMG_0001.JPG", "IMG_0002.JPG", "IMG_0003.JPG"]


def test_iphone_index_copy_all_passes_unlimited_copy_limit(api_client, monkeypatch):
    monkeypatch.setattr(iphone_context.platform, "system", lambda: "Windows")
    monkeypatch.setattr(iphone_context, "compute_phash", lambda path: "phash-demo")
    captured_limits = []

    def fake_copy_iphone_media_for_index(device_id, temp_dir, cutoff_modified_at="", skip_refs=None, limit=1):
        captured_limits.append(limit)
        return []

    monkeypatch.setattr(iphone_context, "_copy_iphone_media_for_index", fake_copy_iphone_media_for_index)

    result = iphone_context.build_iphone_photo_index("Apple iPhone", limit=7, copy_all=True)

    assert captured_limits == [0]
    assert result["copy_all"] is True
    assert result["limit"] == 7


def test_iphone_index_returns_failed_status_when_mtp_copy_fails(api_client, monkeypatch):
    monkeypatch.setattr(iphone_context.platform, "system", lambda: "Windows")

    def fake_copy_iphone_media_for_index(device_id, temp_dir, cutoff_modified_at="", skip_refs=None, limit=1):
        raise RuntimeError("DCIM folder not found.")

    monkeypatch.setattr(iphone_context, "_copy_iphone_media_for_index", fake_copy_iphone_media_for_index)

    result = iphone_context.build_iphone_photo_index("Apple iPhone", limit=5)

    assert result["status"] == "failed"
    assert result["indexed"] == 0
    assert result["imported"] == 0
    assert result["message"] == "DCIM folder not found."


def test_iphone_index_returns_failed_status_when_mtp_copy_times_out(api_client, monkeypatch):
    monkeypatch.setattr(iphone_context.platform, "system", lambda: "Windows")

    def fake_copy_iphone_media_for_index(device_id, temp_dir, cutoff_modified_at="", skip_refs=None, limit=1):
        raise RuntimeError("iPhone index copy timed out after 600 seconds. Unlock the device and try again.")

    monkeypatch.setattr(iphone_context, "_copy_iphone_media_for_index", fake_copy_iphone_media_for_index)

    result = iphone_context.build_iphone_photo_index("Apple iPhone", limit=5)

    assert result["status"] == "failed"
    assert result["indexed"] == 0
    assert result["imported"] == 0
    assert "timed out after 600 seconds" in result["message"]


def test_iphone_index_copy_timeout_is_clean_runtime_error(tmp_path, monkeypatch):
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=kwargs.get("args", "powershell"), timeout=600)

    monkeypatch.setattr(iphone_context.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError) as exc_info:
        iphone_context._copy_iphone_media_for_index("Apple iPhone", tmp_path, limit=5)

    assert "timed out after 600 seconds" in str(exc_info.value)


def test_iphone_index_copy_error_message_is_cleaned():
    message = iphone_context._clean_powershell_error(
        """
�����ꏊ C:\\Users\\User\\AppData\\Local\\Temp\\ztb_iphone_index\\staging\\iphone_index_copy.ps1:103 ����
:24
+ if ($null -eq $dcim) { throw "DCIM folder not found." }
+                        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : OperationStopped: (DCIM folder not found.:String) [], RuntimeException
    + FullyQualifiedErrorId : DCIM folder not found.
""",
        "",
        "iPhone index copy failed",
    )

    assert message == "DCIM folder not found."


def test_iphone_file_time_restore_uses_created_and_modified(monkeypatch, tmp_path):
    target = tmp_path / "photo.jpg"
    target.write_text("content", encoding="utf-8")
    applied = []

    monkeypatch.setattr(iphone_context.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        iphone_context,
        "read_windows_file_times",
        lambda path: ((1, 0), (2, 0), (3, 0)),
    )
    monkeypatch.setattr(
        iphone_context,
        "apply_windows_file_times",
        lambda path, times: applied.append(times),
    )

    iphone_context._apply_iphone_file_times(
        target,
        created_at="2026-05-21 20:48:02",
        modified_at="2026-05-21 20:49:09",
    )

    assert applied
    created, accessed, written = applied[0]
    assert created != written
    assert accessed == (2, 0)


def test_upload_file_time_uses_exif_when_modified_time_drift_is_large(monkeypatch, tmp_path):
    target = tmp_path / "photo.jpg"
    target.write_bytes(b"content")
    exif_time = datetime(2020, 1, 2, 3, 4, 5)
    created_at = datetime(2026, 5, 21, 20, 48, 2)
    modified_at = datetime(2026, 5, 21, 20, 49, 9)

    monkeypatch.setattr(iphone_context, "get_exif_datetime", lambda path: exif_time)
    monkeypatch.setattr(iphone_context, "_apply_iphone_file_times", lambda *args, **kwargs: None)

    adjusted_created, adjusted_modified = iphone_context._apply_portable_file_times(
        target,
        created_at,
        modified_at,
    )

    assert adjusted_created == created_at
    assert adjusted_modified == exif_time
    assert int(target.stat().st_mtime) == int(exif_time.timestamp())


def test_upload_file_time_keeps_modified_time_when_close_to_exif(monkeypatch, tmp_path):
    target = tmp_path / "photo.jpg"
    target.write_bytes(b"content")
    exif_time = datetime(2026, 5, 21, 20, 48, 2)
    modified_at = datetime(2026, 5, 22, 20, 49, 9)

    monkeypatch.setattr(iphone_context, "get_exif_datetime", lambda path: exif_time)
    monkeypatch.setattr(iphone_context, "_apply_iphone_file_times", lambda *args, **kwargs: None)

    _adjusted_created, adjusted_modified = iphone_context._apply_portable_file_times(
        target,
        None,
        modified_at,
    )

    assert adjusted_modified == modified_at
    assert int(target.stat().st_mtime) == int(modified_at.timestamp())


def test_iphone_import_invalidates_gallery_index_cache(api_client, monkeypatch):
    _, _, image_root, _ = api_client
    database_path = root_database_path(image_root)
    cache_digest = digest_for_cache_key(
        image_scan_cache_key(image_root, SUPPORTED_EXTENSIONS, SKIP_SCAN_DIR_NAMES)
    )
    ImageIndexRepository(database_path).save_index(
        cache_digest,
        root=str(image_root),
        items=[],
        total=0,
        generated_at="2026-05-18T00:00:00",
        timeline_entries=[],
    )
    assert ImageIndexRepository(database_path).load_summary(cache_digest) is not None

    monkeypatch.setattr(iphone_context.platform, "system", lambda: "Windows")
    monkeypatch.setattr(iphone_context, "compute_phash", lambda path: "phash-demo")

    def fake_copy_iphone_media_for_index(device_id, temp_dir, cutoff_modified_at="", skip_refs=None, limit=1):
        temp_path = temp_dir / "IMG_0001.JPG"
        temp_path.write_text("new-content", encoding="utf-8")
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

    assert result["status"] == "imported"
    assert ImageIndexRepository(database_path).load_summary(cache_digest) is None


def test_iphone_index_skips_existing_refs_and_imports_first_unprocessed_item(api_client, monkeypatch):
    _, _, image_root, _ = api_client
    previous = image_root / "2026" / "05" / "18" / "IMG_0001.JPG"
    previous.parent.mkdir(parents=True)
    previous.write_text("previous-content", encoding="utf-8")
    database_path = root_database_path(image_root)
    repository = MobileRepository(database_path)
    repository.save_index(
        device_type="iphone",
        device_id="Apple iPhone",
        device_name="Apple iPhone",
        indexed_at="2026-05-18T00:00:00+00:00",
        records=[
            {
                "device_name": "Apple iPhone",
                "album": "100APPLE",
                "filename": "IMG_0001.JPG",
                "size": previous.stat().st_size,
                "modified_at": "2026-05-18 10:00:00",
                "strict_hash": "previous-hash",
                "phash": "previous-phash",
            }
        ],
    )
    repository.mark_imported(
        device_type="iphone",
        device_id="Apple iPhone",
        album="100APPLE",
        filename="IMG_0001.JPG",
        local_path=previous,
        imported_at="2026-05-18T01:00:00+00:00",
    )

    monkeypatch.setattr(iphone_context.platform, "system", lambda: "Windows")
    monkeypatch.setattr(iphone_context, "compute_phash", lambda path: "phash-next")
    captured_cutoffs = []
    captured_skip_refs = []

    def fake_copy_iphone_media_for_index(device_id, temp_dir, cutoff_modified_at="", skip_refs=None, limit=1):
        captured_cutoffs.append(cutoff_modified_at)
        captured_skip_refs.append(skip_refs)
        temp_path = temp_dir / "IMG_0002.JPG"
        temp_path.write_text("next-content", encoding="utf-8")
        return [
            {
                "device_id": device_id,
                "device_name": "Apple iPhone",
                "album": "100APPLE",
                "filename": "IMG_0002.JPG",
                "temp_path": str(temp_path),
                "size": temp_path.stat().st_size,
                "modified_at": "2026-05-18 09:59:00",
            }
        ]

    monkeypatch.setattr(iphone_context, "_copy_iphone_media_for_index", fake_copy_iphone_media_for_index)

    result = iphone_context.build_iphone_photo_index("Apple iPhone")

    assert result["status"] == "imported"
    assert result["skipped_existing_refs"] == 1
    assert captured_cutoffs == [""]
    assert captured_skip_refs == [["100APPLE/IMG_0001.JPG"]]
    records = repository.list_import_records("iphone", "Apple iPhone")
    assert [record["filename"] for record in records] == ["IMG_0001.JPG", "IMG_0002.JPG"]


def test_iphone_index_skips_previous_strict_duplicate_refs(api_client, monkeypatch):
    _, _, image_root, _ = api_client
    existing = image_root / "2026" / "05" / "18" / "IMG_5611.JPG"
    existing.parent.mkdir(parents=True)
    existing.write_text("same-content", encoding="utf-8")
    database_path = root_database_path(image_root)
    repository = MobileRepository(database_path)
    repository.save_index(
        device_type="iphone",
        device_id="Apple iPhone",
        device_name="Apple iPhone",
        indexed_at="2026-05-18T00:00:00+00:00",
        records=[
            {
                "device_name": "Apple iPhone",
                "album": "201806_a",
                "filename": "IMG_5402.JPG",
                "size": existing.stat().st_size,
                "modified_at": "2026-05-18 10:00:00",
                "strict_hash": "duplicate-hash",
                "phash": "duplicate-phash",
            }
        ],
    )
    repository.mark_skipped_duplicate(
        device_type="iphone",
        device_id="Apple iPhone",
        album="201806_a",
        filename="IMG_5402.JPG",
        existing_local_path=existing,
        imported_at="2026-05-18T01:00:00+00:00",
    )

    monkeypatch.setattr(iphone_context.platform, "system", lambda: "Windows")
    monkeypatch.setattr(iphone_context, "compute_phash", lambda path: "phash-next")
    captured_skip_refs = []

    def fake_copy_iphone_media_for_index(device_id, temp_dir, cutoff_modified_at="", skip_refs=None, limit=1):
        captured_skip_refs.append(skip_refs)
        temp_path = temp_dir / "IMG_5403.JPG"
        temp_path.write_text("next-content", encoding="utf-8")
        return [
            {
                "device_id": device_id,
                "device_name": "Apple iPhone",
                "album": "201806_a",
                "filename": "IMG_5403.JPG",
                "temp_path": str(temp_path),
                "size": temp_path.stat().st_size,
                "modified_at": "2026-05-18 09:59:00",
            }
        ]

    monkeypatch.setattr(iphone_context, "_copy_iphone_media_for_index", fake_copy_iphone_media_for_index)

    result = iphone_context.build_iphone_photo_index("Apple iPhone")

    assert result["status"] == "imported"
    assert result["skipped_existing_refs"] == 1
    assert captured_skip_refs == [["201806_a/IMG_5402.JPG"]]


def test_iphone_index_does_not_downgrade_existing_import_when_same_item_is_returned(api_client, monkeypatch):
    _, _, image_root, _ = api_client
    previous = image_root / "2026" / "05" / "18" / "IMG_0001.JPG"
    previous.parent.mkdir(parents=True)
    previous.write_text("same-content", encoding="utf-8")
    strict_hash = "cae1b3faaa5e4ac7c3306bd164b36dcfdff98294b8024c9c949639b4c480bf6b"
    database_path = root_database_path(image_root)
    HashDbRepository(database_path).save_hash_db(
        {"phash": {}, "strict": {strict_hash: [str(previous)]}},
        source_path=database_path,
    )
    repository = MobileRepository(database_path)
    repository.save_index(
        device_type="iphone",
        device_id="Apple iPhone",
        device_name="Apple iPhone",
        indexed_at="2026-05-18T00:00:00+00:00",
        records=[
            {
                "device_name": "Apple iPhone",
                "album": "100APPLE",
                "filename": "IMG_0001.JPG",
                "size": previous.stat().st_size,
                "modified_at": "2026-05-18 10:00:00",
                "strict_hash": strict_hash,
                "phash": "previous-phash",
            }
        ],
    )
    repository.mark_imported(
        device_type="iphone",
        device_id="Apple iPhone",
        album="100APPLE",
        filename="IMG_0001.JPG",
        local_path=previous,
        imported_at="2026-05-18T01:00:00+00:00",
    )

    monkeypatch.setattr(iphone_context.platform, "system", lambda: "Windows")
    monkeypatch.setattr(iphone_context, "compute_phash", lambda path: "phash-demo")

    def fake_copy_iphone_media_for_index(device_id, temp_dir, cutoff_modified_at="", skip_refs=None, limit=1):
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

    assert result["status"] == "already_imported"
    assert result["already_imported"] == 1
    assert result["already_imported_items"] == [
        {
            "album": "100APPLE",
            "filename": "IMG_0001.JPG",
            "target": "100APPLE/IMG_0001.JPG",
            "local_path": str(previous),
        }
    ]
    records = repository.list_import_records("iphone", "Apple iPhone")
    assert records[0]["import_status"] == "imported"
    assert records[0]["save_state"] == "both"
    assert records[0]["local_path"] == str(previous)
    assert records[0]["existing_local_path"] == ""


def test_delete_iphone_photo_marks_import_record_deleted(api_client, monkeypatch):
    _, _, image_root, _ = api_client
    database_path = root_database_path(image_root)
    repository = MobileRepository(database_path)
    repository.save_index(
        device_type="iphone",
        device_id="Apple iPhone",
        device_name="Apple iPhone",
        indexed_at="2026-05-21T00:00:00+00:00",
        records=[
            {
                "device_name": "Apple iPhone",
                "album": "100APPLE",
                "filename": "IMG_0001.JPG",
                "size": 12,
                "modified_at": "2026-05-21 10:00:00",
                "strict_hash": "strict-demo",
                "phash": "phash-demo",
            }
        ],
    )

    monkeypatch.setattr(iphone_context.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        iphone_context,
        "_delete_iphone_media",
        lambda device_id, album, filename: {
            "device_id": device_id,
            "album": album,
            "filename": filename,
            "deleted": True,
        },
    )

    result = iphone_context.delete_iphone_photo("Apple iPhone", "100APPLE/IMG_0001.JPG")

    assert result["status"] == "deleted"
    records = repository.list_import_records("iphone", "Apple iPhone")
    assert records[0]["deleted_from_device_at"]


def test_iphone_index_skips_existing_strict_duplicate(api_client, monkeypatch):
    _, _, image_root, _ = api_client

    existing = image_root / "existing.jpg"
    existing.write_text("same-content", encoding="utf-8")
    strict_hash = "cae1b3faaa5e4ac7c3306bd164b36dcfdff98294b8024c9c949639b4c480bf6b"
    database_path = root_database_path(image_root)
    HashDbRepository(database_path).save_hash_db(
        {"phash": {}, "strict": {strict_hash: [str(existing)]}},
        source_path=database_path,
    )

    monkeypatch.setattr(iphone_context.platform, "system", lambda: "Windows")
    monkeypatch.setattr(iphone_context, "compute_phash", lambda path: "phash-demo")

    def fake_copy_iphone_media_for_index(device_id, temp_dir, cutoff_modified_at="", skip_refs=None, limit=1):
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

    assert result["status"] == "skipped_duplicate"
    assert result["skipped_duplicate"] == 1
    assert result["existing_local_path"] == str(existing.resolve())
    assert result["skipped_duplicate_items"] == [
        {
            "album": "100APPLE",
            "filename": "IMG_0001.JPG",
            "target": "100APPLE/IMG_0001.JPG",
            "existing_local_path": str(existing.resolve()),
        }
    ]
    records = MobileRepository(database_path).list_import_records("iphone", "Apple iPhone")
    assert records[0]["save_state"] == "both"
    assert records[0]["import_status"] == "skipped_duplicate"
    assert records[0]["local_path"] == ""
    assert records[0]["existing_local_path"] == str(existing.resolve())
    assert HashDbRepository(database_path).load_hash_db()["strict"][strict_hash] == [str(existing)]


def test_iphone_index_ignores_mtp_copy_name_mismatch(api_client, monkeypatch):
    _, _, image_root, _ = api_client

    database_path = root_database_path(image_root)
    existing = image_root / "2019" / "08" / "10" / "IMG_2064.JPG"
    existing.parent.mkdir(parents=True)
    existing.write_text("jpg-content", encoding="utf-8")
    strict_hash = "c48b477601d78d5aa0d0828b74584711c165904c808cb1a9ab849143b62a70aa"
    HashDbRepository(database_path).save_hash_db(
        {"phash": {}, "strict": {strict_hash: [str(existing)]}},
        source_path=database_path,
    )

    monkeypatch.setattr(iphone_context.platform, "system", lambda: "Windows")
    monkeypatch.setattr(iphone_context, "compute_phash", lambda path: "phash-demo")

    def fake_copy_iphone_media_for_index(device_id, temp_dir, cutoff_modified_at="", skip_refs=None, limit=1):
        temp_path = temp_dir / "201909_a" / "IMG_2064.JPG"
        temp_path.parent.mkdir(parents=True)
        temp_path.write_text("jpg-content", encoding="utf-8")
        return [
            {
                "device_id": device_id,
                "device_name": "Apple iPhone",
                "album": "201909_a",
                "filename": "IMG_2325.MOV",
                "temp_path": str(temp_path),
                "size": temp_path.stat().st_size,
                "modified_at": "2026-05-18 10:00:00",
            }
        ]

    monkeypatch.setattr(iphone_context, "_copy_iphone_media_for_index", fake_copy_iphone_media_for_index)

    result = iphone_context.build_iphone_photo_index("Apple iPhone")

    assert result["status"] == "indexed"
    assert result["indexed"] == 0
    assert result["imported"] == 0
    assert result["skipped_duplicate"] == 0
    assert MobileRepository(database_path).list_import_records("iphone", "Apple iPhone") == []
