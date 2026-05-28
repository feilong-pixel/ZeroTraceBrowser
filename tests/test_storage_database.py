# SPDX-License-Identifier: MIT

from __future__ import annotations

import sqlite3
from pathlib import Path

from core.domain.root_context import RootContext
from core.storage.database import init_root_database, root_database_path
from core.storage.duplicates_repository import DuplicateResultRepository
from core.storage.exif_repository import ExifRepository
from core.storage.hash_db_repository import HashDbRepository
from core.storage.image_index_repository import ImageIndexRepository
from core.storage.mobile_repository import MobileRepository
from core.storage.phone_sync_repository import PhoneSyncRepository
from core.storage.recycle_repository import RecycleRepository
from core.storage.similarity_repository import SimilarityRepository
from core.storage.task_repository import TaskRunRepository


def test_root_database_initializes_schema(tmp_path: Path) -> None:
    image_root = tmp_path / "images"
    image_root.mkdir()
    root_context = RootContext.from_root(image_root, tmp_path / "data" / "roots", ensure=True)

    database_path = init_root_database(root_database_path(root_context))

    assert database_path == root_context.database_path
    assert database_path.exists()
    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert {
        "schema_migrations",
        "duplicate_results",
        "duplicate_groups",
        "duplicate_items",
        "image_indexes",
        "image_items",
        "timeline_entries",
        "recycle_records",
        "hash_db_metadata",
        "hash_db_records",
        "file_hash_cache",
        "task_runs",
        "task_skipped_existing",
        "skipped_existing_index",
        "image_exif_cache",
        "similarity_files",
        "similarity_features",
        "mobile_devices",
        "mobile_photo_index",
        "mobile_import_records",
        "mobile_pairings",
        "mobile_sync_sessions",
        "import_runs",
        "import_items",
    }.issubset(tables)


def test_duplicate_repository_round_trips_current_result(tmp_path: Path) -> None:
    repository = DuplicateResultRepository(tmp_path / "workspace.sqlite3")
    payload = {
        "generated_at": "2026-05-13T10:00:00",
        "destination_root": str(tmp_path / "images"),
        "group_count": 1,
        "groups": [
            {
                "group_id": "dup_0001",
                "reason": "strict",
                "hash": "abc123",
                "kept_path": "a.jpg",
                "items": [
                    {"role": "kept", "path": "a.jpg"},
                    {"role": "duplicate", "path": "a_dup1.jpg", "exists": False},
                ],
            }
        ],
    }

    repository.save_result(payload, source_path=tmp_path / "workspace.sqlite3")
    repository.save_result(payload, source_path=tmp_path / "workspace.sqlite3")

    assert repository.load_summary() == {
        "available": True,
        "generated_at": "2026-05-13T10:00:00",
        "destination_root": str(tmp_path / "images"),
        "group_count": 1,
        "source_path": str(tmp_path / "workspace.sqlite3"),
        "dirty": False,
        "dirty_reason": "",
        "dirty_at": None,
        "method_counts": {"strict": 1},
    }
    assert repository.load_result() == {
        "generated_at": "2026-05-13T10:00:00",
        "destination_root": str(tmp_path / "images"),
        "group_count": 1,
        "source_path": str(tmp_path / "workspace.sqlite3"),
        "dirty": False,
        "dirty_reason": "",
        "dirty_at": None,
        "groups": [
            {
                "group_id": "dup_0001",
                "reason": "strict",
                "hash": "abc123",
                "kept_path": "a.jpg",
                "item_count": 2,
                "items": [
                    {"role": "kept", "path": "a.jpg", "exists": True},
                    {"role": "duplicate", "path": "a_dup1.jpg", "exists": False},
                ],
            }
        ],
    }


def test_image_index_repository_round_trips_summary_images_and_timeline(tmp_path: Path) -> None:
    repository = ImageIndexRepository(tmp_path / "workspace.sqlite3")

    repository.save_index(
        "digest",
        root=str(tmp_path / "images"),
        generated_at="2026-05-13T10:00:00",
        total=2,
        duplicate_group_count=1,
        items=[
            {
                "relative_path": "a.jpg",
                "path": "a.jpg",
                "name": "a.jpg",
                "size": 100,
                "modified_at": "2026-05-13T10:00:00",
                "timeline_time": "2026-05-13 10:00:00",
                "timeline_ts": 1778643600,
                "timeline_source": "file",
                "width": 640,
                "height": 480,
            },
            {
                "relative_path": "b.jpg",
                "name": "b.jpg",
                "size": 200,
                "exists": False,
            },
        ],
        timeline_entries=[
            {"key": "2026-05", "label": "2026-05", "index_label": "202605"},
        ],
    )

    summary = repository.load_summary("digest")
    assert summary is not None
    assert summary["total"] == 2
    assert summary["duplicate_group_count"] == 1
    assert [item["relative_path"] for item in summary["items"]] == ["a.jpg", "b.jpg"]
    assert repository.list_images("digest", offset=1, limit=1)[0]["relative_path"] == "b.jpg"
    assert repository.load_timeline_entries("digest") == [
        {"key": "2026-05", "label": "2026-05", "index_label": "202605"}
    ]


