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
from MediaArchiveOrganizer.services.organizer import rebuild_duplicate_results_from_hash_db


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


def test_duplicates_api_does_not_check_skipped_pages(api_client, monkeypatch) -> None:
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
    resolved_paths: list[str] = []
    original_resolve_under_root = duplicates_context.resolve_under_root

    def record_resolved_path(root: Path, candidate: str) -> Path:
        resolved_paths.append(candidate)
        return original_resolve_under_root(root, candidate)

    monkeypatch.setattr(duplicates_context, "resolve_under_root", record_resolved_path)

    response = client.get("/api/duplicates", params={"offset": 3, "limit": 1, "method": "strict"})

    assert response.status_code == 200
    payload = response.json()
    assert [group["group_id"] for group in payload["groups"]] == ["dup_0003"]
    assert resolved_paths == [
        "kept_3.jpg",
        "kept_3_dup1.jpg",
        "kept_4.jpg",
        "kept_4_dup1.jpg",
    ]


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
