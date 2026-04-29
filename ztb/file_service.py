# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from fastapi import HTTPException
from fastapi.responses import FileResponse
from PIL import Image
from PIL.ExifTags import TAGS

EXIF_DATETIME_TAG_ORDER = (
    ("DateTimeOriginal",),
    ("CreateDate", "DateTimeDigitized"),
    ("ModifyDate", "DateTime"),
)
EXIF_IFD_TAG_ID = 34665
IMAGE_LIST_CACHE_TTL_SECONDS = 5.0
IMAGE_LIST_CACHE: dict[tuple[str, tuple[str, ...], tuple[str, ...]], tuple[float, list[dict[str, Any]]]] = {}
IMAGE_SCAN_CACHE: dict[tuple[str, tuple[str, ...], tuple[str, ...]], dict[str, Any]] = {}
IMAGE_SCAN_LOCK = threading.Lock()
IMAGE_INDEX_REFRESH_DELAY_SECONDS = 0.0
IMAGE_INDEX_PREVIEW_LIMIT = 240
WindowsFileTime = tuple[int, int]
WindowsFileTimes = tuple[WindowsFileTime, WindowsFileTime, WindowsFileTime]

from MediaArchiveOrganizer.core.file_transfer import transfer_file
from MediaArchiveOrganizer.core.date_classifier import get_target_date, get_target_date_with_source

def replace_with_retry(source: Path, target: Path, attempts: int = 3) -> None:
    for attempt in range(attempts):
        try:
            source.replace(target)
            return
        except PermissionError:
            if attempt >= attempts - 1:
                raise
            time.sleep(0.05 * (attempt + 1))


def copy_file_preserve_times(src: Path, dst: Path):
    transfer_file(src, dst, "copy")


def move_file_preserve_times(src: Path, dst: Path):
    transfer_file(src, dst, "move")


def resolve_under_root(root: Path, candidate: str) -> Path:
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Path escapes configured root") from exc
    return resolved


def clear_image_list_cache(root: Path | None = None) -> None:
    if root is None:
        IMAGE_LIST_CACHE.clear()
        with IMAGE_SCAN_LOCK:
            IMAGE_SCAN_CACHE.clear()
        return

    root_value = str(root.resolve())
    for cache_key in [key for key in IMAGE_LIST_CACHE if key[0] == root_value]:
        IMAGE_LIST_CACHE.pop(cache_key, None)
    with IMAGE_SCAN_LOCK:
        for cache_key in [key for key in IMAGE_SCAN_CACHE if key[0] == root_value]:
            IMAGE_SCAN_CACHE.pop(cache_key, None)


def iter_image_files(root: Path, supported_extensions: set[str], excluded_scan_dirs: set[str]) -> Iterable[Path]:
    if not root.exists():
        return []

    excluded_names = {name.lower() for name in excluded_scan_dirs}

    def directory_priority(path: Path) -> tuple[int, str]:
        name = path.name.lower()
        if name.isdigit():
            numeric = int(name)
            if 1900 <= numeric <= 2100:
                return (0, f"{9999 - numeric:04d}")
            if 1 <= numeric <= 12:
                return (1, f"{99 - numeric:02d}")
            if 1 <= numeric <= 31:
                return (2, f"{99 - numeric:02d}")
        return (3, name)

    def scan(directory: Path) -> Iterable[Path]:
        pending_dirs: deque[Path] = deque([directory])

        while pending_dirs:
            current_dir = pending_dirs.popleft()
            child_dirs: list[Path] = []

            try:
                with os.scandir(current_dir) as entries:
                    for entry in entries:
                        if entry.name.lower() in excluded_names:
                            continue

                        try:
                            if entry.is_dir(follow_symlinks=False):
                                child_dirs.append(Path(entry.path))
                                continue

                            if entry.is_file(follow_symlinks=False):
                                suffix = Path(entry.name).suffix.lower()
                                if suffix in supported_extensions:
                                    yield Path(entry.path)
                        except OSError:
                            continue
            except OSError:
                continue

            child_dirs.sort(key=directory_priority)
            pending_dirs.extendleft(reversed(child_dirs[:24]))
            pending_dirs.extend(child_dirs[24:])

    return scan(root)


