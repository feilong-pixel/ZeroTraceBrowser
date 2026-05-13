# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
from pathlib import Path

from tests.test_api_user_flow import create_test_image

import app as ztb_app
import core.context as ztb_context
from core.domain.root_context import RootContext
from core.storage.duplicates_repository import DuplicateResultRepository


def write_duplicates_json(path: Path, destination_root: Path, groups: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "generated_at": "2026-04-23T12:34:56",
                "destination_root": str(destination_root),
                "group_count": len(groups),
                "groups": groups,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


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
    assert payload["json_path"] == ""
    assert payload["database_path"] == str(database_path)
    assert payload["destination_root"] == str(archive_root)
    assert payload["active_root_matches"] is True
    assert payload["group_count"] == 1
    assert len(payload["groups"]) == 1

    group = payload["groups"][0]
    assert group["group_id"] == "dup_0001"
    assert group["reason"] == "strict"
    assert group["hash"] == "abc123"
    assert group["item_count"] == 4
    assert group["available_count"] == 2
    assert group["preview_paths"] == [
        "2026/04/23/kept.jpg",
        "2026/04/23/kept_dup1.jpg",
    ]
    assert group["items"] == [
        {"role": "kept", "path": "2026/04/23/kept.jpg", "exists": True},
        {"role": "duplicate", "path": "2026/04/23/kept_dup1.jpg", "exists": True},
        {"role": "duplicate", "path": "2026/04/23/missing.jpg", "exists": False},
        {"role": "duplicate", "path": "../outside.jpg", "exists": False},
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


def test_duplicates_api_reports_unavailable_when_no_result_exists(api_client) -> None:
    client, _, image_root, _ = api_client

    response = client.get("/api/duplicates")

    assert response.status_code == 200
    assert response.json() == {
        "available": False,
        "json_path": "",
        "generated_at": None,
        "destination_root": "",
        "active_root": str(image_root),
        "active_root_matches": False,
        "groups": [],
        "group_count": 0,
    }


def test_duplicates_api_migrates_legacy_json_to_database(api_client) -> None:
    client, workspace, *_ = api_client
    archive_root = workspace / "archive"
    create_test_image(archive_root / "same.jpg")
    create_test_image(archive_root / "same_dup1.jpg", color=(10, 20, 30))
    client.post("/api/settings/roots", json={"path": str(archive_root)})

    legacy_path = write_duplicates_json(
        ztb_context.root_duplicates_path(archive_root),
        archive_root,
        [
            {
                "group_id": "legacy_dup",
                "reason": "strict",
                "hash": "legacy-hash",
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
    database_path = RootContext.from_root(archive_root, ztb_app.ROOT_DATA_DIR).database_path
    assert payload["json_path"] == ""
    assert payload["database_path"] == str(database_path)
    assert payload["groups"][0]["group_id"] == "legacy_dup"
    assert DuplicateResultRepository(database_path).load_summary()["source_path"] == str(legacy_path)


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
    assert payload["json_path"] == ""
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
