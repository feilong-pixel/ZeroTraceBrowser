# SPDX-License-Identifier: MIT

from __future__ import annotations

import time
from pathlib import Path

from fastapi import HTTPException
from MediaArchiveOrganizer.core.file_transfer import transfer_file


def replace_with_retry(source: Path, target: Path, attempts: int = 3) -> None:
    for attempt in range(attempts):
        try:
            source.replace(target)
            return
        except PermissionError:
            if attempt >= attempts - 1:
                raise
            time.sleep(0.05 * (attempt + 1))


def copy_file_preserve_times(src: Path, dst: Path) -> None:
    transfer_file(src, dst, "copy")


def move_file_preserve_times(src: Path, dst: Path) -> None:
    transfer_file(src, dst, "move")


def resolve_under_root(root: Path, candidate: str) -> Path:
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Path escapes configured root") from exc
    return resolved