def test_image_index_save_upserts_items_and_deletes_missing_paths(tmp_path: Path) -> None:
    repository = ImageIndexRepository(tmp_path / "workspace.sqlite3")

    repository.save_index(
        "digest",
        root=str(tmp_path / "images"),
        generated_at="2026-05-13T10:00:00",
        total=2,
        items=[
            {"relative_path": "keep.jpg", "name": "keep.jpg", "size": 100},
            {"relative_path": "gone.jpg", "name": "gone.jpg", "size": 200},
        ],
    )
    with sqlite3.connect(tmp_path / "workspace.sqlite3") as connection:
        keep_id = connection.execute(
            "SELECT id FROM image_items WHERE cache_digest = ? AND relative_path = ?",
            ("digest", "keep.jpg"),
        ).fetchone()[0]

    repository.save_index(
        "digest",
        root=str(tmp_path / "images"),
        generated_at="2026-05-13T10:05:00",
        total=2,
        items=[
            {"relative_path": "keep.jpg", "name": "keep.jpg", "size": 101},
            {"relative_path": "new.jpg", "name": "new.jpg", "size": 300},
        ],
    )

    items = repository.list_images("digest")
    assert [(item["relative_path"], item["size"]) for item in items] == [
        ("keep.jpg", 101),
        ("new.jpg", 300),
    ]
    with sqlite3.connect(tmp_path / "workspace.sqlite3") as connection:
        assert connection.execute(
            "SELECT id FROM image_items WHERE cache_digest = ? AND relative_path = ?",
            ("digest", "keep.jpg"),
        ).fetchone()[0] == keep_id
        assert connection.execute(
            "SELECT COUNT(*) FROM image_items WHERE cache_digest = ? AND relative_path = ?",
            ("digest", "gone.jpg"),
        ).fetchone()[0] == 0


def test_timeline_entries_are_merged_and_sorted_by_key(tmp_path: Path) -> None:
    repository = ImageIndexRepository(tmp_path / "workspace.sqlite3")

    repository.replace_timeline_entries(
        "digest",
        root=str(tmp_path / "images"),
        generated_at="2026-05-13T10:00:00",
        entries=[
            {"key": "2026-05", "label": "2026-05", "index_label": "202605"},
            {"key": "2026-03", "label": "2026-03", "index_label": "202603"},
            {"key": "unknown", "label": "Unknown date", "index_label": "Unknown"},
        ],
    )

    with sqlite3.connect(tmp_path / "workspace.sqlite3") as connection:
        before_ids = {
            key: row_id
            for row_id, key in connection.execute(
                "SELECT id, key FROM timeline_entries WHERE cache_digest = ?",
                ("digest",),
            ).fetchall()
        }

    repository.replace_timeline_entries(
        "digest",
        root=str(tmp_path / "images"),
        generated_at="2026-05-13T10:05:00",
        entries=[
            {"key": "2026-05", "label": "2026-05", "index_label": "202605"},
            {"key": "2026-04", "label": "2026-04", "index_label": "202604"},
            {"key": "2026-03", "label": "2026-03", "index_label": "202603"},
        ],
    )

    assert repository.load_timeline_entries("digest") == [
        {"key": "2026-05", "label": "2026-05", "index_label": "202605"},
        {"key": "2026-04", "label": "2026-04", "index_label": "202604"},
        {"key": "2026-03", "label": "2026-03", "index_label": "202603"},
    ]
    with sqlite3.connect(tmp_path / "workspace.sqlite3") as connection:
        after_ids = {
            key: row_id
            for row_id, key in connection.execute(
                "SELECT id, key FROM timeline_entries WHERE cache_digest = ?",
                ("digest",),
            ).fetchall()
        }
    assert after_ids["2026-05"] == before_ids["2026-05"]
    assert after_ids["2026-03"] == before_ids["2026-03"]
    assert "unknown" not in after_ids
    assert "2026-04" in after_ids


