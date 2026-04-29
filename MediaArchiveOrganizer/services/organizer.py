# SPDX-License-Identifier: MIT

import os
import shutil
import csv
import json
import sys
from datetime import datetime
from typing import Callable
from core.date_classifier import get_target_date, build_date_path
from core.duplicate_detector import compute_file_hash, compute_phash, phash_distance
from core.hash_db import (
    add_hash_record,
    create_empty_hash_db,
    get_db_path,
    get_valid_original_paths,
    load_hash_db,
    save_hash_db,
)

from core.file_transfer import apply_windows_file_times, read_windows_file_times, transfer_file

SUPPORTED_EXT = (".jpg", ".jpeg", ".png", ".mp4", ".mov")
ProgressCallback = Callable[[int], None]
PROGRESS_INTERVAL = 25
WindowsFileTime = tuple[int, int]
WindowsFileTimes = tuple[WindowsFileTime, WindowsFileTime, WindowsFileTime]

HashCache = dict[str, dict[str, object]]
HASH_CACHE_VERSION = 1
HASH_CACHE_SUFFIX = ".file_cache.json"


def get_hash_cache_path() -> str:
    # Keep the file-content cache separate from hash_db so the existing hash_db
    # schema and duplicate lookup logic remain untouched.
    return f"{get_db_path()}{HASH_CACHE_SUFFIX}"


def load_hash_cache() -> HashCache:
    cache_path = get_hash_cache_path()
    try:
        with open(cache_path, "r", encoding="utf-8") as file_obj:
            payload = json.load(file_obj)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}

    if not isinstance(payload, dict):
        return {}

    entries = payload.get("entries", {})
    if not isinstance(entries, dict):
        return {}

    return entries


def save_hash_cache(cache: HashCache) -> None:
    cache_path = get_hash_cache_path()
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    payload = {
        "version": HASH_CACHE_VERSION,
        "updated_at": datetime.now().isoformat(),
        "entries": cache,
    }
    with open(cache_path, "w", encoding="utf-8") as file_obj:
        json.dump(payload, file_obj, indent=2, ensure_ascii=False)


def normalize_cache_path(path: str) -> str:
    return os.path.abspath(path)


def get_file_signature(path: str) -> dict[str, int]:
    stat_result = os.stat(path)
    return {
        "size": stat_result.st_size,
        "mtime_ns": stat_result.st_mtime_ns,
    }


def is_cache_entry_current(entry: dict[str, object], signature: dict[str, int]) -> bool:
    return (
        entry.get("size") == signature["size"]
        and entry.get("mtime_ns") == signature["mtime_ns"]
    )


def get_or_compute_hash(
    cache: HashCache,
    method: str,
    path: str,
) -> str | None:
    # Reuse strict hash / pHash when the same file path still has the same
    # size and mtime. This prevents organize / hash-db rebuild / duplicate-json
    # rebuild from decoding and hashing unchanged files repeatedly.
    path_key = normalize_cache_path(path)
    signature = get_file_signature(path)
    entry = cache.get(path_key)

    if isinstance(entry, dict) and is_cache_entry_current(entry, signature):
        cached_value = entry.get(method)
        if isinstance(cached_value, str) and cached_value:
            return cached_value
    else:
        entry = {**signature}
        cache[path_key] = entry

    if method == "strict":
        hash_value = compute_file_hash(path)
    elif method == "phash":
        hash_value = compute_phash(path)
    else:
        raise ValueError(f"Unsupported hash method: {method}")

    if hash_value is not None:
        entry[method] = hash_value

    return hash_value


def copy_hash_cache_entry(cache: HashCache, source_path: str, target_path: str) -> None:
    # The transferred file has the same content as source_path. Reuse already
    # computed hash values for target_path when the target metadata is available.
    source_entry = cache.get(normalize_cache_path(source_path))
    if not isinstance(source_entry, dict):
        return

    try:
        target_signature = get_file_signature(target_path)
    except OSError:
        return

    target_entry: dict[str, object] = {**target_signature}
    for method in ("strict", "phash"):
        value = source_entry.get(method)
        if isinstance(value, str) and value:
            target_entry[method] = value

    cache[normalize_cache_path(target_path)] = target_entry

def timestamp():
    # Keep log timestamps human-readable for quick troubleshooting.
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_unique_path(directory: str, filename: str) -> str:
    # Append a numeric suffix to avoid overwriting an existing file.
    base, ext = os.path.splitext(filename)
    candidate = os.path.join(directory, filename)
    counter = 1

    while os.path.exists(candidate):
        candidate = os.path.join(directory, f"{base}_{counter}{ext}")
        counter += 1

    return candidate


