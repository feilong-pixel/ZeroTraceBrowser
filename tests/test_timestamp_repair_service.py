# SPDX-License-Identifier: MIT

from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path

from PIL import Image

from core.services.timestamp_repair_service import repair_timestamps_from_exif
import core.services.timestamp_repair_service as timestamp_repair_mod


def create_exif_image(path: Path, exif_datetime: datetime) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (32, 32), color=(24, 96, 160))
    exif = Image.Exif()
    exif[36867] = exif_datetime.strftime("%Y:%m:%d %H:%M:%S")
    image.save(path, format="JPEG", exif=exif)
    return path


def test_repair_timestamps_from_exif_updates_mtime_and_renames_date_files(tmp_path: Path) -> None:
    root = tmp_path / "gallery"
    exif_datetime = datetime(2018, 3, 28, 22, 47, 36)
    old_datetime = datetime(2026, 5, 25, 12, 0, 0)
    image_path = create_exif_image(root / "20260525-120000.jpg", exif_datetime)
    os.utime(image_path, (old_datetime.timestamp(), old_datetime.timestamp()))
    log_path = tmp_path / "timestamp_fix_log.csv"

    stats = repair_timestamps_from_exif(
        root,
        supported_extensions={".jpg", ".jpeg", ".png"},
        excluded_scan_dirs=set(),
        threshold_days=7,
        sync_modified_time=True,
        rename_from_exif=True,
        log_path=log_path,
    )

    repaired_path = root / "20180328-224736.jpg"
    assert stats["scanned"] == 1
    assert stats["modified_fixed"] == 1
    assert stats["renamed"] == 1
    assert repaired_path.exists()
    assert not image_path.exists()
    assert abs(repaired_path.stat().st_mtime - exif_datetime.timestamp()) < 2
    log_text = log_path.read_text(encoding="utf-8-sig")
    assert "modified_time_fixed;renamed" in log_text
    assert str(image_path) in log_text
    assert str(repaired_path) in log_text


def test_repair_timestamps_from_exif_renames_date_files_with_suffixes(tmp_path: Path) -> None:
    root = tmp_path / "gallery"
    exif_datetime = datetime(2018, 3, 28, 22, 47, 36)
    image_path = create_exif_image(root / "20180328-224738-006_dup1.JPG", exif_datetime)

    stats = repair_timestamps_from_exif(
        root,
        supported_extensions={".jpg", ".jpeg", ".png"},
        excluded_scan_dirs=set(),
        threshold_days=7,
        sync_modified_time=False,
        rename_from_exif=True,
        log_path=tmp_path / "timestamp_fix_log.csv",
    )

    repaired_path = root / "20180328-224736.JPG"
    assert stats["scanned"] == 1
    assert stats["renamed"] == 1
    assert repaired_path.exists()
    assert not image_path.exists()


def test_repair_timestamps_from_exif_skips_non_date_filename_for_rename(tmp_path: Path) -> None:
    root = tmp_path / "gallery"
    exif_datetime = datetime(2018, 3, 28, 22, 47, 36)
    image_path = create_exif_image(root / "family_trip.jpg", exif_datetime)

    stats = repair_timestamps_from_exif(
        root,
        supported_extensions={".jpg", ".jpeg", ".png"},
        excluded_scan_dirs=set(),
        threshold_days=7,
        sync_modified_time=False,
        rename_from_exif=True,
        log_path=tmp_path / "timestamp_fix_log.csv",
    )

    assert stats["scanned"] == 1
    assert stats["renamed"] == 0
    assert stats["rename_skipped"] == 1
    assert image_path.exists()


def test_repair_timestamps_from_exif_can_update_video_mtime_from_ffprobe(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "gallery"
    video_path = root / "20260525-120000.mov"
    video_path.parent.mkdir(parents=True, exist_ok=True)
    video_path.write_bytes(b"not a real video")
    old_datetime = datetime(2026, 5, 25, 12, 0, 0)
    os.utime(video_path, (old_datetime.timestamp(), old_datetime.timestamp()))

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout='{"format":{"tags":{"creation_time":"2018-03-28T22:47:36Z"}},"streams":[]}',
            stderr="",
        )

    monkeypatch.setattr(timestamp_repair_mod.subprocess, "run", fake_run)

    stats = repair_timestamps_from_exif(
        root,
        supported_extensions={".jpg", ".jpeg", ".mov"},
        excluded_scan_dirs=set(),
        threshold_days=7,
        sync_modified_time=True,
        rename_from_exif=True,
        include_videos=True,
        log_path=tmp_path / "timestamp_fix_log.csv",
    )

    repaired_path = root / "20180328-224736.mov"
    expected_timestamp = datetime(2018, 3, 28, 22, 47, 36).timestamp()
    assert stats["scanned"] == 1
    assert stats["modified_fixed"] == 1
    assert stats["renamed"] == 1
    assert repaired_path.exists()
    assert abs(repaired_path.stat().st_mtime - expected_timestamp) < 2


def test_repair_timestamps_from_exif_skips_videos_by_default(tmp_path: Path) -> None:
    root = tmp_path / "gallery"
    video_path = root / "20260525-120000.mov"
    video_path.parent.mkdir(parents=True, exist_ok=True)
    video_path.write_bytes(b"not a real video")

    stats = repair_timestamps_from_exif(
        root,
        supported_extensions={".jpg", ".jpeg", ".mov"},
        excluded_scan_dirs=set(),
        threshold_days=7,
        sync_modified_time=True,
        rename_from_exif=True,
        log_path=tmp_path / "timestamp_fix_log.csv",
    )

    assert stats["scanned"] == 0
    assert video_path.exists()
