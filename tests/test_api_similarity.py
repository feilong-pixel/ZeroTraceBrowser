# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path

from MediaArchiveOrganizer.core.duplicate_detector import compute_phash
from core.domain.root_context import RootContext
from core.storage.duplicates_repository import DuplicateResultRepository
from core.storage.hash_db_repository import HashDbRepository
from tests.test_api_user_flow import create_test_image

import app as ztb_app


def save_phash_records(root: Path, paths: list[Path]) -> None:
    records: dict[str, list[str]] = {}
    for path in paths:
        phash = compute_phash(str(path))
        assert phash is not None
        records.setdefault(phash, []).append(str(path))

    database_path = RootContext.from_root(root, ztb_app.ROOT_DATA_DIR).database_path
    HashDbRepository(database_path).save_hash_db({"phash": records, "strict": {}}, source_path=database_path)


def save_duplicate_groups(root: Path, groups: list[dict]) -> None:
    database_path = RootContext.from_root(root, ztb_app.ROOT_DATA_DIR).database_path
    DuplicateResultRepository(database_path).save_result(
        {
            "generated_at": "2026-05-22T12:00:00",
            "destination_root": str(root),
            "group_count": len(groups),
            "groups": groups,
        },
        source_path=database_path,
    )


def test_similarity_search_returns_phash_matches_for_selected_image(api_client) -> None:
    client, _, image_root, _ = api_client
    query = create_test_image(image_root / "query.jpg", color=(32, 96, 160))
    match = create_test_image(image_root / "match.jpg", color=(32, 96, 160))
    other = create_test_image(image_root / "other.jpg", color=(160, 32, 96))
    save_phash_records(image_root, [query, match, other])

    response = client.post(
        "/api/similarity/search",
        json={"relative_path": "query.jpg", "method": "phash", "threshold": 0, "limit": 10},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["method"] == "phash"
    assert payload["count"] == 1
    assert payload["items"][0]["relative_path"] == "match.jpg"
    assert payload["items"][0]["distance"] == 0


def test_similarity_search_rejects_unsupported_method(api_client) -> None:
    client, _, image_root, _ = api_client
    create_test_image(image_root / "query.jpg")

    response = client.post(
        "/api/similarity/search",
        json={"relative_path": "query.jpg", "method": "embedding"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported similarity method"


def test_similarity_search_accepts_absolute_query_path_inside_root(api_client) -> None:
    client, _, image_root, _ = api_client
    query = create_test_image(image_root / "query.jpg", color=(32, 96, 160))
    match = create_test_image(image_root / "match.jpg", color=(32, 96, 160))
    save_phash_records(image_root, [query, match])

    response = client.post(
        "/api/similarity/search",
        json={"relative_path": str(query), "method": "phash", "threshold": 0, "limit": 10},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "query.jpg"
    assert payload["items"][0]["relative_path"] == "match.jpg"


def test_similarity_search_accepts_unique_filename_inside_root(api_client) -> None:
    client, _, image_root, _ = api_client
    query = create_test_image(image_root / "2010" / "03" / "20100312-093757_dup7.jpg", color=(32, 96, 160))
    match = create_test_image(image_root / "2010" / "03" / "match.jpg", color=(32, 96, 160))
    save_phash_records(image_root, [query, match])

    response = client.post(
        "/api/similarity/search",
        json={"relative_path": "20100312-093757_dup7.jpg", "method": "phash", "threshold": 0, "limit": 10},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "2010/03/20100312-093757_dup7.jpg"
    assert payload["items"][0]["relative_path"] == "2010/03/match.jpg"


def test_similarity_search_rejects_ambiguous_filename(api_client) -> None:
    client, _, image_root, _ = api_client
    create_test_image(image_root / "a" / "same.jpg")
    create_test_image(image_root / "b" / "same.jpg")

    response = client.post(
        "/api/similarity/search",
        json={"relative_path": "same.jpg", "method": "phash"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Multiple images matched filename. Use a relative path: same.jpg"


def test_similarity_search_supplements_missing_hash_db_records_from_query_directory(api_client) -> None:
    client, _, image_root, _ = api_client
    query = create_test_image(image_root / "2010" / "03" / "12" / "query_dup7.jpg", color=(32, 96, 160))
    match_one = create_test_image(image_root / "2010" / "03" / "12" / "query.jpg", color=(32, 96, 160))
    match_two = create_test_image(image_root / "2010" / "03" / "12" / "query_dup8.jpg", color=(32, 96, 160))
    outside = create_test_image(image_root / "other" / "outside.jpg", color=(32, 96, 160))
    save_phash_records(image_root, [query, outside])

    response = client.post(
        "/api/similarity/search",
        json={"relative_path": "query_dup7.jpg", "method": "phash", "threshold": 0, "limit": 10},
    )

    assert response.status_code == 200
    paths = {item["relative_path"] for item in response.json()["items"]}
    assert paths == {
        "2010/03/12/query.jpg",
        "2010/03/12/query_dup8.jpg",
        "other/outside.jpg",
    }


def test_similarity_search_includes_existing_duplicate_group_matches(api_client) -> None:
    client, _, image_root, _ = api_client
    query = create_test_image(image_root / "query.jpg", color=(32, 96, 160))
    duplicate = create_test_image(image_root / "elsewhere" / "query_dup1.jpg", color=(160, 32, 96))
    save_phash_records(image_root, [query])
    save_duplicate_groups(
        image_root,
        [
            {
                "group_id": "dup-known",
                "reason": "strict",
                "hash": "known-duplicate",
                "kept_path": "query.jpg",
                "items": [
                    {"role": "kept", "path": "query.jpg"},
                    {"role": "duplicate", "path": "elsewhere/query_dup1.jpg"},
                ],
            },
        ],
    )

    response = client.post(
        "/api/similarity/search",
        json={"relative_path": "query.jpg", "method": "phash", "threshold": 0, "limit": 10},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["items"][0]["relative_path"] == "elsewhere/query_dup1.jpg"
    assert payload["items"][0]["reason"] == "duplicates:strict"
    assert payload["items"][0]["source"] == "duplicates"
