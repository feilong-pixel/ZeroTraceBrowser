# SPDX-License-Identifier: MIT

from __future__ import annotations

import csv
import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable

from MediaArchiveOrganizer.core.exif_reader import get_exif_datetime


ProgressCallback = Callable[[dict[str, int | str]], None]
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v", ".avi", ".mkv"}

DATE_STEM_PATTERNS = (
    re.compile(r"^\d{8}[-_]\d{6}(?:[-_]\d+)?(?:_dup\d+)?$"),
    re.compile(r"^\d{14}(?:[-_]\d+)?(?:_dup\d+)?$"),
    re.compile(r"^\d{4}-\d{2}-\d{2}[ _-]\d{2}[-_]\d{2}[-_]\d{2}(?:[-_]\d+)?(?:_dup\d+)?$"),
)


def is_date_formatted_stem(stem: str) -> bool:
    return any(pattern.match(stem) for pattern in DATE_STEM_PATTERNS)


def unique_exif_name(path: Path, exif_datetime: datetime) -> Path:
    base_name = exif_datetime.strftime("%Y%m%d-%H%M%S")
    suffix = path.suffix
    candidate = path.with_name(f"{base_name}{suffix}")
    if candidate == path or not candidate.exists():
        return candidate

    for index in range(1, 1000):
        candidate = path.with_name(f"{base_name}_{index:03d}{suffix}")
        if not candidate.exists():
            return candidate

    raise FileExistsError(f"No available timestamp filename for {path}")


def parse_media_creation_time(value: str) -> datetime | None:
    value = value.strip()
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1]
    try:
        return datetime.fromisoformat(value).replace(tzinfo=None)
    except ValueError:
        return None


def get_video_creation_datetime(path: Path) -> datetime | None:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if result.returncode != 0 or not result.stdout.strip():
        return None

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None

    candidates = []
    format_tags = payload.get("format", {}).get("tags", {})
    if isinstance(format_tags, dict):
        candidates.append(format_tags.get("creation_time"))
    streams = payload.get("streams", [])
    if isinstance(streams, list):
        for stream in streams:
            if isinstance(stream, dict):
                tags = stream.get("tags", {})
                if isinstance(tags, dict):
                    candidates.append(tags.get("creation_time"))

    for candidate in candidates:
        if isinstance(candidate, str):
            parsed = parse_media_creation_time(candidate)
            if parsed is not None:
                return parsed
    return None


def capture_datetime_for_path(path: Path) -> tuple[datetime | None, str]:
    if path.suffix.lower() in VIDEO_EXTENSIONS:
        return get_video_creation_datetime(path), "media_creation_time"
    return get_exif_datetime(str(path)), "exif"


