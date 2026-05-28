# SPDX-License-Identifier: MIT

import os
from datetime import datetime
from .exif_reader import get_exif_datetime, get_file_datetime


def get_target_date_with_source(path: str) -> tuple[datetime, str]:
    exif_time = get_exif_datetime(path)
    if exif_time:
        return exif_time, "exif"
    return get_file_datetime(path), "file"


# Resolve the target date using EXIF first and file time as a fallback.
def get_target_date(path: str) -> datetime:
    target_date, _source = get_target_date_with_source(path)
    return target_date


def get_target_date_source(path: str) -> str:
    _target_date, source = get_target_date_with_source(path)
    return source


# Build the destination folder path in YYYY/MM/DD format.
def build_date_path(base_dir: str, dt: datetime) -> str:
    year = f"{dt.year:04d}"
    month = f"{dt.month:02d}"
    day = f"{dt.day:02d}"
    return os.path.join(base_dir, year, month, day)
