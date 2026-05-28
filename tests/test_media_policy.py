# SPDX-License-Identifier: MIT

from core.media_policy import (
    is_sidecar_filename,
    is_supported_media_filename,
    phash_eligible,
    strict_extension_key,
    strict_extensions_compatible,
)
from core.services.duplicate_result_service import (
    group_strict_duplicate_paths,
    largest_strict_compatible_item_dicts,
)


def test_supported_media_excludes_sidecars() -> None:
    assert is_supported_media_filename("IMG_0001.JPG")
    assert is_supported_media_filename("clip.MOV")
    assert not is_supported_media_filename("IMG_0001.AAE")
    assert is_sidecar_filename("IMG_0001.AAE")


def test_strict_extension_aliases_keep_jpg_and_jpeg_together() -> None:
    assert strict_extension_key("a.jpeg") == ".jpg"
    assert strict_extension_key("b.JPG") == ".jpg"
    assert strict_extensions_compatible("a.jpeg", "b.jpg")


def test_strict_extension_compatibility_rejects_cross_media_pairs() -> None:
    assert not strict_extensions_compatible("a.mov", "b.jpg")
    assert not strict_extensions_compatible("a.aae", "b.jpg")


def test_phash_is_image_only() -> None:
    assert phash_eligible("photo.jpeg")
    assert not phash_eligible("clip.mov")
    assert not phash_eligible("sidecar.aae")


def test_strict_duplicate_path_grouping_uses_shared_compatibility() -> None:
    groups = group_strict_duplicate_paths(["a.jpg", "b.jpeg"])

    assert groups == [["a.jpg", "b.jpeg"]]
    assert group_strict_duplicate_paths(["sidecar.aae", "sidecar.jpg"]) == []
    assert group_strict_duplicate_paths(["clip.mov", "clip.jpg"]) == []


def test_strict_duplicate_item_filter_uses_largest_compatible_group() -> None:
    items = [
        {"path": "a.jpg"},
        {"path": "b.jpeg"},
        {"path": "c.jpg"},
        {"path": "clip.mov"},
        {"path": "clip_copy.mov"},
    ]

    filtered = largest_strict_compatible_item_dicts(items)

    assert [item["path"] for item in filtered] == ["a.jpg", "b.jpeg", "c.jpg"]
