# SPDX-License-Identifier: MIT

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field

from core.services.file_operations import move_file_preserve_times, resolve_under_root
from core.services.image_scan_service import clear_image_list_cache
from core.services.recycle_paths import remove_empty_deleted_parent
from core.services.thumbnail_service import thumbnail_path_for


class RestoreImageRequest(BaseModel):
    """
    Request to restore a deleted file from the recycle area back to its
    original location.
    """

    deleted_to: str = Field(..., min_length=1)


class RestoreImageUseCase:
    """
    Restore a deleted image from the root-scoped deleted/ directory back
    to its original location.

    This use case mirrors the logic in routes/recycle.py -> restore_deleted_item().
    """

    def __init__(
        self,
        root_context: object,
        thumbnails_dir: Path,
        *,
        resolve_fn: Callable[[str], Path] | None = None,
    ):
        """
        Args:
            root_context: A RootContext-like object, providing ``.root`` (Path),
                ``.deleted_dir`` (Path), ``.logs_dir`` (Path), and ``.thumbnails_dir`` (Path).
            thumbnails_dir: The root-scoped thumbnails directory.
            resolve_fn: Optional path resolver for the deleted file (analogous to
                ``RouteContext.resolve_deleted_file``). If provided, it will be used
                instead of a strict ``deleted_dir`` containment check. If ``None``
                (default), the use case enforces that ``deleted_to`` is under
                ``root_context.deleted_dir``.
        """
        self.ctx = root_context
        self.thumbnails_dir = thumbnails_dir
        self.resolve_fn = resolve_fn

    def execute(self, req: RestoreImageRequest) -> dict[str, Any]:
        """
        Execute the restore workflow.

        Returns a dict with keys ``status`` ("restored") and ``restored_to`` (str).
        Raises HTTPException on errors.
        """
        from fastapi import HTTPException

        # 1. Resolve and validate the deleted file path.
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

        # 2. Look up the delete log row for this file.
        log_row = self._find_log_row(deleted_path)
        if not log_row or not log_row.get("root") or not log_row.get("relative_path"):
            raise HTTPException(status_code=400, detail="No restore target found in delete log")

        # 3. Resolve the original restore path.
        restore_root = Path(log_row["root"]).expanduser().resolve()
        restore_path = (restore_root / log_row["relative_path"]).resolve()
        try:
            restore_path.relative_to(restore_root)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Restore path escapes original root") from exc

        if restore_path.exists():
            raise HTTPException(status_code=409, detail="Original path already exists")

        # 4. Move the file back to its original location.
        restore_path.parent.mkdir(parents=True, exist_ok=True)
        move_file_preserve_times(deleted_path, restore_path)

        # 5. Clear in-memory cache for the affected root.
        clear_image_list_cache(restore_root)

                # 6. Remove stale thumbnails.
        # 6a. Remove the original-file thumbnail (if one was cached before deletion).
        stale_thumb = thumbnail_path_for(self.thumbnails_dir, restore_root, log_row["relative_path"])
        if stale_thumb.exists():
            stale_thumb.unlink()

        # 6b. Remove the deleted-file thumbnail, matching the original
        #     route logic (ctx.deleted_thumbnail_path_for).
        from core.services.thumbnail_service import deleted_thumbnail_path_for as deleted_thumb_fn
        stale_deleted_thumb = deleted_thumb_fn(self.thumbnails_dir, deleted_path)
        if stale_deleted_thumb.exists():
            stale_deleted_thumb.unlink()

        # 7. Clean up empty parent directories in the deleted tree.
        remove_empty_deleted_parent(self.ctx.deleted_dir, deleted_path)

        # 8. Write restore log entry.
        self._write_log(restore_root, log_row["relative_path"], deleted_path)

        return {"status": "restored", "restored_to": str(restore_path)}

    def _find_log_row(self, deleted_path: Path) -> dict | None:
        """Search the delete log (in reverse order) for a row matching the deleted file path."""
        log_path = self.ctx.logs_dir / "delete_log.csv"
        if not log_path.exists():
            return None

        deleted_path_str = str(deleted_path)
        with log_path.open("r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        # Reverse search to find most recent matching row (matching route behaviour).
        for row in reversed(rows):
            if row.get("deleted_to", "") == deleted_path_str:
                return row
        return None

    def _write_log(self, root: Path, relative_path: str, deleted_path: Path) -> None:
        """Append a restore row to the delete CSV log."""
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
                str(root),
                relative_path,
                str(deleted_path),
                "restored",
            ])
