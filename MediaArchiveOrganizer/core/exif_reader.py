# SPDX-License-Identifier: MIT

import os
import contextlib
import io
from datetime import datetime
import exifread
from pathlib import Path

EXIF_TIME_CANDIDATES = [
    "DateTimeOriginal",
    "CreateDate",
    "DateTimeDigitized",
    "ModifyDate",
    "DateTime",
]

# Read the capture time from the image EXIF metadata.
def get_exif_datetime(path: str) -> datetime | None:
    try:
        with open(path, "rb") as f:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                tags = exifread.process_file(f, details=False, strict=False)

        for key, value in tags.items():
            for candidate in EXIF_TIME_CANDIDATES:
                if candidate.lower() in key.lower():
                    dt = _parse_exif_datetime(str(value))
                    if dt:
                        return dt
    except Exception:
        pass

    return None

# Use the file modification time when EXIF data is unavailable.
def get_file_datetime(path: str) -> datetime:
    stat = os.stat(path)
    return datetime.fromtimestamp(stat.st_mtime)

# Parse EXIF date/time string into a datetime object.
def _parse_exif_datetime(value):
    if not value:
        return None

    if isinstance(value, bytes):
        value = value.decode(errors="ignore")

    value = value.strip()

    try:
        return datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
    except Exception:
        return None
