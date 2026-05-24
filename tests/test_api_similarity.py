# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from MediaArchiveOrganizer.core.duplicate_detector import compute_phash
from core.domain.root_context import RootContext
from core.storage.duplicates_repository import DuplicateResultRepository
from core.storage.hash_db_repository import HashDbRepository
from core.storage.mobile_repository import MobileRepository
from tests.test_api_user_flow import create_test_image

import app as ztb_app
import core.context_modules.similarity_context as similarity_context


def create_document_photo(path: Path, *, shift: int = 0, rotate: float = 0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (420, 560), (232, 229, 218))
    draw = ImageDraw.Draw(image)
    paper = (55 + shift, 45, 365 + shift, 505)
    draw.rectangle(paper, fill=(247, 245, 236), outline=(24, 24, 24), width=3)
    for index in range(1, 11):
        y = paper[1] + index * 38
        draw.line((paper[0], y, paper[2], y), fill=(40, 40, 40), width=2)
    for index in range(1, 5):
        x = paper[0] + index * 62
        draw.line((x, paper[1], x, paper[3]), fill=(50, 50, 50), width=2)
    for index in range(7):
        y = paper[1] + 22 + index * 55
        draw.ellipse((paper[0] + 18, y, paper[0] + 48, y + 24), outline=(170, 30, 30), width=4)
        draw.text((paper[0] + 88, y - 2), "S", fill=(25, 45, 150))
        draw.text((paper[2] - 92, y - 4), "14:00", fill=(180, 40, 40))
    if rotate:
        image = image.rotate(rotate, expand=True, fillcolor=(45, 43, 40))
    image.save(path)
    return path


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