def parse_exif_datetime(value: Any) -> datetime | None:
    if not value:
        return None

    if isinstance(value, bytes):
        value = value.decode(errors="ignore")

    normalized = str(value).strip()
    for pattern in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(normalized, pattern)
        except ValueError:
            continue

    return None


def preferred_exif_datetime_from_map(exif_map: dict[str, Any]) -> datetime | None:
    for aliases in EXIF_DATETIME_TAG_ORDER:
        for alias in aliases:
            parsed = parse_exif_datetime(exif_map.get(alias))
            if parsed:
                return parsed

    return None


def exif_map_from_raw(raw_exif: Any) -> dict[str, Any]:
    exif_map = {TAGS.get(tag_id, str(tag_id)): value for tag_id, value in raw_exif.items()}

    try:
        exif_ifd = raw_exif.get_ifd(EXIF_IFD_TAG_ID)
    except Exception:
        exif_ifd = {}

    exif_map.update({TAGS.get(tag_id, str(tag_id)): value for tag_id, value in exif_ifd.items()})
    return exif_map

import warnings

def read_preferred_exif_datetime(file_path: Path) -> datetime | None:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return get_target_date(file_path)
    except Exception:
        return None


def timeline_metadata_from_path(file_path: Path) -> tuple[datetime, int, str]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        target_date, target_source = get_target_date_with_source(file_path)
    return target_date, int(target_date.timestamp()), target_source


def image_metadata_from_path(root: Path, file_path: Path, include_exif: bool = True) -> dict[str, Any]:
    relative_path = file_path.relative_to(root).as_posix()
    stat = file_path.stat()
    timeline_date, timeline_ts, timeline_source = timeline_metadata_from_path(file_path)
    captured_at = timeline_date if include_exif else None
    return {
        "relative_path": relative_path,
        "path": relative_path,
        "name": file_path.name,
        "size": stat.st_size,
        "captured_at": captured_at.isoformat() if captured_at else "",
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "timeline_time": timeline_date.strftime("%Y-%m-%d %H:%M:%S"),
        "timeline_ts": timeline_ts,
        "timeline_source": timeline_source,
        "exists": True,
    }


def ensure_image_timeline_metadata(root: Path, item: dict[str, Any]) -> dict[str, Any]:
    relative_path = str(item.get("relative_path", ""))
    if (
        relative_path
        and isinstance(item.get("timeline_ts"), int)
        and str(item.get("timeline_time", "")).strip()
        and str(item.get("timeline_source", "")).strip()
    ):
        return {**item, "path": str(item.get("path") or relative_path)}

    if not relative_path:
        return item

    try:
        candidate = resolve_under_root(root, relative_path)
    except HTTPException:
        return item
    if not candidate.exists() or not candidate.is_file():
        return item

    timeline_date, timeline_ts, timeline_source = timeline_metadata_from_path(candidate)
    return {
        **item,
        "path": str(item.get("path") or relative_path),
        "timeline_time": timeline_date.strftime("%Y-%m-%d %H:%M:%S"),
        "timeline_ts": timeline_ts,
        "timeline_source": timeline_source,
    }


def with_image_exists(root: Path, item: dict[str, Any]) -> dict[str, Any]:
    relative_path = str(item.get("relative_path", ""))
    exists = False
    if relative_path:
        try:
            candidate = resolve_under_root(root, relative_path)
            exists = candidate.exists() and candidate.is_file()
        except HTTPException:
            exists = False
    enriched = ensure_image_timeline_metadata(root, item) if exists else item
    return {**enriched, "exists": exists}


def image_item_exists(root: Path, item: dict[str, Any]) -> bool:
    return bool(with_image_exists(root, item)["exists"])


