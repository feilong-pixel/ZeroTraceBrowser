# SPDX-License-Identifier: MIT

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any, TypeVar

from .media_policy import is_supported_media_filename, strict_extension_key


T = TypeVar("T")


def group_strict_duplicate_paths(paths: Iterable[str]) -> list[list[str]]:
    paths_by_extension: dict[str, list[str]] = {}
    for path in paths:
        if not is_supported_media_filename(path):
            continue
        extension_key = strict_extension_key(path)
        paths_by_extension.setdefault(extension_key, []).append(path)
    return [group for group in paths_by_extension.values() if len(group) >= 2]


def largest_strict_compatible_items(
    items: Sequence[T],
    *,
    path_getter: Callable[[T], str],
) -> list[T]:
    items_by_extension: dict[str, list[T]] = {}
    for item in items:
        path = path_getter(item)
        if not is_supported_media_filename(path):
            continue
        extension_key = strict_extension_key(path)
        items_by_extension.setdefault(extension_key, []).append(item)

    compatible_groups = [group for group in items_by_extension.values() if len(group) >= 2]
    if not compatible_groups:
        return []
    return max(compatible_groups, key=len)


def largest_strict_compatible_item_dicts(items: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return largest_strict_compatible_items(
        items,
        path_getter=lambda item: str(item.get("path", "")),
    )