def save_mobile_records(root: Path, records: list[dict]) -> None:
    database_path = RootContext.from_root(root, ztb_app.ROOT_DATA_DIR).database_path
    repository = MobileRepository(database_path)
    repository.save_index(
        device_type="iphone",
        device_id="Apple iPhone",
        device_name="Apple iPhone",
        indexed_at="2026-05-22T12:00:00+00:00",
        records=records,
    )
    for record in records:
        if record.get("local_path"):
            repository.mark_imported(
                device_type="iphone",
                device_id="Apple iPhone",
                album=record["album"],
                filename=record["filename"],
                local_path=record["local_path"],
                imported_at="2026-05-22T12:00:00+00:00",
            )
        if record.get("existing_local_path"):
            repository.mark_skipped_duplicate(
                device_type="iphone",
                device_id="Apple iPhone",
                album=record["album"],
                filename=record["filename"],
                existing_local_path=record["existing_local_path"],
                imported_at="2026-05-22T12:00:00+00:00",
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


def test_similarity_search_document_method_matches_form_layout_photos(api_client) -> None:
    client, _, image_root, _ = api_client
    query = create_document_photo(image_root / "2026" / "05" / "22" / "IMG_4394.jpeg")
    match_one = create_document_photo(image_root / "2026" / "05" / "21" / "IMG_4392.jpeg", shift=-18, rotate=3)
    match_two = create_document_photo(image_root / "2026" / "05" / "21" / "IMG_4393.jpeg", shift=12, rotate=-2)
    create_test_image(image_root / "other.jpg", color=(160, 32, 96))
    save_phash_records(image_root, [query, match_one, match_two])

    response = client.post(
        "/api/similarity/search",
        json={
            "relative_path": "IMG_4394.jpeg",
            "method": "document",
            "threshold": 96,
            "limit": 10,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    paths = {item["relative_path"] for item in payload["items"]}
    assert payload["method"] == "document"
    assert paths == {
        "2026/05/21/IMG_4392.jpeg",
        "2026/05/21/IMG_4393.jpeg",
    }
    assert all(item["source"] == "document" for item in payload["items"])


def test_similarity_search_feature_method_ranks_orb_akaze_matches(api_client, monkeypatch) -> None:
    client, _, image_root, _ = api_client
    query = create_test_image(image_root / "query.jpg")
    close_match = create_test_image(image_root / "same-form.jpg", color=(10, 20, 30))
    far_match = create_test_image(image_root / "different.jpg", color=(200, 120, 30))
    save_phash_records(image_root, [query, close_match, far_match])

    monkeypatch.setattr(similarity_context, "_feature_descriptors", lambda path: ("orb", 20, object()))

    def fake_feature_distance(left: Path, right: Path, left_features=None):
        if right.name == "same-form.jpg":
            return 22, 0.78, "orb"
        if right.name == "different.jpg":
            return 91, 0.09, "orb"
        return None

    monkeypatch.setattr(similarity_context, "_feature_similarity_distance", fake_feature_distance)

    response = client.post(
        "/api/similarity/search",
        json={"relative_path": "query.jpg", "method": "feature", "threshold": 70, "limit": 10},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["method"] == "feature"
    assert payload["count"] == 1
    assert payload["items"][0]["relative_path"] == "same-form.jpg"
    assert payload["items"][0]["distance"] == 22
    assert payload["items"][0]["source"] == "feature"


def test_similarity_search_feature_method_uses_full_source_scope(api_client, monkeypatch) -> None:
    client, _, image_root, _ = api_client
    create_test_image(image_root / "2026" / "05" / "22" / "IMG_4394.jpeg")
    full_scope_match = create_test_image(image_root / "2026" / "05" / "21" / "IMG_4392.jpeg")
    create_test_image(image_root / "2026" / "04" / "01" / "old.jpg")
    monkeypatch.setattr(similarity_context, "_feature_descriptors", lambda path: ("orb", 20, object()))

    def fake_feature_distance(left: Path, right: Path, left_features=None):
        if right == full_scope_match:
            return 40, 0.6, "orb"
        return 95, 0.05, "orb"

    monkeypatch.setattr(similarity_context, "_feature_similarity_distance", fake_feature_distance)

    response = client.post(
        "/api/similarity/search",
        json={"relative_path": "IMG_4394.jpeg", "method": "feature", "threshold": 70, "limit": 10},
    )

    assert response.status_code == 200
    assert [item["relative_path"] for item in response.json()["items"]] == ["2026/05/21/IMG_4392.jpeg"]


def test_similarity_search_feature_method_stops_at_result_limit(api_client, monkeypatch) -> None:
    client, _, image_root, _ = api_client
    create_test_image(image_root / "query.jpg")
    create_test_image(image_root / "match_1.jpg")
    create_test_image(image_root / "match_2.jpg")
    create_test_image(image_root / "match_3.jpg")
    calls: list[str] = []
    monkeypatch.setattr(similarity_context, "_feature_descriptors", lambda path: ("orb", 20, object()))

    def fake_feature_distance(left: Path, right: Path, left_features=None):
        calls.append(right.name)
        return 40, 0.6, "orb"

    monkeypatch.setattr(similarity_context, "_feature_similarity_distance", fake_feature_distance)

    response = client.post(
        "/api/similarity/search",
        json={"relative_path": "query.jpg", "method": "feature", "threshold": 70, "limit": 2},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 2
    assert len(payload["items"]) == 2
    assert len(calls) == 2


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


def test_similarity_search_supplements_missing_hash_db_records_from_full_root(api_client) -> None:
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


def test_similarity_search_returns_indexed_iphone_matches_with_local_files(api_client) -> None:
    client, _, image_root, _ = api_client
    query = create_test_image(image_root / "mobile" / "query.jpg", color=(32, 96, 160))
    imported_match = create_test_image(image_root / "mobile" / "match.jpg", color=(32, 96, 160))
    skipped_match = create_test_image(image_root / "existing" / "same.jpg", color=(32, 96, 160))
    device_only = create_test_image(image_root / "device-only-temp.jpg", color=(32, 96, 160))
    records = [
        {
            "album": "100APPLE",
            "filename": "IMG_0001.JPG",
            "size": query.stat().st_size,
            "phash": compute_phash(str(query)),
            "local_path": str(query),
        },
        {
            "album": "100APPLE",
            "filename": "IMG_0002.JPG",
            "size": imported_match.stat().st_size,
            "phash": compute_phash(str(imported_match)),
            "local_path": str(imported_match),
        },
        {
            "album": "101APPLE",
            "filename": "IMG_0003.JPG",
            "size": skipped_match.stat().st_size,
            "phash": compute_phash(str(skipped_match)),
            "existing_local_path": str(skipped_match),
        },
        {
            "album": "102APPLE",
            "filename": "IMG_0004.JPG",
            "size": device_only.stat().st_size,
            "phash": compute_phash(str(device_only)),
        },
    ]
    save_mobile_records(image_root, records)
    device_only.unlink()

    response = client.post(
        "/api/similarity/search",
        json={"source": "iphone", "relative_path": "100APPLE/IMG_0001.JPG", "method": "phash", "threshold": 0},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "iphone"
    assert payload["query"] == "100APPLE/IMG_0001.JPG"
    paths = {item["relative_path"] for item in payload["items"]}
    assert paths == {"mobile/match.jpg", "existing/same.jpg"}
    assert {item["mobile_target"] for item in payload["items"]} == {"100APPLE/IMG_0002.JPG", "101APPLE/IMG_0003.JPG"}


def test_similarity_search_rejects_iphone_device_only_query(api_client) -> None:
    client, _, image_root, _ = api_client
    query = create_test_image(image_root / "temp.jpg", color=(32, 96, 160))
    save_mobile_records(
        image_root,
        [
            {
                "album": "100APPLE",
                "filename": "IMG_0001.JPG",
                "size": query.stat().st_size,
                "phash": compute_phash(str(query)),
            }
        ],
    )
    query.unlink()

    response = client.post(
        "/api/similarity/search",
        json={"source": "iphone", "relative_path": "100APPLE/IMG_0001.JPG", "method": "phash"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Indexed iPhone photo not found in local root: 100APPLE/IMG_0001.JPG"
