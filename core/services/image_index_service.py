# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

from core.storage.image_index_repository import ImageIndexRepository

IMAGE_INDEX_PREVIEW_LIMIT = 240


def image_scan_cache_key(
    root: Path,
    supported_extensions: set[str],
    excluded_scan_dirs: set[str],
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    return (
        str(root.resolve()),
        tuple(sorted(supported_extensions)),
        tuple(sorted(excluded_scan_dirs)),
    )


def digest_for_cache_key(cache_key: tuple[str, tuple[str, ...], tuple[str, ...]]) -> str:
    return hashlib.sha1("|".join([cache_key[0], *cache_key[1], *cache_key[2]]).encode("utf-8")).hexdigest()


def image_index_cache_path(
    index_dir: Path,
    cache_key: tuple[str, tuple[str, ...], tuple[str, ...]],
) -> Path:
    return index_dir / f"{digest_for_cache_key(cache_key)}.json"


def image_index_summary_path(
    index_dir: Path,
    cache_key: tuple[str, tuple[str, ...], tuple[str, ...]],
) -> Path:
    return index_dir / f"{digest_for_cache_key(cache_key)}.summary.json"


def timeline_index_cache_path(
    index_dir: Path,
    cache_key: tuple[str, tuple[str, ...], tuple[str, ...]],
) -> Path:
    return index_dir / f"{digest_for_cache_key(cache_key)}.timeline.json"


def database_path_for_index_dir(index_dir: Path) -> Path | None:
    if index_dir.name != "indexes":
        return None
    return index_dir.parent / "workspace.sqlite3"


def image_index_repository(index_dir: Path, *, ensure_schema: bool = True) -> ImageIndexRepository | None:
    database_path = database_path_for_index_dir(index_dir)
    return ImageIndexRepository(database_path, ensure_schema=ensure_schema) if database_path is not None else None


def get_image_timestamp_for_sort(item: dict[str, Any]) -> float | None:
    timestamp = item.get("timeline_ts")
    if isinstance(timestamp, int | float):
        return float(timestamp)
    return None


def timeline_group_key_for_item(item: dict[str, Any]) -> str:
    timeline_time = str(item.get("timeline_time", "")).strip()
    if (
        len(timeline_time) >= 7
        and timeline_time[4] == "-"
        and timeline_time[:4].isdigit()
        and timeline_time[5:7].isdigit()
    ):
        month = int(timeline_time[5:7])
        if 1 <= month <= 12:
            return timeline_time[:7]

    timestamp = get_image_timestamp_for_sort(item)
    if timestamp is None:
        return "unknown"

    date = datetime.fromtimestamp(timestamp)
    return f"{date.year:04d}-{date.month:02d}"


def timeline_group_label_from_key(group_key: str) -> str:
    return "Unknown date" if group_key == "unknown" else group_key


def timeline_tick_label_from_key(group_key: str) -> str:
    return "Unknown" if group_key == "unknown" else group_key.replace("-", "")


def build_timeline_index_entries(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    group_keys = {timeline_group_key_for_item(item) for item in items}

    def group_sort_key(group_key: str) -> tuple[int, str]:
        if group_key == "unknown":
            return (1, group_key)
        return (0, group_key)

    entries = []
    for group_key in sorted(group_keys, key=group_sort_key, reverse=True):
        entries.append(
            {
                "key": group_key,
                "label": timeline_group_label_from_key(group_key),
                "index_label": timeline_tick_label_from_key(group_key),
            }
        )

    return entries


def load_image_index_cache(
    index_dir: Path,
    cache_key: tuple[str, tuple[str, ...], tuple[str, ...]],
) -> tuple[list[dict[str, Any]], int | None, str | None]:
    repository = image_index_repository(index_dir, ensure_schema=False)
    if repository is None:
        return [], None, None

    summary = repository.load_summary(digest_for_cache_key(cache_key))
    if summary is None:
        return [], None, None

    items = summary.get("items", [])
    return (
        items if isinstance(items, list) else [],
        summary.get("total") if isinstance(summary.get("total"), int) else None,
        summary.get("generated_at") if isinstance(summary.get("generated_at"), str) else None,
    )


def load_image_index_summary_metadata(
    index_dir: Path,
    cache_key: tuple[str, tuple[str, ...], tuple[str, ...]],
) -> dict[str, Any]:
    repository = image_index_repository(index_dir, ensure_schema=False)
    if repository is None:
        return {"items": [], "total": None, "generated_at": None, "duplicate_group_count": None}

    summary = repository.load_summary(digest_for_cache_key(cache_key))
    if summary is None:
        return {"items": [], "total": None, "generated_at": None, "duplicate_group_count": None}
    items = summary.get("items", [])
    return {
        "items": items if isinstance(items, list) else [],
        "total": summary.get("total") if isinstance(summary.get("total"), int) else None,
        "generated_at": summary.get("generated_at") if isinstance(summary.get("generated_at"), str) else None,
        "duplicate_group_count": summary.get("duplicate_group_count") if isinstance(summary.get("duplicate_group_count"), int) else None,
    }


def load_full_image_index_cache(
    index_dir: Path,
    cache_key: tuple[str, tuple[str, ...], tuple[str, ...]],
) -> list[dict[str, Any]]:
    repository = image_index_repository(index_dir, ensure_schema=False)
    if repository is None:
        return []
    return repository.list_images(digest_for_cache_key(cache_key))


def load_timeline_group_image_page(
    index_dir: Path,
    cache_key: tuple[str, tuple[str, ...], tuple[str, ...]],
    group_key: str,
    *,
    offset: int = 0,
    limit: int = 300,
) -> list[dict[str, Any]]:
    repository = image_index_repository(index_dir, ensure_schema=False)
    if repository is None:
        return []
    return repository.list_images_for_timeline_group(
        digest_for_cache_key(cache_key),
        group_key,
        offset=offset,
        limit=limit,
    )


def find_timeline_neighbor_group(
    index_dir: Path,
    cache_key: tuple[str, tuple[str, ...], tuple[str, ...]],
    group_key: str,
    direction: str,
) -> str | None:
    repository = image_index_repository(index_dir, ensure_schema=False)
    if repository is None:
        return None
    return repository.find_timeline_neighbor_group(
        digest_for_cache_key(cache_key),
        group_key,
        direction,
    )


def load_timeline_index_cache(
    index_dir: Path,
    cache_key: tuple[str, tuple[str, ...], tuple[str, ...]],
) -> tuple[list[dict[str, str]], str | None]:
    repository = image_index_repository(index_dir, ensure_schema=False)
    if repository is None:
        return [], None

    digest = digest_for_cache_key(cache_key)
    entries = repository.load_timeline_entries(digest)
    metadata = repository.load_metadata(digest)
    if not entries and metadata is None:
        return [], None
    generated_at = metadata.get("timeline_generated_at") if metadata else None
    return entries, generated_at if isinstance(generated_at, str) else None


def save_image_index_cache(
    index_dir: Path,
    cache_key: tuple[str, tuple[str, ...], tuple[str, ...]],
    items: list[dict[str, Any]],
) -> None:
    generated_at = datetime.now().isoformat()
    repository = image_index_repository(index_dir)
    if repository is None:
        return

    repository.save_index(
        digest_for_cache_key(cache_key),
        root=cache_key[0],
        items=items,
        total=len(items),
        generated_at=generated_at,
        timeline_entries=build_timeline_index_entries(items),
    )


def save_image_index_summary(
    index_dir: Path,
    cache_key: tuple[str, tuple[str, ...], tuple[str, ...]],
    items: list[dict[str, Any]],
    total: int | None,
    generated_at: str | None = None,
    duplicate_group_count: int | None = None,
) -> None:
    existing_metadata = load_image_index_summary_metadata(index_dir, cache_key)
    summary_payload = {
        "generated_at": generated_at or existing_metadata.get("generated_at") or datetime.now().isoformat(),
        "root": cache_key[0],
        "total": total if isinstance(total, int) else existing_metadata.get("total"),
        "duplicate_group_count": duplicate_group_count if isinstance(duplicate_group_count, int) else existing_metadata.get("duplicate_group_count"),
        "items": items,
    }
    repository = image_index_repository(index_dir)
    if repository is None:
        return

    digest = digest_for_cache_key(cache_key)
    stored_items = repository.list_images(digest)
    persisted_items = items
    if stored_items and (not isinstance(total, int) or len(items) < len(stored_items)):
        persisted_items = stored_items
    repository.save_index(
        digest,
        root=cache_key[0],
        items=persisted_items,
        total=summary_payload["total"],
        generated_at=summary_payload["generated_at"],
        duplicate_group_count=summary_payload["duplicate_group_count"],
        timeline_entries=None,
        delete_missing_items=False,
    )


def save_image_index_summary_metadata(
    index_dir: Path,
    root: Path,
    supported_extensions: set[str],
    excluded_scan_dirs: set[str],
    total: int | None = None,
    duplicate_group_count: int | None = None,
    generated_at: str | None = None,
) -> None:
    cache_key = image_scan_cache_key(root, supported_extensions, excluded_scan_dirs)
    metadata = load_image_index_summary_metadata(index_dir, cache_key)
    save_image_index_summary(
        index_dir,
        cache_key,
        metadata["items"] if isinstance(metadata.get("items"), list) else [],
        total if isinstance(total, int) else metadata.get("total"),
        generated_at or metadata.get("generated_at"),
        duplicate_group_count if isinstance(duplicate_group_count, int) else metadata.get("duplicate_group_count"),
    )


def save_timeline_index_cache(
    index_dir: Path,
    cache_key: tuple[str, tuple[str, ...], tuple[str, ...]],
    items: list[dict[str, Any]],
    generated_at: str | None = None,
    delete_missing: bool = True,
) -> None:
    repository = image_index_repository(index_dir)
    if repository is None:
        return

    digest = digest_for_cache_key(cache_key)
    repository.replace_timeline_entries(
        digest,
        root=cache_key[0],
        generated_at=generated_at or datetime.now().isoformat(),
        entries=build_timeline_index_entries(items),
        delete_missing=delete_missing,
    )