def test_partial_timeline_merge_keeps_missing_old_keys(tmp_path: Path) -> None:
    repository = ImageIndexRepository(tmp_path / "workspace.sqlite3")

    repository.replace_timeline_entries(
        "digest",
        root=str(tmp_path / "images"),
        generated_at="2026-05-13T10:00:00",
        entries=[
            {"key": "2026-05", "label": "2026-05", "index_label": "202605"},
            {"key": "2026-03", "label": "2026-03", "index_label": "202603"},
        ],
    )
    repository.replace_timeline_entries(
        "digest",
        root=str(tmp_path / "images"),
        generated_at="2026-05-13T10:05:00",
        entries=[
            {"key": "2026-04", "label": "2026-04", "index_label": "202604"},
        ],
        delete_missing=False,
    )

    assert repository.load_timeline_entries("digest") == [
        {"key": "2026-05", "label": "2026-05", "index_label": "202605"},
        {"key": "2026-04", "label": "2026-04", "index_label": "202604"},
        {"key": "2026-03", "label": "2026-03", "index_label": "202603"},
    ]


def test_image_index_save_preserves_total_when_total_is_none(tmp_path: Path) -> None:
    repository = ImageIndexRepository(tmp_path / "workspace.sqlite3")

    repository.save_index(
        "digest",
        root=str(tmp_path / "images"),
        items=[],
        total=12,
        generated_at="2026-05-13T10:00:00",
    )
    repository.save_index(
        "digest",
        root=str(tmp_path / "images"),
        items=[],
        total=None,
        generated_at="2026-05-13T10:05:00",
    )

    assert repository.load_summary("digest")["total"] == 12


def test_hash_db_repository_round_trips_current_hash_records(tmp_path: Path) -> None:
    repository = HashDbRepository(tmp_path / "workspace.sqlite3")
    payload = {
        "phash": {"abc": [str(tmp_path / "a.jpg"), str(tmp_path / "b.jpg")]},
        "strict": {"def": [str(tmp_path / "c.jpg")]},
    }

    repository.save_hash_db(payload, source_path=tmp_path / "hash_db.json")
    repository.save_hash_db(payload, source_path=tmp_path / "hash_db.json")

    summary = repository.load_summary()
    assert repository.load_hash_db() == payload
    assert summary == {
        "available": True,
        "source_path": str(tmp_path / "hash_db.json"),
        "updated_at": summary["updated_at"],
        "record_count": 2,
        "path_count": 3,
        "method_counts": {
            "phash": {"record_count": 1, "path_count": 2},
            "strict": {"record_count": 1, "path_count": 1},
        },
    }


def test_exif_repository_returns_only_current_file_signature(tmp_path: Path) -> None:
    repository = ExifRepository(tmp_path / "workspace.sqlite3")
    payload = {"width": "40", "height": "32", "datetime": "2026-05-13 10:00:00"}

    repository.save_exif("photo.jpg", payload, file_size=123, mtime_ns=456)

    assert repository.load_exif("photo.jpg", file_size=123, mtime_ns=456) == payload
    assert repository.load_exif("photo.jpg", file_size=124, mtime_ns=456) is None


def test_mobile_repository_records_device_index_and_import_state(tmp_path: Path) -> None:
    repository = MobileRepository(tmp_path / "workspace.sqlite3")

    repository.save_index(
        device_type="iphone",
        device_id="Apple iPhone",
        device_name="Apple iPhone",
        indexed_at="2026-05-18T10:00:00+00:00",
        records=[
            {
                "device_name": "Apple iPhone",
                "album": "100APPLE",
                "filename": "IMG_0001.JPG",
                "size": 123,
                "modified_at": "2026-05-18 10:00:00",
                "strict_hash": "strict-demo",
                "phash": "phash-demo",
                "temp_path": str(tmp_path / "staging" / "IMG_0001.JPG"),
            }
        ],
    )
    repository.mark_imported(
        device_type="iphone",
        device_id="Apple iPhone",
        album="100APPLE",
        filename="IMG_0001.JPG",
        local_path=tmp_path / "images" / "IMG_0001.JPG",
        imported_at="2026-05-18T10:01:00+00:00",
    )

    assert repository.list_import_records("iphone", "Apple iPhone") == [
        {
            "device_type": "iphone",
            "device_id": "Apple iPhone",
            "device_name": "Apple iPhone",
            "album": "100APPLE",
            "filename": "IMG_0001.JPG",
            "mobile_ref": "mobile://iphone/Apple iPhone/DCIM/100APPLE/IMG_0001.JPG",
            "size": 123,
            "modified_at": "2026-05-18 10:00:00",
            "strict_hash": "strict-demo",
            "phash": "phash-demo",
            "save_state": "both",
            "import_status": "imported",
            "local_path": str(tmp_path / "images" / "IMG_0001.JPG"),
            "existing_local_path": "",
            "deleted_from_device_at": "",
            "indexed_at": "2026-05-18T10:00:00+00:00",
            "imported_at": "2026-05-18T10:01:00+00:00",
        }
    ]


