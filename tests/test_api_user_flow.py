# SPDX-License-Identifier: MIT

from __future__ import annotations

import sys
import json
from datetime import datetime
from pathlib import Path

from PIL import Image

import app as ztb_app
import core.context as ztb_context
import core.services.image_scan_service as image_scan_service
from MediaArchiveOrganizer.core.file_transfer import apply_windows_file_times, read_windows_file_times
from core.services.image_index_service import (
    build_timeline_index_entries,
    image_index_summary_path,
    image_scan_cache_key,
    save_image_index_cache,
    save_image_index_summary,
    save_timeline_index_cache,
)


def create_test_image(path: Path, color: tuple[int, int, int] = (32, 96, 160)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (40, 32), color=color).save(path, format="JPEG")
    return path


def create_test_image_with_exif_dates(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (40, 32), color=(72, 96, 160))
    exif = Image.Exif()
    exif[306] = "2020:01:02 03:04:05"
    exif[36868] = "2021:02:03 04:05:06"
    exif[36867] = "2022:03:04 05:06:07"
    image.save(path, format="JPEG", exif=exif)
    return path


def indexed_image(relative_path: str, value: str) -> dict[str, object]:
    timeline_dt = datetime.fromisoformat(value)
    return {
        "relative_path": relative_path,
        "path": relative_path,
        "name": Path(relative_path).name,
        "size": 100,
        "captured_at": "",
        "modified_at": value,
        "timeline_time": timeline_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "timeline_ts": int(timeline_dt.timestamp()),
        "timeline_source": "file",
    }


def windows_filetime_from_unix(timestamp: float) -> tuple[int, int]:
    filetime = int((timestamp + 11644473600) * 10000000)
    return filetime & 0xFFFFFFFF, filetime >> 32


def set_windows_creation_time(path: Path, timestamp: float) -> None:
    if not sys.platform.startswith("win"):
        return
    current_times = read_windows_file_times(path)
    assert current_times is not None
    apply_windows_file_times(path, (windows_filetime_from_unix(timestamp), current_times[1], current_times[2]))


def assert_windows_creation_time(path: Path, expected: float) -> None:
    if not sys.platform.startswith("win"):
        return
    assert abs(path.stat().st_ctime - expected) < 2


def test_images_use_exif_datetime_priority(api_client) -> None:
    client, workspace, image_root, copy_target = api_client
    create_test_image_with_exif_dates(image_root / "photo.jpg")

    images_response = client.get("/api/images")

    assert images_response.status_code == 200
    item = images_response.json()["items"][0]
    assert item["captured_at"] == "2020-01-02T03:04:05"
    assert item["path"] == "photo.jpg"
    assert item["timeline_time"] == "2020-01-02 03:04:05"
    assert isinstance(item["timeline_ts"], int)
    assert item["timeline_source"] == "exif"


def test_images_lightweight_page_returns_without_total(api_client) -> None:
    client, workspace, image_root, copy_target = api_client
    for index in range(3):
        create_test_image(image_root / f"photo_{index}.jpg")

    response = client.get("/api/images", params={"limit": 2, "include_exif": "false"})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 2
    assert payload["total"] is None
    assert payload["has_more"] is True
    assert payload["next_offset"] == 2
    assert all(item["captured_at"] for item in payload["items"])
    assert all(isinstance(item["timeline_ts"], int) for item in payload["items"])
    assert all(item["timeline_time"] for item in payload["items"])


def test_images_scan_video_files_and_return_placeholder_thumbnail(api_client) -> None:
    client, _, image_root, _ = api_client
    for name in ("clip.mp4", "sample.webm", "movie.mov", "phone.m4v", "legacy.avi", "archive.mkv"):
        (image_root / name).write_bytes(b"not a real video")

    response = client.get("/api/images")

    assert response.status_code == 200
    payload = response.json()
    paths = {item["relative_path"]: item for item in payload["items"]}
    assert set(paths) == {"clip.mp4", "sample.webm", "movie.mov", "phone.m4v", "legacy.avi", "archive.mkv"}
    assert all(item["media_type"] == "video" for item in paths.values())

    thumbnail_response = client.get("/api/thumbnail", params={"relative_path": "clip.mp4"})
    assert thumbnail_response.status_code == 200
    assert thumbnail_response.headers["content-type"].startswith("image/")


