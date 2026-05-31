# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path

from tests.test_api_user_flow import create_test_image

import app as ztb_app
import core.context as ztb_context
import core.context_modules.duplicates_context as duplicates_context
from core.domain.root_context import RootContext
from core.storage.duplicates_repository import DuplicateResultRepository
from core.storage.hash_db_repository import HashDbRepository
from core.storage.recycle_repository import RecycleRepository
from media_engine.services.organizer import rebuild_duplicate_results_from_hash_db


def save_duplicates_db(root: Path, groups: list[dict], destination_root: Path | None = None) -> Path:
    database_path = RootContext.from_root(root, ztb_app.ROOT_DATA_DIR).database_path
    DuplicateResultRepository(database_path).save_result(
        {
            "generated_at": "2026-04-23T12:34:56",
            "destination_root": str(destination_root or root),
            "group_count": len(groups),
            "groups": groups,
        },
        source_path=database_path,
    )
    return database_path


def test_duplicates_api_loads_latest_result_and_filters_unavailable_groups(api_client) -> None:
    client, workspace, image_root, _ = api_client
    archive_root = workspace / "archive"
    kept = create_test_image(archive_root / "2026" / "04" / "23" / "kept.jpg")
    duplicate = create_test_image(archive_root / "2026" / "04" / "23" / "kept_dup1.jpg", color=(160, 96, 32))

    client.post("/api/settings/roots", json={"path": str(archive_root)})

    database_path = save_duplicates_db(
        archive_root,
        [
            {
                "group_id": "dup_0001",
                "reason": "strict",
                "hash": "abc123",
                "kept_path": "2026/04/23/kept.jpg",
                "items": [
                    {"role": "kept", "path": "2026/04/23/kept.jpg"},
                    {"role": "duplicate", "path": "2026/04/23/kept_dup1.jpg"},
                    {"role": "duplicate", "path": "2026/04/23/missing.jpg"},
                    {"role": "duplicate", "path": "../outside.jpg"},
                ],
            },
            {
                "group_id": "dup_0002",
                "reason": "strict",
                "hash": "single",
                "kept_path": "2026/04/23/only.jpg",
                "items": [
                    {"role": "kept", "path": "2026/04/23/kept.jpg"},
                    {"role": "duplicate", "path": "2026/04/23/missing.jpg"},
                ],
            },
        ],
    )

    response = client.get("/api/duplicates")

    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is True
    assert payload["database_path"] == str(database_path)
    assert payload["destination_root"] == str(archive_root)
    assert payload["active_root_matches"] is True
    assert payload["group_count"] == 1
    assert len(payload["groups"]) == 1

    group = payload["groups"][0]
    assert group["group_id"] == "dup_0001"
    assert group["reason"] == "strict"
    assert group["hash"] == "abc123"
    assert group["item_count"] == 2
    assert group["available_count"] == 2
    assert group["preview_paths"] == [
        "2026/04/23/kept.jpg",
        "2026/04/23/kept_dup1.jpg",
    ]
    assert group["items"] == [
        {"role": "kept", "path": "2026/04/23/kept.jpg", "exists": True},
        {"role": "duplicate", "path": "2026/04/23/kept_dup1.jpg", "exists": True},
    ]
    assert kept.exists()
    assert duplicate.exists()


