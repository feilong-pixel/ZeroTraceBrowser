# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException


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