def list_lightweight_image_metadata(
    root: Path,
    supported_extensions: set[str],
    excluded_scan_dirs: set[str],
) -> list[dict[str, Any]]:
    cache_key = (
        str(root.resolve()),
        tuple(sorted(supported_extensions)),
        tuple(sorted(excluded_scan_dirs)),
    )
    now = time.monotonic()
    cached = IMAGE_LIST_CACHE.get(cache_key)
    if cached and now - cached[0] <= IMAGE_LIST_CACHE_TTL_SECONDS:
        return cached[1]

    items = [
        image_metadata_from_path(root, file_path, include_exif=False)
        for file_path in sorted(iter_image_files(root, supported_extensions, excluded_scan_dirs), key=lambda path: str(path).lower())
    ]
    IMAGE_LIST_CACHE[cache_key] = (now, items)
    return items


def list_lightweight_image_metadata_page(
    root: Path,
    supported_extensions: set[str],
    excluded_scan_dirs: set[str],
    offset: int,
    limit: int,
) -> dict[str, Any]:
    page_items: list[dict[str, Any]] = []
    seen = 0
    has_more = False

    for file_path in iter_image_files(root, supported_extensions, excluded_scan_dirs):
        if seen < offset:
            seen += 1
            continue

        if len(page_items) >= limit:
            has_more = True
            break

        page_items.append(image_metadata_from_path(root, file_path, include_exif=True))
        seen += 1

    page_items.sort(key=lambda item: ((get_image_timestamp_for_sort(item) or 0) * -1, item["relative_path"].lower()))
    next_offset = offset + len(page_items)
    return {
        "items": page_items,
        "count": len(page_items),
        "total": None,
        "offset": offset,
        "limit": limit,
        "next_offset": next_offset if has_more else None,
        "has_more": has_more,
    }


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


def image_index_cache_path(
    index_dir: Path,
    cache_key: tuple[str, tuple[str, ...], tuple[str, ...]],
) -> Path:
    digest = hashlib.sha1("|".join([cache_key[0], *cache_key[1], *cache_key[2]]).encode("utf-8")).hexdigest()
    return index_dir / f"{digest}.json"


def image_index_summary_path(
    index_dir: Path,
    cache_key: tuple[str, tuple[str, ...], tuple[str, ...]],
) -> Path:
    digest = hashlib.sha1("|".join([cache_key[0], *cache_key[1], *cache_key[2]]).encode("utf-8")).hexdigest()
    return index_dir / f"{digest}.summary.json"


def timeline_index_cache_path(
    index_dir: Path,
    cache_key: tuple[str, tuple[str, ...], tuple[str, ...]],
) -> Path:
    digest = hashlib.sha1("|".join([cache_key[0], *cache_key[1], *cache_key[2]]).encode("utf-8")).hexdigest()
    return index_dir / f"{digest}.timeline.json"


def timeline_group_key_for_item(item: dict[str, Any]) -> str:
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


def load_full_image_index_cache(index_dir: Path, cache_key: tuple[str, tuple[str, ...], tuple[str, ...]]) -> list[dict[str, Any]]:
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


def get_timeline_index(
    index_dir: Path,
    root: Path,
    supported_extensions: set[str],
    excluded_scan_dirs: set[str],
) -> dict[str, Any]:
    cache_key = image_scan_cache_key(root, supported_extensions, excluded_scan_dirs)

    summary_metadata = load_image_index_summary_metadata(index_dir, cache_key)
    summary_generated_at = summary_metadata.get("generated_at")

    entries, timeline_generated_at = load_timeline_index_cache(index_dir, cache_key)

    # 只要 timeline 和 full index 的生成时间一致，就直接返回旧 timeline
    if entries and summary_generated_at == timeline_generated_at:
        return {
            "root": str(root),
            "entries": entries,
            "available": True,
            "from_cache": True,
        }

    # 关键：timeline 只允许从完整 index 生成
    full_items = load_full_image_index_cache(index_dir, cache_key)

    if full_items:
        full_items = [ensure_image_timeline_metadata(root, item) for item in full_items]
        save_timeline_index_cache(index_dir, cache_key, full_items, summary_generated_at)
        return {
            "root": str(root),
            "entries": build_timeline_index_entries(full_items),
            "available": True,
            "from_cache": True,
        }

    # 没有完整 index 时，不用 summary_items 生成 timeline
    return {
        "root": str(root),
        "entries": entries if entries else [],
        "available": bool(entries),
        "from_cache": bool(entries),
    }