def test_duplicates_thumbnail_and_open_result_root(api_client, monkeypatch) -> None:
    client, workspace, *_ = api_client
    archive_root = workspace / "archive"
    create_test_image(archive_root / "same.jpg")
    create_test_image(archive_root / "same_dup1.jpg", color=(90, 120, 45))
    client.post("/api/settings/roots", json={"path": str(archive_root)})
    save_duplicates_db(
        archive_root,
        [
            {
                "group_id": "dup_0001",
                "reason": "strict",
                "hash": "abc123",
                "kept_path": "same.jpg",
                "items": [
                    {"role": "kept", "path": "same.jpg"},
                    {"role": "duplicate", "path": "same_dup1.jpg"},
                ],
            },
        ],
    )
    opened: list[Path] = []
    monkeypatch.setattr(ztb_app, "open_path_in_file_manager", opened.append)

    thumbnail_response = client.get("/api/duplicates/thumbnail", params={"relative_path": "same.jpg"})
    assert thumbnail_response.status_code == 200
    assert thumbnail_response.headers["content-type"].startswith("image/")
    assert any(ztb_context.root_thumbnail_dir(archive_root).rglob("*.jpg"))

    open_response = client.post("/api/duplicates/open-result-root", json={})
    assert open_response.status_code == 200
    assert open_response.json() == {"status": "opened", "path": str(archive_root)}
    assert opened == [archive_root]


def test_duplicates_thumbnail_uses_summary_without_loading_all_groups(api_client, monkeypatch) -> None:
    client, workspace, *_ = api_client
    archive_root = workspace / "archive"
    create_test_image(archive_root / "same.jpg")
    create_test_image(archive_root / "same_dup1.jpg", color=(90, 120, 45))
    client.post("/api/settings/roots", json={"path": str(archive_root)})
    save_duplicates_db(
        archive_root,
        [
            {
                "group_id": "dup_0001",
                "reason": "strict",
                "hash": "abc123",
                "kept_path": "same.jpg",
                "items": [
                    {"role": "kept", "path": "same.jpg"},
                    {"role": "duplicate", "path": "same_dup1.jpg"},
                ],
            },
        ],
    )
    duplicates_context.clear_duplicates_path_cache()

    def fail_full_load(active_root: str) -> dict | None:
        raise AssertionError(f"thumbnail root lookup should not load all groups: {active_root}")

    monkeypatch.setattr(duplicates_context, "load_database_duplicates_payload", fail_full_load)

    thumbnail_response = client.get("/api/duplicates/thumbnail", params={"relative_path": "same.jpg"})

    assert thumbnail_response.status_code == 200


def test_duplicates_thumbnail_returns_placeholder_for_video(api_client) -> None:
    client, workspace, *_ = api_client
    archive_root = workspace / "archive"
    archive_root.mkdir()
    (archive_root / "clip.mp4").write_bytes(b"not a real video")
    client.post("/api/settings/roots", json={"path": str(archive_root)})
    save_duplicates_db(
        archive_root,
        [
            {
                "group_id": "video-group",
                "reason": "strict",
                "hash": "video",
                "kept_path": "clip.mp4",
                "items": [{"role": "kept", "path": "clip.mp4"}],
            },
        ],
    )

    thumbnail_response = client.get("/api/duplicates/thumbnail", params={"relative_path": "clip.mp4"})

    assert thumbnail_response.status_code == 200
    assert thumbnail_response.headers["content-type"].startswith("image/")


