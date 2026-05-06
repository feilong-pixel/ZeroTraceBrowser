# SPDX-License-Identifier: MIT

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field

from core.services.image_scan_service import clear_image_list_cache
from core.services.recycle_paths import remove_empty_deleted_parent
from core.services.thumbnail_service import (
    deleted_thumbnail_path_for,
)


class PurgeImageRequest(BaseModel):
    """
    Request to permanently remove a single file from the recycle area.
    """

    deleted_to: str = Field(..., min_length=1)


class PurgeImageResult(BaseModel):
    status: str = "purged"
    deleted_to: str = ""


class PurgeImageUseCase:
    """
    Permanently remove (purge) a deleted file from the root-scoped
    recycle area.

    On Windows the file is moved to the system Recycle Bin; on other
    platforms it is deleted permanently.  The matching delete log row
    is updated with action ``"purged"``.
    """

    def __init__(
        self,
        root_context: object,
        thumbnails_dir: Path,
        *,
        resolve_fn: Callable[[str], Path] | None = None,
        dispose_fn: Callable[[Path], None] | None = None,
    ):
        """
        Args:
            root_context: A RootContext-like object, providing ``.root`` (Path),
                ``.deleted_dir`` (Path), ``.logs_dir`` (Path).
            thumbnails_dir: The root-scoped thumbnails directory.
            resolve_fn: Optional path resolver (see ``RestoreImageUseCase``).
            dispose_fn: Callable for file disposal. If ``None``, defaults to
                ``path.unlink()``.
        """
        self.ctx = root_context
        self.thumbnails_dir = thumbnails_dir
        self.resolve_fn = resolve_fn
        self.dispose_fn = dispose_fn or (lambda p: p.unlink())

    def execute(self, req: PurgeImageRequest) -> dict[str, Any]:
        """
        Purge a single deleted file.

        Returns a dict with ``status`` ("purged") and ``deleted_to`` (str).
        """
        from fastapi import HTTPException

        # 1. Resolve and validate path.
        if self.resolve_fn is not None:
            deleted_path = self.resolve_fn(req.deleted_to)
        else:
            deleted_path = Path(req.deleted_to).expanduser().resolve()
            try:
                deleted_path.relative_to(self.ctx.deleted_dir)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Invalid deleted file path") from exc

        if not deleted_path.exists() or not deleted_path.is_file():
            raise HTTPException(status_code=404, detail="Deleted file not found")

        # 2. Look up the log row.
        log_row = self._find_log_row(deleted_path)

        # 3. Handle system recycle for Windows (matching route logic:
        #    ctx.prepare_system_recycle_path -> original filename handling)
        recycle_path, thumb_path = self._prepare_system_recycle(deleted_path, log_row)

        # 4. Dispose of the file.
        self._dispose_file(recycle_path)

        # 5. Remove the corresponding thumbnail.
        if thumb_path.exists():
            thumb_path.unlink()

        # 6. Cleanup empty parent dirs.
        remove_empty_deleted_parent(self.ctx.deleted_dir, recycle_path)

        # 7. Update delete log.
        self._write_log(log_row, deleted_path)

        return {"status": "purged", "deleted_to": str(deleted_path)}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_log_row(self, deleted_path: Path) -> dict | None:
        """Search the delete log (reverse) for a row matching the file path."""
        log_path = self.ctx.logs_dir / "delete_log.csv"
        if not log_path.exists():
            return None
        deleted_str = str(deleted_path)
        with log_path.open("r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        for row in reversed(rows):
            if row.get("deleted_to", "") == deleted_str:
                return row
        return None

    def _prepare_system_recycle(self, deleted_path: Path, log_row: dict | None) -> tuple[Path, Path]:
        """
        Mirror of ``RouteContext.prepare_system_recycle_path``:
        If the original filename differs from the hashed deleted filename,
        rename the file back to its original name before recycling.
        """
        thumb_path = deleted_thumbnail_path_for(self.thumbnails_dir, deleted_path)
        original_name = Path(log_row.get("relative_path", "")).name if log_row else ""
        if not original_name or deleted_path.name == original_name:
            return deleted_path, thumb_path

        restored_name_path = deleted_path.parent / original_name
        if restored_name_path.exists():
            return deleted_path, thumb_path

        from core.services.file_operations import move_file_preserve_times
        move_file_preserve_times(deleted_path, restored_name_path)
        return restored_name_path, thumb_path

    def _dispose_file(self, path: Path) -> None:
        """Call the injected dispose function, or delete permanently as fallback."""
        self.dispose_fn(path)

    def _write_log(self, log_row: dict | None, deleted_path: Path) -> None:
        """Append a 'purged' row to the delete CSV log."""
        log_path = self.ctx.logs_dir / "delete_log.csv"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        if not log_path.exists():
            with log_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "root", "relative_path", "deleted_to", "action"])

        with log_path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(),
                log_row["root"] if log_row else "",
                log_row["relative_path"] if log_row else "",
                str(deleted_path),
                "purged",
            ])
