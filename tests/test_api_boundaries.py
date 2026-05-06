# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
from pathlib import Path

import pytest

import app as ztb_app
import core.context as ztb_context
from core.services.file_service import (
    image_index_cache_path,
    image_index_summary_path,
    image_scan_cache_key,
    timeline_index_cache_path,
)


def test_config_uses_local_cors_origin(api_client) -> None:
    client, *_ = api_client

    response = client.options(
        "/api/config",
        headers={
            "Origin": "http://localhost:8000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:8000"


def test_config_rejects_untrusted_host(api_client) -> None:
    client, *_ = api_client

    response = client.get("/api/config", headers={"host": "example.com"})

    assert response.status_code == 400


def test_config_reports_system_recycle_support(api_client) -> None:
    client, *_ = api_client

    response = client.get("/api/config")

    assert response.status_code == 200
    assert response.json()["system_recycle_supported"] == ztb_app.is_windows()


def test_startup_creates_only_root_scoped_runtime_dirs(api_client) -> None:
    _, workspace, image_root, _ = api_client

    workspace_root = ztb_context.root_data_dir(image_root)

    assert workspace_root.exists()
    assert (workspace_root / "deleted").exists()
    assert (workspace_root / "indexes").exists()
    assert (workspace_root / "logs").exists()
    assert (workspace_root / "tasks").exists()
    assert (workspace_root / "thumbnails").exists()
    assert (ztb_app.ROOT_DATA_DIR / "_indexes").exists()
    assert not (workspace / "logs" / "copy_log.csv").exists()
    assert not (workspace / "logs" / "delete_log.csv").exists()
    assert not (workspace / "thumbnails" / "_indexes").exists()


def test_open_path_blocks_unconfigured_location(api_client) -> None:
    client, tmp_path, *_ = api_client
    outside_path = tmp_path / "outside"
    outside_path.mkdir()

    response = client.post("/api/open-path", json={"path": str(outside_path)})

    assert response.status_code == 403
    assert response.json()["detail"] == "Path is outside configured safe locations"


def test_open_path_allows_configured_root(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _, image_root, _ = api_client
    opened: list[Path] = []
    monkeypatch.setattr(ztb_app, "open_path_in_file_manager", opened.append)

    response = client.post("/api/open-path", json={"path": str(image_root)})

    assert response.status_code == 200
    assert opened == [image_root]


def test_add_root_requires_existing_directory(api_client) -> None:
    client, tmp_path, *_ = api_client

    response = client.post("/api/settings/roots", json={"path": str(tmp_path / "missing")})

    assert response.status_code == 400
    assert response.json()["detail"] == "Image root must be an existing directory"


def test_image_path_traversal_is_rejected(api_client) -> None:
    client, *_ = api_client

    response = client.get("/api/image", params={"relative_path": "../settings.json"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Path escapes configured root"


def test_copy_image_uses_default_target_and_keeps_original(api_client) -> None:
    client, _, image_root, copy_target = api_client
    source = image_root / "photo.jpg"
    source.write_text("demo", encoding="utf-8")

    response = client.post("/api/copy", json={"relative_path": "photo.jpg", "target_dir": ""})

    assert response.status_code == 200
    copied_to = Path(response.json()["copied_to"])
    assert copied_to == copy_target / "photo.jpg"
    assert copied_to.read_text(encoding="utf-8") == "demo"
    assert source.exists()


def test_delete_image_moves_file_to_local_recycle(api_client) -> None:
    client, _, image_root, _ = api_client
    source = image_root / "photo.jpg"
    source.write_text("demo", encoding="utf-8")

    response = client.post("/api/delete", json={"relative_path": "photo.jpg"})

    assert response.status_code == 200
    deleted_to = Path(response.json()["deleted_to"])
    assert deleted_to.is_relative_to(ztb_context.root_deleted_dir(image_root))
    assert deleted_to.name == "photo.jpg"
    assert deleted_to.read_text(encoding="utf-8") == "demo"
    assert not source.exists()


def test_clear_recycle_bin_clears_active_root_recycle_items(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _, image_root, _ = api_client
    source = image_root / "photo.jpg"
    source.write_text("demo", encoding="utf-8")

    delete_response = client.post("/api/delete", json={"relative_path": "photo.jpg"})
    assert delete_response.status_code == 200
    deleted_to = Path(delete_response.json()["deleted_to"])
    assert deleted_to.is_relative_to(ztb_context.root_deleted_dir(image_root))

    recycled_paths: list[Path] = []

    def fake_system_recycle(path: Path) -> None:
        recycled_paths.append(path)
        path.unlink()

    monkeypatch.setattr(ztb_app, "move_to_system_recycle_bin", fake_system_recycle)

    clear_response = client.post("/api/recycle-bin/clear", json={"confirm": True})

    assert clear_response.status_code == 200
    assert clear_response.json()["removed_count"] == 1
    assert recycled_paths == [deleted_to]
    assert not deleted_to.exists()
    assert client.get("/api/recycle-bin").json()["count"] == 0


def test_clear_recycle_bin_permanently_deletes_on_non_windows(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _, image_root, _ = api_client
    source = image_root / "photo.jpg"
    source.write_text("demo", encoding="utf-8")

    delete_response = client.post("/api/delete", json={"relative_path": "photo.jpg"})
    assert delete_response.status_code == 200
    deleted_to = Path(delete_response.json()["deleted_to"])
    monkeypatch.setattr(ztb_app, "is_windows", lambda: False)

    clear_response = client.post("/api/recycle-bin/clear", json={"confirm": True})

    assert clear_response.status_code == 200
    assert clear_response.json()["removed_count"] == 1
    assert not deleted_to.exists()
    assert client.get("/api/recycle-bin").json()["count"] == 0


def test_purge_uses_original_filename_for_legacy_recycle_item(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _, image_root, _ = api_client
    deleted_to = ztb_app.DELETED_DIR / "20260426_abcd1234_photo.jpg"
    deleted_to.write_text("demo", encoding="utf-8")
    ztb_app.append_log(
        "delete_log.csv",
        "2026-04-26T12:00:00",
        str(image_root),
        "album/photo.jpg",
        str(deleted_to),
        "deleted",
    )
    recycled_paths: list[Path] = []

    def fake_system_recycle(path: Path) -> None:
        recycled_paths.append(path)
        path.unlink()

    monkeypatch.setattr(ztb_app, "move_to_system_recycle_bin", fake_system_recycle)

    response = client.post("/api/recycle-bin/purge", json={"deleted_to": str(deleted_to)})

    assert response.status_code == 200
    assert [path.name for path in recycled_paths] == ["photo.jpg"]
    assert not deleted_to.exists()


def test_purge_permanently_deletes_on_non_windows(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _, image_root, _ = api_client
    deleted_to = ztb_context.root_deleted_dir(image_root) / "entry" / "photo.jpg"
    deleted_to.parent.mkdir(parents=True, exist_ok=True)
    deleted_to.write_text("demo", encoding="utf-8")
    monkeypatch.setattr(ztb_app, "is_windows", lambda: False)

    response = client.post("/api/recycle-bin/purge", json={"deleted_to": str(deleted_to)})

    assert response.status_code == 200
    assert response.json()["status"] == "purged"
    assert not deleted_to.exists()


def test_recycle_thumbnail_rejects_unsupported_image_format(api_client) -> None:
    client, _, image_root, _ = api_client
    deleted_to = ztb_context.root_deleted_dir(image_root) / "entry" / "clip.MOV"
    deleted_to.parent.mkdir(parents=True, exist_ok=True)
    deleted_to.write_bytes(b"not an image")

    response = client.get("/api/recycle-bin/thumbnail", params={"deleted_to": str(deleted_to)})

    assert response.status_code == 415
    assert response.json()["detail"] == "Unsupported image format"


def test_delete_missing_image_clears_stale_gallery_entry(api_client) -> None:
    client, _, _, _ = api_client

    response = client.post("/api/delete", json={"relative_path": "missing.jpg"})

    assert response.status_code == 200
    assert response.json() == {"status": "missing", "relative_path": "missing.jpg"}


def test_remove_root_can_clear_related_data(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    client, workspace, image_root, _ = api_client
    other_root = workspace / "other_images"
    other_root.mkdir()
    client.post("/api/settings/roots", json={"path": str(other_root)})
    client.post("/api/settings/active-root", json={"path": str(image_root)})

    cache_key = image_scan_cache_key(image_root, ztb_app.SUPPORTED_EXTENSIONS, ztb_app.EXCLUDED_SCAN_DIRS)
    image_index_dir = ztb_context.root_image_index_dir(image_root)
    image_index_path = image_index_cache_path(image_index_dir, cache_key)
    image_summary_path = image_index_summary_path(image_index_dir, cache_key)
    timeline_path = timeline_index_cache_path(image_index_dir, cache_key)
    index_payload = {"items": [{"relative_path": "photo.jpg", "name": "photo.jpg"}]}
    for path in (image_index_path, image_summary_path, timeline_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}" if path == timeline_path else json.dumps(index_payload), encoding="utf-8")

    thumbnail_path = ztb_app.thumbnail_path_for(image_root, "photo.jpg")
    thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
    thumbnail_path.write_text("thumb", encoding="utf-8")

    duplicates_path = ztb_context.root_duplicates_path(image_root)
    hash_db_path = ztb_context.root_hash_db_path(image_root)
    duplicates_path.parent.mkdir(parents=True, exist_ok=True)
    duplicates_path.write_text("{}", encoding="utf-8")
    hash_db_path.write_text("{}", encoding="utf-8")
    ztb_app.save_root_summary(str(image_root), image_count=3, duplicate_group_count=1, updated_at="2026-04-26T12:00:00")

    deleted_copy = ztb_context.root_deleted_dir(image_root) / "entry" / "photo.jpg"
    deleted_copy.parent.mkdir(parents=True, exist_ok=True)
    deleted_copy.write_text("demo", encoding="utf-8")
    deleted_thumbnail_path = ztb_app.deleted_thumbnail_path_for(deleted_copy)
    deleted_thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
    deleted_thumbnail_path.write_text("deleted-thumb", encoding="utf-8")
    ztb_app.append_log(
        "delete_log.csv",
        "2026-04-26T12:00:00",
        str(image_root),
        "photo.jpg",
        str(deleted_copy),
        "deleted",
    )
    recycled_paths: list[Path] = []

    def fake_system_recycle(path: Path) -> None:
        recycled_paths.append(path)
        path.unlink()

    monkeypatch.setattr(ztb_app, "move_to_system_recycle_bin", fake_system_recycle)

    response = client.post(
        "/api/settings/remove-root",
        json={"path": str(image_root), "cleanup_root_data": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert str(image_root) not in payload["image_roots"]
    assert str(image_root) not in payload["root_summaries"]
    assert payload["cleanup"]["removed"]["root_workspace_dirs"] == 1
    assert payload["cleanup"]["removed"]["delete_log_rows"] == 1
    assert payload["cleanup"]["removed"]["recycle_files"] == 1
    assert recycled_paths == [deleted_copy]
    assert not image_index_path.exists()
    assert not image_summary_path.exists()
    assert not timeline_path.exists()
    assert not duplicates_path.exists()
    assert not hash_db_path.exists()
    assert not thumbnail_path.exists()
    assert not deleted_thumbnail_path.exists()
    assert ztb_app.read_delete_log_rows() == []


def test_run_organizer_rejects_destination_inside_source(api_client) -> None:
    client, _, image_root, _ = api_client
    destination = image_root / "nested" / "organized"

    response = client.post(
        "/api/tasks/run-organizer",
        json={
            "src": str(image_root),
            "dst": str(destination),
            "mode": "copy",
            "duplicate_detection": "strict",
            "phash_threshold": 4,
            "lang": "en",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Destination directory must not be the source directory or one of its children"
    )


def test_rebuild_hash_db_requires_existing_root(api_client) -> None:
    client, tmp_path, *_ = api_client

    response = client.post(
        "/api/tasks/rebuild-hash-db",
        json={
            "root": str(tmp_path / "missing"),
            "rebuild_mode": "replace",
            "hash_method": "strict",
            "lang": "en",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Rebuild root must be an existing directory"