def test_images_async_scan_can_return_cached_total(api_client, monkeypatch) -> None:
    client, _, image_root, _ = api_client
    create_test_image(image_root / "a.jpg")
    index_dir = ztb_context.root_image_index_dir(image_root)
    cache_key = image_scan_cache_key(
        image_root,
        ztb_app.SUPPORTED_EXTENSIONS,
        ztb_app.SKIP_SCAN_DIR_NAMES,
    )
    save_image_index_summary(
        index_dir,
        cache_key,
        [indexed_image("a.jpg", "2024-01-01T00:00:00")],
        total=123,
    )

    response = client.get(
        "/api/images",
        params={
            "offset": 0,
            "limit": 48,
            "include_exif": "false",
            "async_scan": "true",
            "refresh_scan": "false",
            "include_total": "true",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 123
    assert isinstance(payload["total_generated_at"], str)
    assert payload["scan_complete"] is False
    assert payload["has_more"] is True


def test_images_async_scan_starts_refresh_for_preview_cache_on_first_load(api_client, monkeypatch) -> None:
    client, _, image_root, _ = api_client
    monkeypatch.setattr(image_scan_service, "IMAGE_SCAN_CACHE", {})
    index_dir = ztb_context.root_image_index_dir(image_root)

    for index in range(3):
        create_test_image(image_root / f"photo_{index}.jpg")

    cache_key = image_scan_cache_key(
        image_root,
        ztb_app.SUPPORTED_EXTENSIONS,
        ztb_app.SKIP_SCAN_DIR_NAMES,
    )
    save_image_index_summary(
        index_dir,
        cache_key,
        [indexed_image("photo_0.jpg", "2024-01-01T00:00:00")],
        total=3,
    )

    started_threads = []

    class RecordingThread:
        def __init__(self, target, args=(), daemon=None):
            self.target = target
            self.args = args
            self.daemon = daemon

        def start(self) -> None:
            started_threads.append(self)

    monkeypatch.setattr(image_scan_service.threading, "Thread", RecordingThread)

    response = client.get(
        "/api/images",
        params={
            "offset": 0,
            "limit": 48,
            "include_exif": "false",
            "async_scan": "true",
            "refresh_scan": "false",
            "include_total": "true",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(started_threads) == 1
    assert payload["scan_complete"] is False
    assert payload["has_more"] is True
    assert payload["total"] == 3
    assert [item["path"] for item in payload["items"]] == ["photo_0.jpg"]

    started_threads[0].target(*started_threads[0].args)

    next_response = client.get(
        "/api/images",
        params={
            "offset": 1,
            "limit": 48,
            "include_exif": "false",
            "async_scan": "true",
            "refresh_scan": "false",
            "include_total": "true",
        },
    )

    assert next_response.status_code == 200
    next_payload = next_response.json()
    assert next_payload["scan_complete"] is True
    assert next_payload["has_more"] is False
    assert next_payload["total"] == 3
    assert [item["path"] for item in next_payload["items"]] == [
        "photo_1.jpg",
        "photo_2.jpg",
    ]


def test_images_async_scan_drops_stale_preview_items_after_refresh(api_client, monkeypatch) -> None:
    client, _, image_root, _ = api_client
    monkeypatch.setattr(image_scan_service, "IMAGE_SCAN_CACHE", {})
    index_dir = ztb_context.root_image_index_dir(image_root)

    create_test_image(image_root / "photo_1.jpg")

    cache_key = image_scan_cache_key(
        image_root,
        ztb_app.SUPPORTED_EXTENSIONS,
        ztb_app.SKIP_SCAN_DIR_NAMES,
    )
    save_image_index_summary(
        index_dir,
        cache_key,
        [
            indexed_image("missing.jpg", "2024-01-02T00:00:00"),
            indexed_image("photo_1.jpg", "2024-01-01T00:00:00"),
        ],
        total=3,
    )

    started_threads = []

    class RecordingThread:
        def __init__(self, target, args=(), daemon=None):
            self.target = target
            self.args = args
            self.daemon = daemon

        def start(self) -> None:
            started_threads.append(self)

    monkeypatch.setattr(image_scan_service.threading, "Thread", RecordingThread)

    response = client.get(
        "/api/images",
        params={
            "offset": 0,
            "limit": 48,
            "include_exif": "false",
            "async_scan": "true",
            "refresh_scan": "false",
        },
    )

    assert response.status_code == 200
    assert [item["path"] for item in response.json()["items"]] == ["photo_1.jpg"]
    assert len(started_threads) == 1

    started_threads[0].target(*started_threads[0].args)

    refreshed_response = client.get(
        "/api/images",
        params={
            "offset": 0,
            "limit": 48,
            "include_exif": "false",
            "async_scan": "true",
            "refresh_scan": "false",
        },
    )

    assert refreshed_response.status_code == 200
    refreshed_payload = refreshed_response.json()
    assert refreshed_payload["scan_complete"] is True
    assert [item["path"] for item in refreshed_payload["items"]] == ["photo_1.jpg"]


def test_images_async_scan_marks_stale_cached_items_missing(api_client, monkeypatch) -> None:
    client, _, image_root, _ = api_client
    index_dir = ztb_context.root_image_index_dir(image_root)
    cache_key = image_scan_cache_key(
        image_root,
        ztb_app.SUPPORTED_EXTENSIONS,
        ztb_app.SKIP_SCAN_DIR_NAMES,
    )
    save_image_index_summary(
        index_dir,
        cache_key,
        [indexed_image("missing.jpg", "2024-01-01T00:00:00")],
        total=1,
    )

    response = client.get(
        "/api/images",
        params={
            "offset": 0,
            "limit": 48,
            "include_exif": "false",
            "async_scan": "true",
            "refresh_scan": "false",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"] == []
    assert payload["count"] == 0
    assert payload["has_more"] is False


def test_async_scan_writes_index_under_root_indexes(api_client, monkeypatch) -> None:
    client, _, image_root, _ = api_client
    create_test_image(image_root / "photo.jpg")

    started_threads = []

    class RecordingThread:
        def __init__(self, target, args=(), daemon=None):
            self.target = target
            self.args = args
            self.daemon = daemon

        def start(self) -> None:
            started_threads.append(self)

    monkeypatch.setattr(image_scan_service.threading, "Thread", RecordingThread)

    response = client.get(
        "/api/images",
        params={
            "offset": 0,
            "limit": 48,
            "include_exif": "false",
            "async_scan": "true",
            "refresh_scan": "true",
        },
    )

    assert response.status_code == 200
    assert len(started_threads) == 1
    started_threads[0].target(*started_threads[0].args)
    index_dir = ztb_context.root_data_dir(image_root) / "indexes"
    assert ztb_context.root_image_index_dir(image_root) == index_dir
    assert any(index_dir.glob("*.summary.json"))
    assert not (ztb_context.root_thumbnail_dir(image_root) / "_indexes").exists()


def test_legacy_root_thumbnail_indexes_are_migrated_to_root_indexes(api_client) -> None:
    _, workspace, image_root, _ = api_client
    legacy_index_dir = workspace / "thumbnails" / "_indexes"
    cache_key = image_scan_cache_key(
        image_root,
        ztb_app.SUPPORTED_EXTENSIONS,
        ztb_app.SKIP_SCAN_DIR_NAMES,
    )
    save_image_index_cache(
        legacy_index_dir,
        cache_key,
        [indexed_image("photo.jpg", "2024-01-01T00:00:00")],
    )

    ztb_context.ensure_root_workspace(image_root)

    scoped_index_dir = ztb_context.root_image_index_dir(image_root)
    assert any(scoped_index_dir.glob("*.json"))
    assert not legacy_index_dir.exists()
    assert not (workspace / "thumbnails").exists()


def test_root_indexes_are_canonicalized_when_cache_key_changes(api_client) -> None:
    _, _, image_root, _ = api_client
    index_dir = ztb_context.root_image_index_dir(image_root)
    old_cache_key = image_scan_cache_key(
        image_root,
        ztb_app.SUPPORTED_EXTENSIONS,
        {*ztb_app.SKIP_SCAN_DIR_NAMES, "legacy_skip_dir"},
    )
    current_cache_key = image_scan_cache_key(
        image_root,
        ztb_app.SUPPORTED_EXTENSIONS,
        ztb_app.SKIP_SCAN_DIR_NAMES,
    )
    old_summary_path = image_index_summary_path(index_dir, old_cache_key)
    current_summary_path = image_index_summary_path(index_dir, current_cache_key)

    save_image_index_summary(
        old_summary_path.parent,
        old_cache_key,
        [indexed_image("old.jpg", "2024-01-01T00:00:00")],
        total=7,
        generated_at="2026-05-05T21:50:42",
        duplicate_group_count=3,
    )
    save_image_index_summary(
        current_summary_path.parent,
        current_cache_key,
        [indexed_image("new.jpg", "2024-01-02T00:00:00")],
        total=7,
        generated_at="2026-05-06T09:06:42",
    )

    ztb_context.ensure_root_workspace(image_root)

    assert current_summary_path.exists()
    with current_summary_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    assert payload["duplicate_group_count"] == 3
    assert [item["relative_path"] for item in payload["items"]] == ["old.jpg"]
    assert not old_summary_path.exists()


def test_timeline_index_is_loaded_from_saved_directory_cache(api_client, monkeypatch) -> None:
    client, _, image_root, _ = api_client
    index_dir = ztb_context.root_image_index_dir(image_root)
    create_test_image(image_root / "2024" / "12" / "25" / "winter.jpg")
    create_test_image(image_root / "2023" / "01" / "02" / "newyear.jpg")

    cache_key = image_scan_cache_key(
        image_root,
        ztb_app.SUPPORTED_EXTENSIONS,
        ztb_app.SKIP_SCAN_DIR_NAMES,
    )
    save_image_index_cache(
        index_dir,
        cache_key,
        [
            indexed_image("2024/12/25/winter.jpg", "2024-12-25T12:00:00"),
            indexed_image("2023/01/02/newyear.jpg", "2023-01-02T08:00:00"),
        ],
    )

    response = client.get("/api/timeline-index")

    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is True
    assert payload["from_cache"] is True
    assert payload["root"] == str(image_root)
    assert payload["entries"] == [
        {"key": "2024-12", "label": "2024-12", "index_label": "202412"},
        {"key": "2023-01", "label": "2023-01", "index_label": "202301"},
    ]


def test_timeline_index_rebuilds_when_image_index_cache_is_newer(api_client, monkeypatch) -> None:
    client, _, image_root, _ = api_client
    index_dir = ztb_context.root_image_index_dir(image_root)
    cache_key = image_scan_cache_key(
        image_root,
        ztb_app.SUPPORTED_EXTENSIONS,
        ztb_app.SKIP_SCAN_DIR_NAMES,
    )

    save_image_index_summary(
        index_dir,
        cache_key,
        [
            indexed_image("2024/12/25/winter.jpg", "2024-12-25T12:00:00"),
            indexed_image("2023/01/02/newyear.jpg", "2023-01-02T08:00:00"),
        ],
        total=2,
        generated_at="2026-04-25T15:44:30",
    )
    save_image_index_cache(
        index_dir,
        cache_key,
        [
            indexed_image("2024/12/25/winter.jpg", "2024-12-25T12:00:00"),
            indexed_image("2023/01/02/newyear.jpg", "2023-01-02T08:00:00"),
        ],
    )
    save_timeline_index_cache(
        index_dir,
        cache_key,
        [indexed_image("2022/02/03/old.jpg", "2022-02-03T08:00:00")],
        "2020-01-01T00:00:00",
    )

    response = client.get("/api/timeline-index")

    assert response.status_code == 200
    payload = response.json()
    assert payload["entries"] == build_timeline_index_entries(
        [
            indexed_image("2024/12/25/winter.jpg", "2024-12-25T12:00:00"),
            indexed_image("2023/01/02/newyear.jpg", "2023-01-02T08:00:00"),
        ]
    )


def test_timeline_grouping_uses_timeline_time_month(api_client, monkeypatch) -> None:
    client, _, image_root, _ = api_client
    index_dir = ztb_context.root_image_index_dir(image_root)
    create_test_image(image_root / "edge.jpg")

    edge_item = indexed_image("edge.jpg", "2024-02-01T00:30:00")
    edge_item["timeline_ts"] = int(datetime(2024, 1, 31, 15, 30, 0).timestamp())

    assert build_timeline_index_entries([edge_item]) == [
        {"key": "2024-02", "label": "2024-02", "index_label": "202402"}
    ]

    cache_key = image_scan_cache_key(
        image_root,
        ztb_app.SUPPORTED_EXTENSIONS,
        ztb_app.SKIP_SCAN_DIR_NAMES,
    )
    save_image_index_cache(index_dir, cache_key, [edge_item])

    index_response = client.get("/api/timeline-index")
    assert index_response.status_code == 200
    assert index_response.json()["entries"] == [
        {"key": "2024-02", "label": "2024-02", "index_label": "202402"}
    ]

    group_response = client.get("/api/images/by-group", params={"group_key": "2024-02"})
    assert group_response.status_code == 200
    group_payload = group_response.json()
    assert group_payload["count"] == 1
    assert group_payload["items"][0]["relative_path"] == "edge.jpg"


def test_gallery_copy_delete_recycle_restore_flow(api_client) -> None:
    client, workspace, image_root, copy_target = api_client
    added_root = workspace / "added_root"
    image_path = create_test_image(added_root / "album" / "photo.jpg")
    original_created_at = 1577934245.0
    set_windows_creation_time(image_path, original_created_at)

    add_root_response = client.post("/api/settings/roots", json={"path": str(added_root)})
    assert add_root_response.status_code == 200
    assert add_root_response.json()["active_root"] == str(added_root)

    images_response = client.get("/api/images")
    assert images_response.status_code == 200
    images_payload = images_response.json()
    assert images_payload["root"] == str(added_root)
    assert [item["relative_path"] for item in images_payload["items"]] == ["album/photo.jpg"]

    thumbnail_response = client.get("/api/thumbnail", params={"relative_path": "album/photo.jpg"})
    assert thumbnail_response.status_code == 200
    assert thumbnail_response.headers["content-type"].startswith("image/")
    assert any(ztb_context.root_thumbnail_dir(added_root).rglob("*.jpg"))

    copy_response = client.post("/api/copy", json={"relative_path": "album/photo.jpg", "target_dir": ""})
    assert copy_response.status_code == 200
    copied_to = Path(copy_response.json()["copied_to"])
    assert copied_to == copy_target / "photo.jpg"
    assert copied_to.read_bytes() == image_path.read_bytes()
    assert_windows_creation_time(copied_to, original_created_at)
    assert image_path.exists()

    delete_response = client.post("/api/delete", json={"relative_path": "album/photo.jpg"})
    assert delete_response.status_code == 200
    deleted_to = Path(delete_response.json()["deleted_to"])
    assert deleted_to.is_relative_to(ztb_context.root_deleted_dir(added_root))
    assert deleted_to.name == "photo.jpg"
    assert deleted_to.exists()
    assert_windows_creation_time(deleted_to, original_created_at)
    assert not image_path.exists()

    images_after_delete_response = client.get("/api/images")
    assert images_after_delete_response.status_code == 200
    assert images_after_delete_response.json()["items"] == []

    recycle_response = client.get("/api/recycle-bin")
    assert recycle_response.status_code == 200
    recycle_payload = recycle_response.json()
    assert recycle_payload["count"] == 1
    recycle_item = recycle_payload["items"][0]
    assert recycle_item["deleted_to"] == str(deleted_to)
    assert recycle_item["relative_path"] == "album/photo.jpg"
    assert recycle_item["restorable"] is True
    assert recycle_item["original_exists"] is False

    recycle_thumbnail_response = client.get("/api/recycle-bin/thumbnail", params={"deleted_to": str(deleted_to)})
    assert recycle_thumbnail_response.status_code == 200
    assert recycle_thumbnail_response.headers["content-type"].startswith("image/")

    restore_response = client.post("/api/recycle-bin/restore", json={"deleted_to": str(deleted_to)})
    assert restore_response.status_code == 200
    assert restore_response.json()["restored_to"] == str(image_path)
    assert image_path.exists()
    assert_windows_creation_time(image_path, original_created_at)
    assert not deleted_to.exists()

    images_after_restore_response = client.get("/api/images")
    assert images_after_restore_response.status_code == 200
    assert [item["relative_path"] for item in images_after_restore_response.json()["items"]] == ["album/photo.jpg"]

    recycle_after_restore_response = client.get("/api/recycle-bin")
    assert recycle_after_restore_response.status_code == 200
    assert recycle_after_restore_response.json()["count"] == 0

    logs_response = client.get("/api/recycle-bin/logs")
    assert logs_response.status_code == 200
    actions = [item["action"] for item in logs_response.json()["items"]]
    assert "deleted" in actions
    assert "restored" in actions


def test_recycle_bin_api_can_return_only_requested_page(api_client) -> None:
    client, workspace, *_ = api_client
    deleted_paths = [
        create_test_image(ztb_app.DELETED_DIR / f"deleted_{index}.jpg", color=(90 + index, 100, 110))
        for index in range(3)
    ]

    for index, deleted_path in enumerate(deleted_paths):
        ztb_app.append_log(
            "delete_log.csv",
            f"2026-04-23T12:34:5{index}",
            str(workspace),
            f"photo_{index}.jpg",
            str(deleted_path),
            "deleted",
        )

    response = client.get("/api/recycle-bin", params={"offset": 0, "limit": 2})

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 3
    assert payload["page_offset"] == 0
    assert payload["page_limit"] == 2
    assert payload["has_more"] is True
    assert len(payload["items"]) == 2
