# SPDX-License-Identifier: MIT

from __future__ import annotations

import sqlite3
from pathlib import Path

from core.domain.root_context import RootContext
from core.storage.database import init_root_database, root_database_path
from core.storage.duplicates_repository import DuplicateResultRepository
from core.storage.hash_db_repository import HashDbRepository
from core.storage.image_index_repository import ImageIndexRepository
from core.storage.recycle_repository import RecycleRepository


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

    repository.save_result(payload, source_path=tmp_path / "duplicates.json")
    repository.save_result(payload, source_path=tmp_path / "duplicates.json")

    assert repository.load_summary() == {
        "available": True,
        "generated_at": "2026-05-13T10:00:00",
        "destination_root": str(tmp_path / "images"),
        "group_count": 1,
        "source_path": str(tmp_path / "duplicates.json"),
        "method_counts": {"strict": 1},
    }
    assert repository.load_result() == {
        "generated_at": "2026-05-13T10:00:00",
        "destination_root": str(tmp_path / "images"),
        "group_count": 1,
        "source_path": str(tmp_path / "duplicates.json"),
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