def repair_timestamps_from_exif(
    root: Path,
    *,
    supported_extensions: set[str],
    excluded_scan_dirs: set[str],
    threshold_days: int,
    sync_modified_time: bool,
    rename_from_exif: bool,
    include_videos: bool = False,
    log_path: Path,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, int]:
    threshold_seconds = threshold_days * 24 * 60 * 60
    stats = {
        "scanned": 0,
        "no_exif": 0,
        "no_timestamp": 0,
        "within_threshold": 0,
        "modified_fixed": 0,
        "renamed": 0,
        "rename_skipped": 0,
        "failed": 0,
    }
    log_rows: list[dict[str, str]] = []

    def flush_log_rows() -> None:
        if not log_rows:
            return
        log_path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not log_path.exists()
        with log_path.open("a", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "timestamp",
                    "status",
                    "old_path",
                    "new_path",
                    "exif_datetime",
                    "timestamp_source",
                    "old_modified_at",
                    "new_modified_at",
                    "diff_days",
                    "message",
                ],
            )
            if write_header:
                writer.writeheader()
            writer.writerows(log_rows)
        log_rows.clear()

    def add_log_row(
        *,
        status: str,
        old_path: Path,
        new_path: Path | None,
        exif_datetime: datetime | None,
        timestamp_source: str = "",
        old_modified_at: datetime | None,
        new_modified_at: datetime | None,
        diff_days: float | None,
        message: str = "",
    ) -> None:
        log_rows.append(
            {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "status": status,
                "old_path": str(old_path),
                "new_path": str(new_path or old_path),
                "exif_datetime": exif_datetime.isoformat(sep=" ") if exif_datetime else "",
                "timestamp_source": timestamp_source,
                "old_modified_at": old_modified_at.isoformat(sep=" ") if old_modified_at else "",
                "new_modified_at": new_modified_at.isoformat(sep=" ") if new_modified_at else "",
                "diff_days": f"{diff_days:.2f}" if diff_days is not None else "",
                "message": message,
            }
        )

    for path in iter_repair_candidates(root, supported_extensions, excluded_scan_dirs, include_videos):
        stats["scanned"] += 1
        original_path = path
        current_path = path
        try:
            exif_datetime, timestamp_source = capture_datetime_for_path(current_path)
            if exif_datetime is None:
                if current_path.suffix.lower() in VIDEO_EXTENSIONS:
                    stats["no_timestamp"] += 1
                else:
                    stats["no_exif"] += 1
                continue

            stat = current_path.stat()
            old_modified_at = datetime.fromtimestamp(stat.st_mtime)
            diff_seconds = abs(stat.st_mtime - exif_datetime.timestamp())
            diff_days = diff_seconds / (24 * 60 * 60)
            status_parts: list[str] = []

            if sync_modified_time and diff_seconds > threshold_seconds:
                os.utime(current_path, (stat.st_atime, exif_datetime.timestamp()))
                stats["modified_fixed"] += 1
                status_parts.append("modified_time_fixed")
                new_modified_at = exif_datetime
            else:
                if sync_modified_time:
                    stats["within_threshold"] += 1
                new_modified_at = old_modified_at

            if rename_from_exif:
                if is_date_formatted_stem(current_path.stem):
                    target_path = unique_exif_name(current_path, exif_datetime)
                    if target_path != current_path:
                        current_path.rename(target_path)
                        current_path = target_path
                        stats["renamed"] += 1
                        status_parts.append("renamed")
                else:
                    stats["rename_skipped"] += 1

            if status_parts:
                add_log_row(
                    status=";".join(status_parts),
                    old_path=original_path,
                    new_path=current_path,
                    exif_datetime=exif_datetime,
                    timestamp_source=timestamp_source,
                    old_modified_at=old_modified_at,
                    new_modified_at=new_modified_at,
                    diff_days=diff_days,
                )

        except Exception as exc:
            stats["failed"] += 1
            add_log_row(
                status="failed",
                old_path=original_path,
                new_path=current_path,
                exif_datetime=None,
                timestamp_source="",
                old_modified_at=None,
                new_modified_at=None,
                diff_days=None,
                message=str(exc),
            )

        if stats["scanned"] % 25 == 0:
            flush_log_rows()
            if progress_callback:
                progress_callback({**stats})

    flush_log_rows()
    if progress_callback:
        progress_callback({**stats, "status": "done"})

    return stats


def iter_repair_candidates(
    root: Path,
    supported_extensions: set[str],
    excluded_scan_dirs: set[str],
    include_videos: bool = False,
) -> Iterable[Path]:
    excluded_names = {name.lower() for name in excluded_scan_dirs}
    image_extensions = supported_extensions - VIDEO_EXTENSIONS
    candidate_extensions = image_extensions | (VIDEO_EXTENSIONS if include_videos else set())

    for current_root, dir_names, file_names in os.walk(root):
        dir_names[:] = [name for name in dir_names if name.lower() not in excluded_names]
        for file_name in file_names:
            path = Path(current_root) / file_name
            if path.suffix.lower() in candidate_extensions:
                yield path
