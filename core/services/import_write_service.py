# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from core.config.app_config import ROOT_DATA_DIR, SKIP_SCAN_DIR_NAMES, SUPPORTED_EXTENSIONS
from core.domain.root_context import RootContext
from core.media_policy import phash_eligible
from core.services.image_index_service import (
    build_timeline_index_entries,
    digest_for_cache_key,
    image_index_cache_path,
    image_index_summary_path,
    image_scan_cache_key,
    load_image_index_summary_metadata,
    save_image_index_summary_metadata,
    timeline_index_cache_path,
)
from core.services.image_scan_service import clear_image_list_cache, image_metadata_from_path
from core.storage.duplicates_repository import DuplicateResultRepository
from core.storage.hash_db_repository import HashDbRepository
from core.storage.image_index_repository import ImageIndexRepository
from media_engine.core.date_classifier import build_date_path, get_target_date
from media_engine.core.duplicate_detector import compute_phash
from media_engine.services.organizer import get_unique_path, transfer_file


ApplyFileTimes = Callable[[Path, str, str], None]
RepairModifiedTime = Callable[[Path, str, str], str]
ComputePhash = Callable[[str], str | None]


@dataclass(frozen=True)
class StagedMediaAnalysis:
    strict_hash: str
    phash: str
    size: int


@dataclass(frozen=True)
class ImportedMedia:
    path: Path
    strict_hash: str
    phash: str
    size: int
    duplicate_dirty: bool


def analyze_staged_media(
    staged_path: Path,
    *,
    compute_phash_fn: ComputePhash = compute_phash,
) -> StagedMediaAnalysis:
    strict_hash = sha256_file(staged_path)
    phash = ""
    if phash_eligible(staged_path):
        phash = compute_phash_fn(str(staged_path)) or ""
    return StagedMediaAnalysis(
        strict_hash=strict_hash,
        phash=phash,
        size=staged_path.stat().st_size,
    )


def import_staged_media(
    *,
    staged_path: Path,
    filename: str,
    gallery_root: Path,
    duplicate_dirty_reason: str,
    created_at: str = "",
    modified_at: str = "",
    database_path: str | Path | None = None,
    analysis: StagedMediaAnalysis | None = None,
    compute_phash_fn: ComputePhash = compute_phash,
    apply_file_times_fn: ApplyFileTimes | None = None,
    repair_modified_time_fn: RepairModifiedTime | None = None,
) -> ImportedMedia:
    analysis = analysis or analyze_staged_media(staged_path, compute_phash_fn=compute_phash_fn)
    if repair_modified_time_fn is not None:
        modified_at = repair_modified_time_fn(staged_path, created_at, modified_at)

    target_date = get_target_date(str(staged_path))
    target_dir = Path(build_date_path(str(gallery_root), target_date))
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = Path(get_unique_path(str(target_dir), filename))
    transfer_file(staged_path, target_path, "copy")

    if apply_file_times_fn is not None:
        apply_file_times_fn(target_path, created_at, modified_at)

    db_path = Path(database_path) if database_path is not None else root_database_path(gallery_root)
    imported_item = image_metadata_from_path(gallery_root, target_path, include_exif=True)
    cache_key = image_scan_cache_key(gallery_root, SUPPORTED_EXTENSIONS, SKIP_SCAN_DIR_NAMES)
    cache_digest = digest_for_cache_key(cache_key)
    max_existing_timeline_ts = ImageIndexRepository(db_path).max_timeline_ts(cache_digest)
    imported_timeline_ts = imported_item.get("timeline_ts")
    should_mark_duplicates_dirty = not (
        isinstance(imported_timeline_ts, int | float)
        and isinstance(max_existing_timeline_ts, int | float)
        and float(imported_timeline_ts) > float(max_existing_timeline_ts)
    )
    hash_repository = HashDbRepository(db_path)
    hash_repository.add_hash_record("strict", analysis.strict_hash, str(target_path))
    if analysis.phash:
        hash_repository.add_hash_record("phash", analysis.phash, str(target_path))
    hash_repository.upsert_file_hash_cache(
        target_path,
        strict_hash=analysis.strict_hash,
        phash=analysis.phash,
    )
    if should_mark_duplicates_dirty:
        DuplicateResultRepository(db_path).mark_dirty(gallery_root, duplicate_dirty_reason)
    invalidate_gallery_index(gallery_root, imported_path=target_path, imported_count=1, imported_item=imported_item)

    return ImportedMedia(
        path=target_path,
        strict_hash=analysis.strict_hash,
        phash=analysis.phash,
        size=analysis.size,
        duplicate_dirty=should_mark_duplicates_dirty,
    )


