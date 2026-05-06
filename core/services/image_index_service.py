# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from core.services.file_operations import replace_with_retry

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
    cache_path = image_index_summary_path(index_dir, cache_key)
    try:
        with cache_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return [], None, None

    items = payload.get("items", [])
    if not isinstance(items, list):
        return [], None, None

    total = payload.get("total")
    generated_at = payload.get("generated_at")
    return [
        item
        for item in items
        if isinstance(item, dict)
        and isinstance(item.get("relative_path"), str)
        and isinstance(item.get("name"), str)
    ], total if isinstance(total, int) else None, generated_at if isinstance(generated_at, str) else None


def load_image_index_summary_metadata(
    index_dir: Path,
    cache_key: tuple[str, tuple[str, ...], tuple[str, ...]],
) -> dict[str, Any]:
    cache_path = image_index_summary_path(index_dir, cache_key)
    try:
        with cache_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {"items": [], "total": None, "generated_at": None, "duplicate_group_count": None}

    items = payload.get("items", [])
    if not isinstance(items, list):
        items = []

    total = payload.get("total")
    generated_at = payload.get("generated_at")
    duplicate_group_count = payload.get("duplicate_group_count")
    return {
        "items": items,
        "total": total if isinstance(total, int) else None,
        "generated_at": generated_at if isinstance(generated_at, str) else None,
        "duplicate_group_count": duplicate_group_count if isinstance(duplicate_group_count, int) else None,
    }


def load_full_image_index_cache(
    index_dir: Path,
    cache_key: tuple[str, tuple[str, ...], tuple[str, ...]],
) -> list[dict[str, Any]]:
    cache_path = image_index_cache_path(index_dir, cache_key)
    try:
        with cache_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return []

    items = payload.get("items", [])
    if not isinstance(items, list):
        return []

    return [
        item
        for item in items
        if isinstance(item, dict)
        and isinstance(item.get("relative_path"), str)
        and isinstance(item.get("name"), str)
    ]


def load_timeline_index_cache(
    index_dir: Path,
    cache_key: tuple[str, tuple[str, ...], tuple[str, ...]],
) -> tuple[list[dict[str, str]], str | None]:
    cache_path = timeline_index_cache_path(index_dir, cache_key)
    try:
        with cache_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return [], None

    entries = payload.get("entries", [])
    if not isinstance(entries, list):
        return [], None

    generated_at = payload.get("generated_at")
    return [
        entry
        for entry in entries
        if isinstance(entry, dict)
        and isinstance(entry.get("key"), str)
        and isinstance(entry.get("label"), str)
        and isinstance(entry.get("index_label"), str)
    ], generated_at if isinstance(generated_at, str) else None


def save_image_index_cache(
    index_dir: Path,
    cache_key: tuple[str, tuple[str, ...], tuple[str, ...]],
    items: list[dict[str, Any]],
) -> None:
    index_dir.mkdir(parents=True, exist_ok=True)
    cache_path = image_index_cache_path(index_dir, cache_key)
    payload = {
        "generated_at": datetime.now().isoformat(),
        "root": cache_key[0],
        "items": items,
    }
    temp_path = cache_path.with_name(f"{cache_path.name}.{threading.get_ident()}.tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
    replace_with_retry(temp_path, cache_path)

    save_image_index_summary(
        index_dir,
        cache_key,
        items[:IMAGE_INDEX_PREVIEW_LIMIT],
        len(items),
        payload["generated_at"],
    )
    save_timeline_index_cache(index_dir, cache_key, items, payload["generated_at"])


def save_image_index_summary(
    index_dir: Path,
    cache_key: tuple[str, tuple[str, ...], tuple[str, ...]],
    items: list[dict[str, Any]],
    total: int | None,
    generated_at: str | None = None,
    duplicate_group_count: int | None = None,
) -> None:
    index_dir.mkdir(parents=True, exist_ok=True)
    summary_path = image_index_summary_path(index_dir, cache_key)
    existing_metadata = load_image_index_summary_metadata(index_dir, cache_key)
    summary_payload = {
        "generated_at": generated_at or existing_metadata.get("generated_at") or datetime.now().isoformat(),
        "root": cache_key[0],
        "total": total,
        "duplicate_group_count": duplicate_group_count if isinstance(duplicate_group_count, int) else existing_metadata.get("duplicate_group_count"),
        "items": items,
    }
    summary_temp_path = summary_path.with_name(f"{summary_path.name}.{threading.get_ident()}.tmp")
    with summary_temp_path.open("w", encoding="utf-8") as handle:
        json.dump(summary_payload, handle, ensure_ascii=False)
    replace_with_retry(summary_temp_path, summary_path)


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
) -> None:
    index_dir.mkdir(parents=True, exist_ok=True)
    cache_path = timeline_index_cache_path(index_dir, cache_key)
    payload = {
        "generated_at": generated_at or datetime.now().isoformat(),
        "root": cache_key[0],
        "entries": build_timeline_index_entries(items),
    }
    temp_path = cache_path.with_name(f"{cache_path.name}.{threading.get_ident()}.tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
    replace_with_retry(temp_path, cache_path)