def test_phone_sync_repository_records_pair_session_and_manifest(tmp_path: Path) -> None:
    repository = PhoneSyncRepository(tmp_path / "workspace.sqlite3")

    pairing = repository.pair_device(
        server_id="server-1",
        root_id="root-1",
        destination_root=str(tmp_path / "images"),
        sync_token="sync-token",
        token_expires_at="2026-05-24T10:30:00+00:00",
        payload={
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
    assert pairing["server_id"] == "server-1"
    assert pairing["root_id"] == "root-1"
    assert pairing["device_id"] == "phone-1"

    session = repository.start_session(
        session_id="session-1",
        server_id="server-1",
        root_id="root-1",
        destination_root=str(tmp_path / "images"),
        sync_token="sync-token",
        token_expires_at="2026-05-24T10:30:00+00:00",
        payload={
            "device_type": "iphone",
            "device_id": "phone-1",
            "last_client_cursor": "client-cursor",
            "battery_state": "charging",
            "network_type": "wifi",
        },
    )
    assert session["session_id"] == "session-1"
    assert session["status"] == "ready"

    manifest = repository.save_manifest(
        upload_batch_id="batch-1",
        payload={
            "session_id": "session-1",
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
    assert manifest["status"] == "accepted"
    assert manifest["upload"] == [
        {
            "item_id": "asset-1",
            "upload_url": "/api/mobile/sync/upload",
            "status": "upload_required",
        }
    ]
    assert repository.status(destination_root=str(tmp_path / "images"))["paired_devices"] == 1


def test_similarity_repository_round_trips_file_and_features(tmp_path: Path) -> None:
    repository = SimilarityRepository(tmp_path / "workspace.sqlite3")

    file_record = repository.upsert_file(
        relative_path="2026/05/a.jpg",
        absolute_path=tmp_path / "images" / "2026" / "05" / "a.jpg",
        size=123,
        mtime_ns=456,
    )
    feature = repository.upsert_feature(
        file_id=file_record.id,
        method="feature",
        model="orb",
        version=1,
        value_blob=b"descriptor-bytes",
        keypoint_count=42,
        detector="orb",
    )

    assert feature.relative_path == "2026/05/a.jpg"
    assert feature.file_name == "a.jpg"
    assert feature.value_blob == b"descriptor-bytes"
    assert feature.keypoint_count == 42
    assert repository.get_current_file("2026/05/a.jpg", size=123, mtime_ns=456) == file_record
    assert repository.get_feature(
        "2026/05/a.jpg",
        method="feature",
        model="orb",
        size=123,
        mtime_ns=456,
    ) == feature
    assert repository.list_features(method="feature", model="orb") == [feature]


def test_similarity_repository_updates_feature_and_invalidates_by_signature(
    tmp_path: Path,
) -> None:
    repository = SimilarityRepository(tmp_path / "workspace.sqlite3")

    file_record = repository.upsert_file(
        relative_path="a.jpg",
        absolute_path=tmp_path / "images" / "a.jpg",
        size=100,
        mtime_ns=200,
    )
    first = repository.upsert_feature(
        file_id=file_record.id,
        method="phash",
        value_text="abc",
    )
    second = repository.upsert_feature(
        file_id=file_record.id,
        method="phash",
        value_text="def",
    )

    assert second.id == first.id
    assert repository.get_feature("a.jpg", method="phash").value_text == "def"
    assert repository.get_feature("a.jpg", method="phash", size=101, mtime_ns=200) is None

    refreshed = repository.upsert_file(
        relative_path="a.jpg",
        absolute_path=tmp_path / "images" / "a.jpg",
        size=101,
        mtime_ns=201,
    )
    assert refreshed.id == file_record.id
    assert repository.get_current_file("a.jpg", size=100, mtime_ns=200) is None
    assert repository.get_feature("a.jpg", method="phash", size=101, mtime_ns=201).value_text == "def"


def test_similarity_repository_deletes_file_with_cached_features(tmp_path: Path) -> None:
    repository = SimilarityRepository(tmp_path / "workspace.sqlite3")
    first = repository.upsert_file(relative_path="a.jpg", size=1, mtime_ns=2)
    second = repository.upsert_file(relative_path="b.jpg", size=3, mtime_ns=4)
    repository.upsert_feature(file_id=first.id, method="document", value_text="hash-a")
    repository.upsert_feature(file_id=second.id, method="document", value_text="hash-b")

    assert repository.delete_file("a.jpg") is True
    assert repository.delete_file("missing.jpg") is False

    assert repository.get_file("a.jpg") is None
    assert [item.relative_path for item in repository.list_features(method="document")] == ["b.jpg"]


def test_similarity_repository_prunes_missing_or_stale_file_records(tmp_path: Path) -> None:
    repository = SimilarityRepository(tmp_path / "workspace.sqlite3")
    current = repository.upsert_file(relative_path="current.jpg", size=1, mtime_ns=2)
    stale = repository.upsert_file(relative_path="stale.jpg", size=3, mtime_ns=4)
    missing = repository.upsert_file(relative_path="missing.jpg", size=5, mtime_ns=6)
    repository.upsert_feature(file_id=current.id, method="document", value_text="current")
    repository.upsert_feature(file_id=stale.id, method="document", value_text="stale")
    repository.upsert_feature(file_id=missing.id, method="document", value_text="missing")

    deleted = repository.delete_stale_files(
        {
            "current.jpg": (1, 2),
            "stale.jpg": (3, 5),
        }
    )

    assert deleted == 2
    assert [item.relative_path for item in repository.list_features(method="document")] == ["current.jpg"]


def test_recycle_repository_updates_lifecycle_action(tmp_path: Path) -> None:
    repository = RecycleRepository(tmp_path / "workspace.sqlite3")

    repository.append_record(
        timestamp="2026-05-13T10:00:00",
        root=str(tmp_path / "images"),
        relative_path="a.jpg",
        deleted_to=str(tmp_path / "deleted" / "a.jpg"),
    )

    assert repository.update_action(str(tmp_path / "deleted" / "a.jpg"), "restored") is True
    assert repository.update_action(str(tmp_path / "deleted" / "missing.jpg"), "restored") is False
    assert repository.list_records() == [
        {
            "timestamp": "2026-05-13T10:00:00",
            "root": str(tmp_path / "images"),
            "relative_path": "a.jpg",
            "deleted_to": str(tmp_path / "deleted" / "a.jpg"),
            "action": "restored",
        }
    ]
    assert repository.list_records(include_terminal=False) == []


def test_task_run_repository_records_task_and_skipped_existing(tmp_path: Path) -> None:
    repository = TaskRunRepository(tmp_path / "workspace.sqlite3")
    task = {
        "task_id": "task_1",
        "task_type": "organizer",
        "status": "running",
        "started_at": "2026-05-18T10:00:00",
        "finished_at": None,
        "params": {
            "src": str(tmp_path / "phone"),
            "dst": str(tmp_path / "gallery"),
            "mode": "copy",
            "duplicate_detection": "both",
            "phash_threshold": 5,
            "skip_existing_exact": False,
        },
        "outputs": {
            "log_path": str(tmp_path / "tasks" / "task_1" / "organizer.log"),
            "duplicate_report_path": str(tmp_path / "tasks" / "task_1" / "duplicate_report.csv"),
        },
        "error": None,
    }

    repository.save_task_started(task)
    repository.record_skipped_existing(
        task_id="task_1",
        source_path=str(tmp_path / "phone" / "a.jpg"),
        existing_path=str(tmp_path / "gallery" / "a.jpg"),
        strict_hash="hash-a",
        size=123,
        file_name="a.jpg",
    )
    repository.record_skipped_existing(
        task_id="task_1",
        source_path=str(tmp_path / "phone" / "a.jpg"),
        existing_path=str(tmp_path / "gallery" / "a.jpg"),
        strict_hash="hash-a",
        size=123,
        file_name="a.jpg",
    )
    task["status"] = "completed"
    task["finished_at"] = "2026-05-18T10:05:00"
    repository.update_task_finished(
        task,
        scanned_count=2,
        saved_count=1,
        skipped_existing_count=1,
        skipped_existing_bytes=123,
        similar_group_count=0,
    )

    saved = repository.load_task("task_1")
    assert saved is not None
    assert saved["task_type"] == "organizer"
    assert saved["status"] == "completed"
    assert saved["skip_existing_exact"] == 0
    assert saved["scanned_count"] == 2
    assert saved["skipped_existing_bytes"] == 123
    assert len(repository.list_skipped_existing("task_1")) == 2

    with sqlite3.connect(tmp_path / "workspace.sqlite3") as connection:
        index_row = connection.execute(
            "SELECT seen_count, first_task_id, last_task_id FROM skipped_existing_index WHERE strict_hash = ?",
            ("hash-a",),
        ).fetchone()
    assert index_row == (2, "task_1", "task_1")