def invalidate_gallery_index(
    root: Path,
    imported_path: Path | None = None,
    imported_count: int = 0,
    imported_item: dict | None = None,
) -> None:
    clear_image_list_cache(root)
    index_dir = root_image_index_dir(root)
    cache_key = image_scan_cache_key(root, SUPPORTED_EXTENSIONS, SKIP_SCAN_DIR_NAMES)
    cache_digest = digest_for_cache_key(cache_key)
    metadata = load_image_index_summary_metadata(index_dir, cache_key)
    previous_total = metadata.get("total")
    repository = ImageIndexRepository(root_database_path(root))
    stored_items = repository.list_images(cache_digest)
    if imported_path is None:
        updated_total = count_gallery_media(root)
    elif isinstance(previous_total, int):
        updated_total = max(previous_total + imported_count, len(stored_items) + imported_count)
    else:
        updated_total = count_gallery_media(root)
    generated_at = datetime.now().isoformat()
    save_image_index_summary_metadata(
        index_dir,
        root,
        SUPPORTED_EXTENSIONS,
        SKIP_SCAN_DIR_NAMES,
        total=updated_total,
        duplicate_group_count=metadata.get("duplicate_group_count"),
        generated_at=generated_at,
    )
    if imported_path is None:
        repository.clear_image_items(cache_digest)
        repository.replace_timeline_entries(
            cache_digest,
            root=str(root),
            entries=[],
            generated_at=generated_at,
            delete_missing=True,
        )
        timeline_entries = []
    else:
        item = imported_item
        if item is None:
            try:
                item = image_metadata_from_path(root, imported_path, include_exif=True)
            except (OSError, ValueError):
                item = None
        if item is not None:
            item["position"] = repository.insertion_position_for_image(cache_digest, item)
            repository.shift_image_positions_from(cache_digest, item["position"])
            repository.save_index(
                cache_digest,
                root=str(root),
                items=[item],
                total=updated_total,
                generated_at=generated_at,
                duplicate_group_count=metadata.get("duplicate_group_count"),
                timeline_entries=None,
                delete_missing_items=False,
            )
            timeline_entries = repository.load_timeline_entries(cache_digest)
            if not timeline_entries:
                timeline_entries = build_timeline_index_entries([*stored_items, item])
            else:
                existing_keys = {str(entry.get("key", "")) for entry in timeline_entries}
                for entry in build_timeline_index_entries([item]):
                    if str(entry.get("key", "")) not in existing_keys:
                        timeline_entries.append(entry)
        else:
            timeline_entries = repository.load_timeline_entries(cache_digest)
    if timeline_entries:
        repository.replace_timeline_entries(
            cache_digest,
            root=str(root),
            entries=timeline_entries,
            generated_at=generated_at,
            delete_missing=False,
        )
    for cache_path in (
        image_index_cache_path(index_dir, cache_key),
        image_index_summary_path(index_dir, cache_key),
        timeline_index_cache_path(index_dir, cache_key),
    ):
        try:
            cache_path.unlink()
        except OSError:
            pass


def mark_gallery_item_missing(root: Path, relative_path: str) -> dict[str, object]:
    return mark_gallery_items_missing(root, [relative_path])


def mark_gallery_items_missing(root: Path, relative_paths: list[str]) -> dict[str, object]:
    clear_image_list_cache(root)
    index_dir = root_image_index_dir(root)
    cache_key = image_scan_cache_key(root, SUPPORTED_EXTENSIONS, SKIP_SCAN_DIR_NAMES)
    cache_digest = digest_for_cache_key(cache_key)
    metadata = load_image_index_summary_metadata(index_dir, cache_key)
    generated_at = datetime.now().isoformat()
    repository = ImageIndexRepository(root_database_path(root))
    existing_timeline_entries = repository.load_timeline_entries(cache_digest)
    removed_count = repository.mark_items_missing(cache_digest, relative_paths)
    remaining_count = repository.count_images(cache_digest)
    previous_total = metadata.get("total")
    if isinstance(previous_total, int):
        updated_total = max(0, previous_total - max(removed_count, 0))
    elif removed_count > 0:
        updated_total = remaining_count
    else:
        updated_total = count_gallery_media(root)
    save_image_index_summary_metadata(
        index_dir,
        root,
        SUPPORTED_EXTENSIONS,
        SKIP_SCAN_DIR_NAMES,
        total=updated_total,
        duplicate_group_count=metadata.get("duplicate_group_count"),
        generated_at=generated_at,
    )
    if remaining_count > 0 and existing_timeline_entries:
        repository.replace_timeline_entries(
            cache_digest,
            root=str(root),
            entries=existing_timeline_entries,
            generated_at=generated_at,
            delete_missing=False,
        )
    for cache_path in (
        image_index_cache_path(index_dir, cache_key),
        image_index_summary_path(index_dir, cache_key),
        timeline_index_cache_path(index_dir, cache_key),
    ):
        try:
            cache_path.unlink()
        except OSError:
            pass
    return {"total": updated_total, "total_generated_at": generated_at}


def count_gallery_media(root: Path) -> int:
    return sum(
        1
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix.lower() in SUPPORTED_EXTENSIONS
        and not any(part in SKIP_SCAN_DIR_NAMES for part in path.relative_to(root).parts[:-1])
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def root_database_path(root: Path) -> Path:
    return RootContext.from_root(root, ROOT_DATA_DIR, ensure=True).database_path


def root_image_index_dir(root: Path) -> Path:
    return RootContext.from_root(root, ROOT_DATA_DIR, ensure=True).indexes_dir
