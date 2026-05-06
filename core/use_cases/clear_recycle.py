# SPDX-License-Identifier: MIT

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field

from core.services.recycle_paths import remove_empty_deleted_parent
from core.services.recycle_service import (
    archive_delete_log as archive_log_service,
    list_recycle_items as list_recycle_items_service,
    read_delete_log_rows,
)
from core.services.thumbnail_service import (
    deleted_thumbnail_path_for,
)


class ClearRecycleRequest(BaseModel):
    """
    Request to permanently remove ALL files from the recycle area
    (clear recycle bin).
    """

    confirm: bool = Field(default=False)


class ClearRecycleUseCase:
    """
    Permanently remove all files from the root-scoped recycle area.

    On Windows files are moved to the system Recycle Bin; on other
    platforms they are deleted permanently.  After clearing, the
    delete log is archived.
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
            resolve_fn: Optional path resolver for deleted files.
            dispose_fn: Callable for file disposal. If ``None``, defaults to
                ``path.unlink()``.
        """
        self.ctx = root_context
        self.thumbnails_dir = thumbnails_dir
        self.resolve_fn = resolve_fn
        self.dispose_fn = dispose_fn or (lambda p: p.unlink())

    def execute(self, req: ClearRecycleRequest) -> dict[str, Any]:
        """
        Clear all items from the recycle bin.

        Returns a dict with ``status`` ("cleared"), ``removed_count`` (int),
        and ``log_archive`` (dict).
        """
        from fastapi import HTTPException

        if not req.confirm:
            raise HTTPException(status_code=400, detail="Confirmation required")

        removed = 0

        # 1. Get all recycle items.
        log_rows = read_delete_log_rows(self.ctx.logs_dir)
        items = list_recycle_items_service(log_rows, self.ctx.deleted_dir)

        for item in items:
            deleted_to = item.get("deleted_to", "")
            if not deleted_to:
                continue

            # 2. Resolve path.
            if self.resolve_fn is not None:
                file_path = self.resolve_fn(deleted_to)
            else:
                file_path = Path(deleted_to).expanduser().resolve()
                try:
                    file_path.relative_to(self.ctx.deleted_dir)
                except ValueError:
                    continue

            if not file_path.exists() or not file_path.is_file() or file_path.name == ".gitkeep":
                continue

            # 3. Look up the log row.
            log_row = next(
                (r for r in reversed(log_rows) if r.get("deleted_to", "") == str(file_path)),
                None,
            )

            # 4. Prepare and dispose (matching purge logic).
            recycle_path, thumb_path = self._prepare_system_recycle(file_path, log_row)
            self._dispose_file(recycle_path)
            if thumb_path.exists():
                thumb_path.unlink()
            remove_empty_deleted_parent(self.ctx.deleted_dir, recycle_path)

            # 5. Write purge log entry.
            self._write_log(log_row, recycle_path)
            removed += 1

        # 6. Archive the delete log (if anything was removed).
        archive_result = (
            archive_log_service(self.ctx.logs_dir) if removed > 0 else {
                "archived": False,
                "archive_path": "",
                "archived_count": 0,
            }
        )

        return {
            "status": "cleared",
            "removed_count": removed,
            "log_archive": archive_result,
        }

    # ------------------------------------------------------------------
    # Internal helpers (mirrored from PurgeImageUseCase)
    # ------------------------------------------------------------------

    def _prepare_system_recycle(self, deleted_path: Path, log_row: dict | None) -> tuple[Path, Path]:
        """Rename to original filename before recycling, matching route logic."""
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
        self.dispose_fn(path)

    def _write_log(self, log_row: dict | None, file_path: Path) -> None:
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
                str(file_path),
                "purged",
            ])
