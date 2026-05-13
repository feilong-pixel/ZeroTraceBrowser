# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path

from MediaArchiveOrganizer.core.duplicate_detector import compute_phash
from core.domain.root_context import RootContext
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