def get_duplicate_path(original_path: str) -> str:
    # Keep duplicates beside the retained file using an explicit duplicate suffix.
    directory = os.path.dirname(original_path)
    base, ext = os.path.splitext(os.path.basename(original_path))
    counter = 1
    candidate = os.path.join(directory, f"{base}_dup{counter}{ext}")

    while os.path.exists(candidate):
        counter += 1
        candidate = os.path.join(directory, f"{base}_dup{counter}{ext}")

    return candidate


def build_duplicate_report_path(log_path: str) -> str:
    log_dir = os.path.dirname(os.path.abspath(log_path))
    return os.path.join(log_dir, "duplicate_report.csv")


def build_duplicate_json_path(log_path: str) -> str:
    log_dir = os.path.dirname(os.path.abspath(log_path))
    return os.path.join(log_dir, "duplicates.json")


def append_duplicate_report_rows(report_path: str, rows: list[dict[str, str]]) -> None:
    if not rows:
        return

    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    fieldnames = [
        "original_name",
        "original_path",
        "kept_path",
        "duplicate_method",
        "hash",
        "duplicate_path",
    ]
    write_header = not os.path.exists(report_path)

    with open(report_path, "a", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


def to_relative_if_possible(path: str, root_dir: str) -> str:
    path_abs = os.path.abspath(path)
    root_abs = os.path.abspath(root_dir)

    try:
        return os.path.relpath(path_abs, root_abs).replace("\\", "/")
    except ValueError:
        return path_abs.replace("\\", "/")


def write_duplicate_json(json_path: str, dst_dir: str, rows: list[dict[str, str]]) -> None:
    groups_by_kept_path: dict[str, dict] = {}

    for row in rows:
        kept_path = row["kept_path"]
        group_paths = row.get("group_paths") or [kept_path, row["duplicate_path"]]
        group = groups_by_kept_path.setdefault(
            kept_path,
            {
                "reason": row["duplicate_method"],
                "hash": row["hash"],
                "kept_path": to_relative_if_possible(kept_path, dst_dir),
                "items": [],
                "source_files": [],
                "seen_paths": set(),
            },
        )

        for index, path in enumerate(group_paths):
            path_abs = os.path.abspath(path)
            if path_abs in group["seen_paths"]:
                continue

            group["seen_paths"].add(path_abs)
            group["items"].append(
                {
                    "role": "kept" if index == 0 else "duplicate",
                    "path": to_relative_if_possible(path, dst_dir),
                }
            )
        group["source_files"].append(row["original_path"])

    groups = []
    for index, group in enumerate(groups_by_kept_path.values(), start=1):
        groups.append(
            {
                "group_id": f"dup_{index:04d}",
                "reason": group["reason"],
                "hash": group["hash"],
                "kept_path": group["kept_path"],
                "items": group["items"],
                "source_files": group["source_files"],
            }
        )

    payload = {
        "generated_at": datetime.now().isoformat(),
        "destination_root": os.path.abspath(dst_dir),
        "group_count": len(groups),
        "groups": groups,
    }

    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as file_obj:
        json.dump(payload, file_obj, indent=2, ensure_ascii=False)


def build_duplicate_payload_groups(dst_dir: str, groups: list[dict]) -> list[dict]:
    payload_groups = []

    for index, group in enumerate(groups, start=1):
        paths = sorted(group["paths"], key=lambda value: os.path.abspath(value).lower())
        if len(paths) < 2:
            continue

        kept_path = paths[0]
        payload_groups.append(
            {
                "group_id": f"dup_{len(payload_groups) + 1:04d}",
                "reason": group["reason"],
                "hash": group["hash"],
                "kept_path": to_relative_if_possible(kept_path, dst_dir),
                "items": [
                    {
                        "role": "kept" if item_index == 0 else "duplicate",
                        "path": to_relative_if_possible(path, dst_dir),
                    }
                    for item_index, path in enumerate(paths)
                ],
                "source_files": [],
            }
        )

    return payload_groups


def load_mergeable_duplicate_groups(
    json_path: str,
    dst_dir: str,
    replace_methods: set[str],
) -> list[dict]:
    if not os.path.exists(json_path):
        return []

    try:
        with open(json_path, "r", encoding="utf-8") as file_obj:
            payload = json.load(file_obj)
    except (OSError, json.JSONDecodeError):
        return []

    if os.path.abspath(str(payload.get("destination_root", ""))) != os.path.abspath(dst_dir):
        return []

    groups = payload.get("groups", [])
    if not isinstance(groups, list):
        return []

    kept_groups = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        reason = str(group.get("reason", "")).strip().lower()
        if reason in replace_methods:
            continue

        items = group.get("items", [])
        if not isinstance(items, list) or len(items) < 2:
            continue

        normalized_items = []
        for item_index, item in enumerate(items):
            if not isinstance(item, dict) or not item.get("path"):
                continue
            normalized_items.append(
                {
                    "role": str(item.get("role") or ("kept" if item_index == 0 else "duplicate")),
                    "path": str(item["path"]),
                }
            )

        if len(normalized_items) < 2:
            continue

        kept_groups.append(
            {
                "group_id": "",
                "reason": group.get("reason", "-"),
                "hash": str(group.get("hash", "")),
                "kept_path": str(group.get("kept_path") or normalized_items[0]["path"]),
                "items": normalized_items,
                "source_files": group.get("source_files", []) if isinstance(group.get("source_files"), list) else [],
            }
        )

    return kept_groups


def merge_duplicate_payload_groups(existing_groups: list[dict], new_groups: list[dict]) -> list[dict]:
    merged = []
    seen = set()

    for group in [*existing_groups, *new_groups]:
        item_paths = tuple(sorted(str(item.get("path", "")) for item in group.get("items", [])))
        key = (str(group.get("reason", "")).strip().lower(), item_paths)
        if not item_paths or key in seen:
            continue

        seen.add(key)
        copied = {**group, "group_id": f"dup_{len(merged) + 1:04d}"}
        merged.append(copied)

    return merged


def write_duplicate_groups_json(
    json_path: str,
    dst_dir: str,
    groups: list[dict],
    merge_existing_methods: set[str] | None = None,
) -> int:
    payload_groups = build_duplicate_payload_groups(dst_dir, groups)
    if merge_existing_methods:
        existing_groups = load_mergeable_duplicate_groups(json_path, dst_dir, merge_existing_methods)
        payload_groups = merge_duplicate_payload_groups(existing_groups, payload_groups)

    payload = {
        "generated_at": datetime.now().isoformat(),
        "destination_root": os.path.abspath(dst_dir),
        "group_count": len(payload_groups),
        "groups": payload_groups,
    }

    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as file_obj:
        json.dump(payload, file_obj, indent=2, ensure_ascii=False)
    return len(payload_groups)



def parse_phash_prefix(phash_value: str, prefix_hex_chars: int = 4) -> int | None:
    # Use the high bits of the pHash as a safe pre-filter. If two hashes are
    # within the full Hamming threshold, their prefix distance must also be
    # within that threshold, so this does not intentionally drop valid matches.
    try:
        return int(phash_value[:prefix_hex_chars], 16)
    except (TypeError, ValueError):
        return None


def build_hamming_masks(bit_count: int, max_distance: int) -> list[int]:
    masks = [0]

    def visit(start: int, remaining: int, mask: int) -> None:
        if remaining == 0:
            masks.append(mask)
            return

        for bit_index in range(start, bit_count):
            visit(bit_index + 1, remaining - 1, mask | (1 << bit_index))

    for distance in range(1, max_distance + 1):
        visit(0, distance, 0)

    return masks


def group_phash_records(
    phash_records: list[tuple[str, str]],
    phash_threshold: int,
    progress_callback: ProgressCallback | None = None,
) -> list[dict]:
    # Bucket by the first 16 pHash bits, then search only buckets whose prefix
    # is within the configured Hamming threshold. This keeps matching complete
    # for threshold-based pHash search while avoiding a full all-vs-all scan in
    # normal photo libraries.
    records = sorted(phash_records, key=lambda item: item[1].lower())
    parsed_prefixes = [parse_phash_prefix(hash_value) for hash_value, _ in records]

    if any(prefix is None for prefix in parsed_prefixes):
        return group_phash_records_legacy(records, phash_threshold, progress_callback)

    prefix_buckets: dict[int, list[int]] = {}
    for index, prefix in enumerate(parsed_prefixes):
        assert prefix is not None
        prefix_buckets.setdefault(prefix, []).append(index)

    prefix_bit_count = 16
    safe_prefix_threshold = min(phash_threshold, prefix_bit_count)
    masks = build_hamming_masks(prefix_bit_count, safe_prefix_threshold)
    visited: set[int] = set()
    groups: list[dict] = []
    grouped_seed_count = 0

    for seed_index, (seed_hash, _) in enumerate(records):
        if seed_index in visited:
            continue

        seed_prefix = parsed_prefixes[seed_index]
        assert seed_prefix is not None
        grouped_seed_count += 1
        if progress_callback and grouped_seed_count % PROGRESS_INTERVAL == 0:
            progress_callback(grouped_seed_count)

        group_indexes = [seed_index]
        visited.add(seed_index)
        candidate_indexes: set[int] = set()

        for mask in masks:
            candidate_indexes.update(prefix_buckets.get(seed_prefix ^ mask, []))

        for candidate_index in sorted(candidate_indexes):
            if candidate_index == seed_index or candidate_index in visited:
                continue

            candidate_hash, _ = records[candidate_index]
            if phash_distance(seed_hash, candidate_hash) <= phash_threshold:
                group_indexes.append(candidate_index)
                visited.add(candidate_index)

        if len(group_indexes) >= 2:
            groups.append(
                {
                    "reason": "phash",
                    "hash": seed_hash,
                    "paths": [records[index][1] for index in group_indexes],
                }
            )

    return groups


def group_phash_records_legacy(
    phash_records: list[tuple[str, str]],
    phash_threshold: int,
    progress_callback: ProgressCallback | None = None,
) -> list[dict]:
    unused = sorted(phash_records, key=lambda item: item[1].lower())
    grouped_seed_count = 0
    groups: list[dict] = []

    while unused:
        seed_hash, seed_path = unused.pop(0)
        grouped_seed_count += 1
        if progress_callback and grouped_seed_count % PROGRESS_INTERVAL == 0:
            progress_callback(grouped_seed_count)
        group_paths = [seed_path]
        remaining = []

        for candidate_hash, candidate_path in unused:
            if phash_distance(seed_hash, candidate_hash) <= phash_threshold:
                group_paths.append(candidate_path)
            else:
                remaining.append((candidate_hash, candidate_path))

        if len(group_paths) >= 2:
            groups.append({"reason": "phash", "hash": seed_hash, "paths": group_paths})
        unused = remaining

    return groups


def rebuild_duplicate_results_json(
    root_dir: str,
    json_path: str,
    hash_method: str = "both",
    phash_threshold: int = 4,
    scan_progress_callback: ProgressCallback | None = None,
    group_progress_callback: ProgressCallback | None = None,
    merge_existing_methods: set[str] | None = None,
) -> dict[str, int | str]:
    root_abs = os.path.abspath(root_dir)
    strict_records: dict[str, list[str]] = {}
    phash_records: list[tuple[str, str]] = []
    scanned_files = 0
    hash_cache = load_hash_cache()

    for path in iter_supported_media_files(root_abs):
        scanned_files += 1
        if scan_progress_callback and scanned_files % PROGRESS_INTERVAL == 0:
            scan_progress_callback(scanned_files)

        if hash_method in ("strict", "both"):
            strict_value = get_or_compute_hash(hash_cache, "strict", path)
            if strict_value is not None:
                strict_records.setdefault(strict_value, []).append(path)

        if hash_method in ("phash", "both"):
            phash_value = get_or_compute_hash(hash_cache, "phash", path)
            if phash_value is not None:
                phash_records.append((phash_value, path))

    groups: list[dict] = []

    if hash_method in ("strict", "both"):
        for hash_value, paths in sorted(strict_records.items()):
            if len(paths) >= 2:
                groups.append({"reason": "strict", "hash": hash_value, "paths": paths})

    if hash_method in ("phash", "both"):
        groups.extend(
            group_phash_records(
                phash_records,
                phash_threshold,
                group_progress_callback,
            )
        )

    save_hash_cache(hash_cache)
    duplicate_group_count = write_duplicate_groups_json(json_path, root_abs, groups, merge_existing_methods)
    return {
        "root_dir": root_abs,
        "json_path": os.path.abspath(json_path),
        "scanned_files": scanned_files,
        "duplicate_group_count": duplicate_group_count,
    }


def resolve_duplicate_hash(
    path: str,
    duplicate_detection: str,
    hash_cache: HashCache,
) -> tuple[str, str] | None:
    # Select the requested duplicate detection method for the current file.
    if duplicate_detection == "off":
        return None

    if duplicate_detection == "strict":
        strict_value = get_or_compute_hash(hash_cache, "strict", path)
        if strict_value is None:
            return None
        return "strict", strict_value

    phash_value = get_or_compute_hash(hash_cache, "phash", path)
    if phash_value is None:
        return None

    return "phash", phash_value


def iter_supported_media_files(root_dir: str):
    for walk_root, _, files in os.walk(root_dir):
        for name in files:
            if name.lower().endswith(SUPPORTED_EXT):
                yield os.path.join(walk_root, name)


def rebuild_hash_db(
    root_dir: str,
    rebuild_mode: str = "replace",
    hash_method: str = "both",
    progress_callback: ProgressCallback | None = None,
) -> dict[str, int | str]:
    root_abs = os.path.abspath(root_dir)
    db = load_hash_db() if rebuild_mode == "append" else create_empty_hash_db()
    hash_cache = load_hash_cache()
    stats = {
        "root_dir": root_abs,
        "db_path": os.path.abspath(get_db_path()),
        "scanned_files": 0,
        "strict_indexed": 0,
        "phash_indexed": 0,
    }

    for path in iter_supported_media_files(root_abs):
        stats["scanned_files"] += 1
        if progress_callback and stats["scanned_files"] % PROGRESS_INTERVAL == 0:
            progress_callback(stats["scanned_files"])

        if hash_method in ("strict", "both"):
            strict_value = get_or_compute_hash(hash_cache, "strict", path)
            if strict_value is not None:
                add_hash_record(db, "strict", strict_value, path)
                stats["strict_indexed"] += 1

        if hash_method in ("phash", "both"):
            phash_value = get_or_compute_hash(hash_cache, "phash", path)
            if phash_value is not None:
                add_hash_record(db, "phash", phash_value, path)
                stats["phash_indexed"] += 1

    save_hash_db(db)
    save_hash_cache(hash_cache)
    return stats


def organize_images(
    src_dir: str,
    dst_dir: str,
    log_path: str,
    mode: str = "move",
    lang=None,
    duplicate_detection: str = "phash",
    phash_threshold: int = 4,
    progress_callback: ProgressCallback | None = None,
    duplicates_json_path: str | None = None,
):
    os.makedirs(dst_dir, exist_ok=True)
    log_lines = []
    duplicate_rows = []
    processed_count = 0

    # Load the persisted hash database and file-content hash cache once per run.
    hash_db = load_hash_db()
    hash_cache = load_hash_cache()

    for root, _, files in os.walk(src_dir):
        for name in files:
            path = os.path.join(root, name)

            # Ignore files outside the supported media extensions.
            if not name.lower().endswith(SUPPORTED_EXT):
                continue

            try:
                processed_count += 1
                if progress_callback and processed_count % PROGRESS_INTERVAL == 0:
                    progress_callback(processed_count)

                duplicate_info = resolve_duplicate_hash(path, duplicate_detection, hash_cache)
                valid_paths = []

                if duplicate_info is not None:
                    method, hash_value = duplicate_info
                    # Only treat matches inside the current destination root as duplicates.
                    valid_paths = get_valid_original_paths(
                        hash_db,
                        method,
                        hash_value,
                        dst_dir,
                        threshold=phash_threshold,
                    )

                if valid_paths:
                    original_path = valid_paths[0]
                    target_path = get_duplicate_path(original_path)
                    transfer_file(path, target_path, mode)
                    copy_hash_cache_entry(hash_cache, path, target_path)
                    duplicate_rows.append(
                        {
                            "original_name": os.path.basename(path),
                            "original_path": path,
                            "kept_path": original_path,
                            "duplicate_method": method,
                            "hash": hash_value,
                            "duplicate_path": target_path,
                            "group_paths": [*valid_paths, target_path],
                        }
                    )

                    log_lines.append(
                        f"{timestamp()} | DUP | {method}={hash_value} | {path} -> {target_path} | original={original_path}"
                    )

                else:
                    dt = get_target_date(path)
                    target_dir = build_date_path(dst_dir, dt)
                    os.makedirs(target_dir, exist_ok=True)

                    target_path = get_unique_path(target_dir, name)
                    transfer_file(path, target_path, mode)
                    copy_hash_cache_entry(hash_cache, path, target_path)

                    log_lines.append(
                        f"{timestamp()} | OK | {mode.upper()} | {path} -> {target_path}"
                    )

                if duplicate_info is not None:
                    method, hash_value = duplicate_info
                    add_hash_record(hash_db, method, hash_value, target_path)

            except Exception as e:
                log_lines.append(
                    f"{timestamp()} | ERR | {type(e).__name__} | {path} | {str(e)}"
                )

    # Persist the updated hash database and file-content hash cache after the run completes.
    save_hash_db(hash_db)
    save_hash_cache(hash_cache)
    append_duplicate_report_rows(build_duplicate_report_path(log_path), duplicate_rows)
    write_duplicate_json(duplicates_json_path or build_duplicate_json_path(log_path), dst_dir, duplicate_rows)

    # Write one log entry per processed file so each run can be audited later.
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))
