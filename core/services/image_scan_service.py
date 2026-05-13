# SPDX-License-Identifier: MIT

from __future__ import annotations

import os
import threading
import time
import warnings
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from fastapi import HTTPException
from MediaArchiveOrganizer.core.date_classifier import get_target_date_with_source
from core.config.app_config import VIDEO_EXTENSIONS
from core.services.file_operations import (
    copy_file_preserve_times,
    move_file_preserve_times,
    resolve_under_root,
)
from core.services.image_index_service import (
    IMAGE_INDEX_PREVIEW_LIMIT,
    build_timeline_index_entries,
    get_image_timestamp_for_sort,
    image_index_cache_path,
    image_index_summary_path,
    image_scan_cache_key,
    load_full_image_index_cache,
    load_image_index_cache,
    load_image_index_summary_metadata,
    load_timeline_index_cache,
    save_image_index_cache,
    save_image_index_summary,
    save_image_index_summary_metadata,
    save_timeline_index_cache,
    timeline_group_key_for_item,
    timeline_index_cache_path,
)
from core.services.recycle_paths import (
    build_deleted_path,
    remove_empty_deleted_parent,
    resolve_deleted_file,
)
from core.services.thumbnail_service import (
    deleted_thumbnail_path_for,
    image_file_response,
    thumbnail_path_for,
)

IMAGE_LIST_CACHE_TTL_SECONDS = 5.0
IMAGE_LIST_CACHE: dict[tuple[str, tuple[str, ...], tuple[str, ...]], tuple[float, list[dict[str, Any]]]] = {}
IMAGE_SCAN_CACHE: dict[tuple[str, tuple[str, ...], tuple[str, ...]], dict[str, Any]] = {}
IMAGE_SCAN_LOCK = threading.Lock()
IMAGE_INDEX_REFRESH_DELAY_SECONDS = 0.0


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
    media_type = "video" if file_path.suffix.lower() in VIDEO_EXTENSIONS else "image"
    return {
        "relative_path": relative_path,
        "path": relative_path,
        "name": file_path.name,
        "media_type": media_type,
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
        and isinstance(item.get("timeline_ts"), int | float)
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

    # If timeline and full index have the same generation time, return the old timeline
    if entries and summary_generated_at == timeline_generated_at:
        return {
            "root": str(root),
            "entries": entries,
            "available": True,
            "from_cache": True,
        }

    # Critical: timeline must only be generated from a full index
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

    # Without a full index, do not generate timeline from summary items
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
    refreshed_paths: set[str] = set()
    live_paths: set[str] | None = None
    wrote_preview_summary = False
    try:
        for file_path in iter_image_files(root, supported_extensions, excluded_scan_dirs):
            item = image_metadata_from_path(root, file_path, include_exif=True)
            relative_path = str(item.get("relative_path", ""))
            preview_items: list[dict[str, Any]] = []
            with IMAGE_SCAN_LOCK:
                state = IMAGE_SCAN_CACHE.get(cache_key)
                if state is None:
                    return
                if state.get("from_cache"):
                    if live_paths is None:
                        live_paths = {
                            str(cached_item.get("relative_path", ""))
                            for cached_item in state["items"]
                        }
                    refreshed_items.append(item)
                    refreshed_paths.add(relative_path)
                    if relative_path and relative_path not in live_paths:
                        state["items"].append(item)
                        live_paths.add(relative_path)
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
            cached_preview_only = isinstance(cached_total, int) and cached_total > len(cached_items)
            state = {
                "items": cached_items,
                "complete": bool(cached_items) and not refresh and not cached_preview_only,
                "scanning": refresh or not cached_items or cached_preview_only,
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