def get_images_for_timeline_group(
    index_dir: Path,
    root: Path,
    supported_extensions: set[str],
    excluded_scan_dirs: set[str],
    group_key: str,
) -> dict[str, Any]:
    cache_key = image_scan_cache_key(root, supported_extensions, excluded_scan_dirs)
    items = load_full_image_index_cache(index_dir, cache_key)
    if not items:
        items = list_lightweight_image_metadata(root, supported_extensions, excluded_scan_dirs)

    group_items = []
    for item in items:
        item_with_exists = with_image_exists(root, item)
        if item_with_exists["exists"] and timeline_group_key_for_item(item_with_exists) == group_key:
            group_items.append(item_with_exists)
    group_items.sort(
        key=lambda item: ((get_image_timestamp_for_sort(item) or 0) * -1, item["relative_path"].lower())
    )
    return {
        "root": str(root),
        "group_key": group_key,
        "items": group_items,
        "count": len(group_items),
    }


def scan_lightweight_image_metadata_into_cache(
    cache_key: tuple[str, tuple[str, ...], tuple[str, ...]],
    index_dir: Path,
    root: Path,
    supported_extensions: set[str],
    excluded_scan_dirs: set[str],
) -> None:
    time.sleep(IMAGE_INDEX_REFRESH_DELAY_SECONDS)
    refreshed_items: list[dict[str, Any]] = []
    wrote_preview_summary = False
    try:
        for file_path in iter_image_files(root, supported_extensions, excluded_scan_dirs):
            item = image_metadata_from_path(root, file_path, include_exif=True)
            preview_items: list[dict[str, Any]] = []
            with IMAGE_SCAN_LOCK:
                state = IMAGE_SCAN_CACHE.get(cache_key)
                if state is None:
                    return
                if state.get("from_cache"):
                    refreshed_items.append(item)
                else:
                    state["items"].append(item)
                    if len(state["items"]) >= IMAGE_INDEX_PREVIEW_LIMIT and not wrote_preview_summary:
                        preview_items = list(state["items"][:IMAGE_INDEX_PREVIEW_LIMIT])
            if preview_items and not wrote_preview_summary:
                save_image_index_summary(index_dir, cache_key, preview_items, None)
                wrote_preview_summary = True
    except Exception as exc:
        with IMAGE_SCAN_LOCK:
            state = IMAGE_SCAN_CACHE.get(cache_key)
            if state is not None:
                state["error"] = str(exc)
    finally:
        with IMAGE_SCAN_LOCK:
            state = IMAGE_SCAN_CACHE.get(cache_key)
            if state is not None:
                if state.get("from_cache"):
                    refreshed_items.sort(key=lambda item: ((get_image_timestamp_for_sort(item) or 0) * -1, item["relative_path"].lower()))
                    state["items"] = refreshed_items
                    state["from_cache"] = False
                else:
                    state["items"].sort(key=lambda item: ((get_image_timestamp_for_sort(item) or 0) * -1, item["relative_path"].lower()))
                items = list(state["items"])
                state["complete"] = True
                state["scanning"] = False
                state["total"] = len(items)
                state["generated_at"] = datetime.now().isoformat()
            else:
                items = []
        if items:
            try:
                save_image_index_cache(index_dir, cache_key, items)
            except FileNotFoundError:
                pass