def test_duplicates_api_can_return_only_requested_page(api_client) -> None:
    client, workspace, *_ = api_client
    archive_root = workspace / "archive"
    groups = []
    for index in range(3):
        kept_name = f"kept_{index}.jpg"
        duplicate_name = f"kept_{index}_dup1.jpg"
        create_test_image(archive_root / kept_name)
        create_test_image(archive_root / duplicate_name, color=(80 + index, 90, 100))
        groups.append(
            {
                "group_id": f"dup_{index:04d}",
                "reason": "strict",
                "hash": f"hash_{index}",
                "kept_path": kept_name,
                "items": [
                    {"role": "kept", "path": kept_name},
                    {"role": "duplicate", "path": duplicate_name},
                ],
            }
        )

    client.post("/api/settings/roots", json={"path": str(archive_root)})
    save_duplicates_db(archive_root, groups)

    response = client.get("/api/duplicates", params={"offset": 0, "limit": 1, "method": "strict"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["group_count"] == 3
    assert payload["page_offset"] == 0
    assert payload["page_limit"] == 1
    assert payload["method_filter"] == "strict"
    assert payload["has_more"] is True
    assert payload["method_counts"] == {"phash": 0, "strict": 3}
    assert [group["group_id"] for group in payload["groups"]] == ["dup_0000"]


def test_duplicates_api_phash_page_skips_unavailable_leading_groups(api_client) -> None:
    client, workspace, *_ = api_client
    archive_root = workspace / "archive"
    create_test_image(archive_root / "visible_a.jpg")
    create_test_image(archive_root / "visible_b.jpg", color=(80, 90, 100))
    create_test_image(archive_root / "visible_c.jpg", color=(90, 100, 110))
    create_test_image(archive_root / "visible_d.jpg", color=(100, 110, 120))
    groups = [
        {
            "group_id": "missing_0000",
            "reason": "phash",
            "hash": "missing",
            "items": [
                {"role": "kept", "path": "missing_a.jpg", "exists": False},
                {"role": "duplicate", "path": "missing_b.jpg", "exists": False},
            ],
        },
        {
            "group_id": "visible_0001",
            "reason": "phash",
            "hash": "visible-1",
            "items": [
                {"role": "kept", "path": "visible_a.jpg"},
                {"role": "duplicate", "path": "visible_b.jpg"},
            ],
        },
        {
            "group_id": "visible_0002",
            "reason": "phash",
            "hash": "visible-2",
            "items": [
                {"role": "kept", "path": "visible_c.jpg"},
                {"role": "duplicate", "path": "visible_d.jpg"},
            ],
        },
    ]

    client.post("/api/settings/roots", json={"path": str(archive_root)})
    save_duplicates_db(archive_root, groups)

    response = client.get("/api/duplicates", params={"offset": 0, "limit": 1, "method": "phash"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["group_count"] == 2
    assert payload["has_more"] is True
    assert [group["group_id"] for group in payload["groups"]] == ["visible_0001"]


def test_duplicates_api_paged_results_reconcile_missing_files(api_client) -> None:
    client, workspace, *_ = api_client
    archive_root = workspace / "archive"
    archive_root.mkdir()
    groups = [
        {
            "group_id": "db_visible",
            "reason": "phash",
            "hash": "db-visible",
            "items": [
                {"role": "kept", "path": "missing_on_disk_a.jpg", "exists": True},
                {"role": "duplicate", "path": "missing_on_disk_b.jpg", "exists": True},
            ],
        },
    ]

    client.post("/api/settings/roots", json={"path": str(archive_root)})
    save_duplicates_db(archive_root, groups)

    response = client.get("/api/duplicates", params={"offset": 0, "limit": 20, "method": "phash"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["group_count"] == 0
    assert payload["groups"] == []


def test_duplicates_api_strict_page_counts_only_remaining_visible_groups(api_client) -> None:
    client, workspace, *_ = api_client
    archive_root = workspace / "archive"
    create_test_image(archive_root / "visible_a.jpg")
    create_test_image(archive_root / "visible_b.jpg", color=(80, 90, 100))
    create_test_image(archive_root / "visible_c.jpg", color=(90, 100, 110))
    create_test_image(archive_root / "visible_d.jpg", color=(100, 110, 120))
    groups = [
        {
            "group_id": "missing_0000",
            "reason": "strict",
            "hash": "missing",
            "items": [
                {"role": "kept", "path": "missing_a.jpg", "exists": False},
                {"role": "duplicate", "path": "missing_b.jpg", "exists": False},
            ],
        },
        {
            "group_id": "visible_0001",
            "reason": "strict",
            "hash": "visible-1",
            "items": [
                {"role": "kept", "path": "visible_a.jpg"},
                {"role": "duplicate", "path": "visible_b.jpg"},
            ],
        },
        {
            "group_id": "visible_0002",
            "reason": "strict",
            "hash": "visible-2",
            "items": [
                {"role": "kept", "path": "visible_c.jpg"},
                {"role": "duplicate", "path": "visible_d.jpg"},
            ],
        },
    ]

    client.post("/api/settings/roots", json={"path": str(archive_root)})
    save_duplicates_db(archive_root, groups)

    first_response = client.get("/api/duplicates", params={"offset": 0, "limit": 1, "method": "strict"})
    second_response = client.get("/api/duplicates", params={"offset": 1, "limit": 1, "method": "strict"})

    assert first_response.status_code == 200
    first_payload = first_response.json()
    assert first_payload["group_count"] == 2
    assert first_payload["has_more"] is True
    assert [group["group_id"] for group in first_payload["groups"]] == ["visible_0001"]

    assert second_response.status_code == 200
    second_payload = second_response.json()
    assert second_payload["group_count"] == 2
    assert second_payload["has_more"] is False
    assert [group["group_id"] for group in second_payload["groups"]] == ["visible_0002"]


def test_duplicates_api_strict_offset_uses_remaining_visible_groups(api_client) -> None:
    client, workspace, *_ = api_client
    archive_root = workspace / "archive"
    groups = []
    for index in range(6):
        kept_name = f"kept_{index}.jpg"
        duplicate_name = f"kept_{index}_dup1.jpg"
        create_test_image(archive_root / kept_name)
        create_test_image(archive_root / duplicate_name, color=(80 + index, 90, 100))
        groups.append(
            {
                "group_id": f"dup_{index:04d}",
                "reason": "strict",
                "hash": f"hash_{index}",
                "kept_path": kept_name,
                "items": [
                    {"role": "kept", "path": kept_name},
                    {"role": "duplicate", "path": duplicate_name},
                ],
            }
        )

    client.post("/api/settings/roots", json={"path": str(archive_root)})
    save_duplicates_db(archive_root, groups)

    response = client.get("/api/duplicates", params={"offset": 3, "limit": 1, "method": "strict"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["group_count"] == 6
    assert payload["has_more"] is True
    assert [group["group_id"] for group in payload["groups"]] == ["dup_0003"]


def test_duplicates_api_delete_updates_remaining_group_count(api_client) -> None:
    client, workspace, *_ = api_client
    archive_root = workspace / "archive"
    create_test_image(archive_root / "remove_a.jpg")
    create_test_image(archive_root / "remove_b.jpg", color=(80, 90, 100))
    create_test_image(archive_root / "keep_a.jpg", color=(90, 100, 110))
    create_test_image(archive_root / "keep_b.jpg", color=(100, 110, 120))
    client.post("/api/settings/roots", json={"path": str(archive_root)})
    save_duplicates_db(
        archive_root,
        [
            {
                "group_id": "removed_after_delete",
                "reason": "strict",
                "hash": "remove",
                "items": [
                    {"role": "kept", "path": "remove_a.jpg"},
                    {"role": "duplicate", "path": "remove_b.jpg"},
                ],
            },
            {
                "group_id": "still_remaining",
                "reason": "strict",
                "hash": "keep",
                "items": [
                    {"role": "kept", "path": "keep_a.jpg"},
                    {"role": "duplicate", "path": "keep_b.jpg"},
                ],
            },
        ],
    )

    delete_response = client.post("/api/delete", json={"relative_path": "remove_b.jpg"})
    config_response = client.get("/api/config")
    images_response = client.get(
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
    response = client.get("/api/duplicates", params={"offset": 0, "limit": 20, "method": "strict"})

    assert delete_response.status_code == 200
    assert config_response.status_code == 200
    assert config_response.json()["root_summary"]["image_count"] == 3
    assert images_response.status_code == 200
    assert images_response.json()["total"] == 3
    assert response.status_code == 200
    payload = response.json()
    assert payload["group_count"] == 1
    assert payload["has_more"] is False
    assert payload["method_counts"] == {"phash": 0, "strict": 1}
    assert [group["group_id"] for group in payload["groups"]] == ["still_remaining"]


def test_delete_missing_duplicate_item_marks_duplicate_missing(api_client) -> None:
    client, workspace, *_ = api_client
    archive_root = workspace / "archive"
    create_test_image(archive_root / "keep_a.jpg")
    client.post("/api/settings/roots", json={"path": str(archive_root)})
    database_path = save_duplicates_db(
        archive_root,
        [
            {
                "group_id": "stale_missing_group",
                "reason": "strict",
                "hash": "stale",
                "items": [
                    {"role": "kept", "path": "keep_a.jpg"},
                    {"role": "duplicate", "path": "already_missing.jpg"},
                ],
            },
        ],
    )

    delete_response = client.post("/api/delete", json={"relative_path": "already_missing.jpg"})
    payload = DuplicateResultRepository(database_path).load_remaining_result_page(
        offset=0,
        limit=20,
        method="strict",
    )

    assert delete_response.status_code == 200
    assert delete_response.json() == {"status": "missing", "relative_path": "already_missing.jpg"}
    assert payload is not None
    assert payload["group_count"] == 0


def test_duplicates_api_syncs_existing_recycle_records_to_remaining_count(api_client) -> None:
    client, workspace, *_ = api_client
    archive_root = workspace / "archive"
    create_test_image(archive_root / "deleted_a.jpg")
    create_test_image(archive_root / "deleted_b.jpg", color=(80, 90, 100))
    create_test_image(archive_root / "keep_a.jpg", color=(90, 100, 110))
    create_test_image(archive_root / "keep_b.jpg", color=(100, 110, 120))
    client.post("/api/settings/roots", json={"path": str(archive_root)})
    database_path = save_duplicates_db(
        archive_root,
        [
            {
                "group_id": "old_deleted_group",
                "reason": "phash",
                "hash": "deleted",
                "items": [
                    {"role": "kept", "path": "deleted_a.jpg"},
                    {"role": "duplicate", "path": "deleted_b.jpg"},
                ],
            },
            {
                "group_id": "still_remaining",
                "reason": "phash",
                "hash": "keep",
                "items": [
                    {"role": "kept", "path": "keep_a.jpg"},
                    {"role": "duplicate", "path": "keep_b.jpg"},
                ],
            },
        ],
    )
    RecycleRepository(database_path).append_record(
        timestamp="2026-05-29T10:00:00",
        root=str(archive_root),
        relative_path="deleted_b.jpg",
        deleted_to=str(archive_root / ".deleted" / "deleted_b.jpg"),
        action="deleted",
    )

    response = client.get("/api/duplicates", params={"offset": 0, "limit": 20, "method": "phash"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["group_count"] == 1
    assert payload["method_counts"] == {"phash": 1, "strict": 0}
    assert [group["group_id"] for group in payload["groups"]] == ["still_remaining"]


def test_duplicates_api_restore_updates_remaining_group_count(api_client) -> None:
    client, workspace, *_ = api_client
    archive_root = workspace / "archive"
    create_test_image(archive_root / "restore_a.jpg")
    create_test_image(archive_root / "restore_b.jpg", color=(80, 90, 100))
    client.post("/api/settings/roots", json={"path": str(archive_root)})
    database_path = save_duplicates_db(
        archive_root,
        [
            {
                "group_id": "restored_group",
                "reason": "strict",
                "hash": "restore",
                "items": [
                    {"role": "kept", "path": "restore_a.jpg"},
                    {"role": "duplicate", "path": "restore_b.jpg"},
                ],
            },
        ],
    )

    delete_response = client.post("/api/delete", json={"relative_path": "restore_b.jpg"})
    after_delete_response = client.get("/api/duplicates", params={"offset": 0, "limit": 20, "method": "strict"})
    restore_response = client.post(
        "/api/recycle-bin/restore",
        json={"deleted_to": delete_response.json()["deleted_to"]},
    )
    after_restore_response = client.get("/api/duplicates", params={"offset": 0, "limit": 20, "method": "strict"})

    assert delete_response.status_code == 200
    assert after_delete_response.status_code == 200
    assert after_delete_response.json()["group_count"] == 0
    assert restore_response.status_code == 200
    assert after_restore_response.status_code == 200
    payload = after_restore_response.json()
    assert payload["database_path"] == str(database_path)
    assert payload["group_count"] == 1
    assert [group["group_id"] for group in payload["groups"]] == ["restored_group"]


def test_duplicates_api_filters_strict_cross_type_groups(api_client) -> None:
    client, workspace, *_ = api_client
    archive_root = workspace / "archive"
    create_test_image(archive_root / "same.jpg")
    create_test_image(archive_root / "same.jpeg", color=(32, 96, 160))
    create_test_image(archive_root / "sidecar.aae")
    create_test_image(archive_root / "sidecar.jpg", color=(90, 120, 45))
    create_test_image(archive_root / "clip.mov")
    create_test_image(archive_root / "clip.jpg", color=(80, 90, 100))

    client.post("/api/settings/roots", json={"path": str(archive_root)})
    save_duplicates_db(
        archive_root,
        [
            {
                "group_id": "jpg-jpeg",
                "reason": "strict",
                "hash": "same-image",
                "items": [
                    {"role": "kept", "path": "same.jpg"},
                    {"role": "duplicate", "path": "same.jpeg"},
                ],
            },
            {
                "group_id": "aae-jpg",
                "reason": "strict",
                "hash": "sidecar",
                "items": [
                    {"role": "kept", "path": "sidecar.aae"},
                    {"role": "duplicate", "path": "sidecar.jpg"},
                ],
            },
            {
                "group_id": "mov-jpg",
                "reason": "strict",
                "hash": "movie",
                "items": [
                    {"role": "kept", "path": "clip.mov"},
                    {"role": "duplicate", "path": "clip.jpg"},
                ],
            },
        ],
    )

    response = client.get("/api/duplicates", params={"method": "strict"})

    assert response.status_code == 200
    payload = response.json()
    assert [group["group_id"] for group in payload["groups"]] == ["jpg-jpeg"]
    assert payload["groups"][0]["preview_paths"] == ["same.jpg", "same.jpeg"]


def test_rebuild_duplicates_ignores_strict_cross_type_hashes(api_client) -> None:
    _, workspace, image_root, _ = api_client
    jpg = create_test_image(image_root / "same.jpg")
    jpeg = create_test_image(image_root / "same.jpeg")
    aae = create_test_image(image_root / "sidecar.aae")
    sidecar_jpg = create_test_image(image_root / "sidecar.jpg")
    mov = create_test_image(image_root / "clip.mov")
    clip_jpg = create_test_image(image_root / "clip.jpg")
    database_path = RootContext.from_root(image_root, ztb_app.ROOT_DATA_DIR).database_path

    stats = rebuild_duplicate_results_from_hash_db(
        str(image_root),
        "",
        {
            "phash": {},
            "strict": {
                "same-image": [str(jpg), str(jpeg)],
                "sidecar": [str(aae), str(sidecar_jpg)],
                "movie": [str(mov), str(clip_jpg)],
            },
        },
        "strict",
        sqlite_db_path=str(database_path),
    )

    assert stats["duplicate_group_count"] == 1
    payload = DuplicateResultRepository(database_path).load_result()
    assert payload is not None
    assert [group["hash"] for group in payload["groups"]] == ["same-image"]


def test_duplicates_api_reports_unavailable_when_no_result_exists(api_client) -> None:
    client, _, image_root, _ = api_client

    response = client.get("/api/duplicates")

    assert response.status_code == 200
    assert response.json() == {
        "available": False,
        "generated_at": None,
        "destination_root": "",
        "active_root": str(image_root),
        "active_root_matches": False,
        "groups": [],
        "group_count": 0,
    }


def test_duplicates_api_rebuilds_dirty_results_from_hash_db(api_client) -> None:
    client, workspace, *_ = api_client
    archive_root = workspace / "archive"
    kept = create_test_image(archive_root / "same.jpg")
    duplicate = create_test_image(archive_root / "same_copy.jpg", color=(160, 96, 32))
    client.post("/api/settings/roots", json={"path": str(archive_root)})

    database_path = RootContext.from_root(archive_root, ztb_app.ROOT_DATA_DIR).database_path
    HashDbRepository(database_path).save_hash_db(
        {"phash": {}, "strict": {"strict-hash": [str(kept), str(duplicate)]}},
        source_path=database_path,
    )
    repository = DuplicateResultRepository(database_path)
    repository.mark_dirty(archive_root, "phone_sync_upload")

    response = client.get("/api/duplicates")

    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is True
    assert payload["dirty"] is False
    assert payload["destination_root"] == str(archive_root)
    assert payload["group_count"] == 1
    assert payload["groups"][0]["reason"] == "strict"
    assert payload["groups"][0]["preview_paths"] == ["same.jpg", "same_copy.jpg"]
    assert DuplicateResultRepository(database_path).load_summary()["dirty"] is False


def test_duplicates_api_prefers_result_matching_active_root(api_client) -> None:
    client, workspace, _, _ = api_client
    archive_a = workspace / "archive_a"
    archive_b = workspace / "archive_b"
    create_test_image(archive_a / "a.jpg")
    create_test_image(archive_a / "a_dup1.jpg", color=(10, 20, 30))
    create_test_image(archive_b / "b.jpg")
    create_test_image(archive_b / "b_dup1.jpg", color=(40, 50, 60))

    client.post("/api/settings/roots", json={"path": str(archive_a)})
    client.post("/api/settings/roots", json={"path": str(archive_b)})
    client.post("/api/settings/active-root", json={"path": str(archive_a)})

    save_duplicates_db(
        archive_a,
        [
            {
                "group_id": "dup_a",
                "reason": "strict",
                "hash": "hash_a",
                "kept_path": "a.jpg",
                "items": [
                    {"role": "kept", "path": "a.jpg"},
                    {"role": "duplicate", "path": "a_dup1.jpg"},
                ],
            },
        ],
    )
    save_duplicates_db(
        archive_b,
        [
            {
                "group_id": "dup_b",
                "reason": "strict",
                "hash": "hash_b",
                "kept_path": "b.jpg",
                "items": [
                    {"role": "kept", "path": "b.jpg"},
                    {"role": "duplicate", "path": "b_dup1.jpg"},
                ],
            },
        ],
    )
    response = client.get("/api/duplicates")

    assert response.status_code == 200
    payload = response.json()
    assert payload["destination_root"] == str(archive_a)
    assert payload["database_path"]
    assert payload["group_count"] == 1
    assert payload["groups"][0]["group_id"] == "dup_a"


def test_duplicates_api_ignores_latest_result_for_different_active_root(api_client) -> None:
    client, workspace, image_root, _ = api_client
    other_root = workspace / "other_archive"
    other_root.mkdir()
    create_test_image(other_root / "same.jpg")
    create_test_image(other_root / "same_dup1.jpg", color=(10, 20, 30))

    save_duplicates_db(
        other_root,
        [
            {
                "group_id": "other_dup",
                "reason": "strict",
                "hash": "hash-other",
                "kept_path": "same.jpg",
                "items": [
                    {"role": "kept", "path": "same.jpg"},
                    {"role": "duplicate", "path": "same_dup1.jpg"},
                ],
            },
        ],
    )

    response = client.get("/api/duplicates")

    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is False
    assert payload["active_root"] == str(image_root)
    assert payload["destination_root"] == ""