def ensure_image_scan_started(
    index_dir: Path,
    root: Path,
    supported_extensions: set[str],
    excluded_scan_dirs: set[str],
    refresh: bool = True,
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    cache_key = image_scan_cache_key(root, supported_extensions, excluded_scan_dirs)
    with IMAGE_SCAN_LOCK:
        state = IMAGE_SCAN_CACHE.get(cache_key)
        if state is None:
            cached_items, cached_total, cached_generated_at = load_image_index_cache(index_dir, cache_key)
            state = {
                "items": cached_items,
                "complete": bool(cached_items) and not refresh,
                "scanning": refresh or not cached_items,
                "from_cache": bool(cached_items),
                "total": cached_total,
                "generated_at": cached_generated_at,
                "error": "",
                "started_at": time.monotonic(),
            }
            IMAGE_SCAN_CACHE[cache_key] = state
            if state["scanning"]:
                thread = threading.Thread(
                    target=scan_lightweight_image_metadata_into_cache,
                    args=(cache_key, index_dir, root, supported_extensions, excluded_scan_dirs),
                    daemon=True,
                )
                thread.start()
        elif refresh and not state.get("scanning") and state.get("from_cache"):
            state["scanning"] = True
            thread = threading.Thread(
                target=scan_lightweight_image_metadata_into_cache,
                args=(cache_key, index_dir, root, supported_extensions, excluded_scan_dirs),
                daemon=True,
            )
            thread.start()

        return cache_key


def list_images_cached_page(
    index_dir: Path,
    root: Path,
    supported_extensions: set[str],
    excluded_scan_dirs: set[str],
    offset: int,
    limit: int,
    refresh: bool = True,
    include_total: bool = False,
) -> dict[str, Any]:
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must be greater than or equal to 0")
    if limit < 1:
        raise HTTPException(status_code=400, detail="limit must be greater than 0")

    cache_key = ensure_image_scan_started(index_dir, root, supported_extensions, excluded_scan_dirs, refresh)

    with IMAGE_SCAN_LOCK:
        state = IMAGE_SCAN_CACHE.get(cache_key)
        if state is None:
            items_count = 0
            page_items = []
            scanning = True
            complete = False
            total = None
            generated_at = None
            error = ""
        else:
            stale_paths: set[str] = set()
            page_items = []
            cursor = offset
            raw_items = list(state["items"])
            while cursor < len(raw_items) and len(page_items) < limit:
                item = with_image_exists(root, raw_items[cursor])
                if item["exists"]:
                    page_items.append(item)
                else:
                    stale_paths.add(str(item.get("relative_path", "")))
                cursor += 1

            if stale_paths:
                state["items"] = [
                    item
                    for item in state["items"]
                    if str(item.get("relative_path", "")) not in stale_paths
                ]
                if isinstance(state.get("total"), int):
                    state["total"] = max(0, state["total"] - len(stale_paths))

            items_count = len(state["items"])
            scanning = bool(state["scanning"])
            complete = bool(state["complete"])
            total = state.get("total")
            generated_at = state.get("generated_at")
            error = str(state.get("error", ""))

    next_offset = offset + len(page_items)
    has_more = scanning or next_offset < items_count

    return {
        "items": page_items,
        "count": len(page_items),
        "total": (total if isinstance(total, int) else (items_count if complete else None)) if include_total else None,
        "total_generated_at": generated_at if include_total and isinstance(generated_at, str) else None,
        "offset": offset,
        "limit": limit,
        "next_offset": next_offset if has_more else None,
        "has_more": has_more,
        "scanning": scanning,
        "scan_complete": complete,
        "preview_only": bool(not scanning and isinstance(total, int) and total > items_count),
        "scan_error": error,
    }


def get_image_timestamp_for_sort(item: dict[str, Any]) -> float | None:
    timestamp = item.get("timeline_ts")
    if isinstance(timestamp, int | float):
        return float(timestamp)
    return None


def list_images(root: Path, supported_extensions: set[str], excluded_scan_dirs: set[str]) -> list[dict[str, Any]]:
    return [
        image_metadata_from_path(root, file_path, include_exif=True)
        for file_path in sorted(iter_image_files(root, supported_extensions, excluded_scan_dirs), key=lambda path: str(path).lower())
    ]


def list_images_page(
    root: Path,
    supported_extensions: set[str],
    excluded_scan_dirs: set[str],
    offset: int = 0,
    limit: int | None = None,
    include_exif: bool = True,
) -> dict[str, Any]:
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must be greater than or equal to 0")
    if limit is not None and limit < 1:
        raise HTTPException(status_code=400, detail="limit must be greater than 0")

    if not include_exif and limit is not None:
        return list_lightweight_image_metadata_page(root, supported_extensions, excluded_scan_dirs, offset, limit)

    if include_exif:
        items = list_images(root, supported_extensions, excluded_scan_dirs)
    else:
        items = list_lightweight_image_metadata(root, supported_extensions, excluded_scan_dirs)

    total = len(items)
    page_items = items[offset:] if limit is None else items[offset : offset + limit]
    next_offset = offset + len(page_items)
    return {
        "items": page_items,
        "count": len(page_items),
        "total": total,
        "offset": offset,
        "limit": limit,
        "next_offset": next_offset if next_offset < total else None,
        "has_more": next_offset < total,
    }


def build_deleted_path(deleted_dir: Path, root: Path, relative_path: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    digest = hashlib.sha1(f"{root}|{relative_path}".encode("utf-8")).hexdigest()[:10]
    file_name = Path(relative_path).name
    return deleted_dir / f"{timestamp}_{digest}" / file_name


def resolve_deleted_file(deleted_dir: Path, candidate: str) -> Path:
    deleted_path = Path(candidate).expanduser().resolve()
    deleted_root = deleted_dir.resolve()
    try:
        deleted_path.relative_to(deleted_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid deleted file path")
    return deleted_path


def remove_empty_deleted_parent(deleted_dir: Path, deleted_path: Path) -> None:
    deleted_root = deleted_dir.resolve()
    parent = deleted_path.resolve().parent
    while parent != deleted_root:
        try:
            parent.rmdir()
        except OSError:
            break
        parent = parent.parent


def thumbnail_path_for(thumbnail_dir: Path, root: Path, relative_path: str) -> Path:
    digest = hashlib.sha1(f"{root}|{relative_path}".encode("utf-8")).hexdigest()
    return thumbnail_dir / digest[:2] / digest[2:4] / f"{digest}.jpg"


def deleted_thumbnail_path_for(thumbnail_dir: Path, deleted_path: Path) -> Path:
    digest = hashlib.sha1(f"deleted|{deleted_path}".encode("utf-8")).hexdigest()
    return thumbnail_dir / "deleted" / digest[:2] / f"deleted_{digest}.jpg"


def image_file_response(image_path: Path, thumbnail_path: Path, thumbnail_size: tuple[int, int], image_module: Any, image_ops_module: Any) -> FileResponse:
    should_refresh = not thumbnail_path.exists() or thumbnail_path.stat().st_mtime < image_path.stat().st_mtime
    if not should_refresh:
        try:
            with image_module.open(thumbnail_path) as existing_thumb:
                should_refresh = max(existing_thumb.size) < max(thumbnail_size)
        except Exception:
            should_refresh = True

    if should_refresh:
        thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
        with image_module.open(image_path) as img:
            if hasattr(img, "draft"):
                img.draft("RGB", thumbnail_size)
            thumb = image_ops_module.exif_transpose(img)
            thumb.thumbnail(thumbnail_size)
            if thumb.mode != "RGB":
                thumb = thumb.convert("RGB")
            thumb.save(thumbnail_path, format="JPEG", quality=92, optimize=True)

    return FileResponse(thumbnail_path)
