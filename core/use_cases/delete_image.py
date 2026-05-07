# SPDX-License-Identifier: MIT

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from core.services.file_operations import move_file_preserve_times, resolve_under_root
from core.services.image_scan_service import clear_image_list_cache
from core.services.recycle_paths import build_deleted_path
from core.services.thumbnail_service import thumbnail_path_for


class DeleteImageRequest(BaseModel):
    """
    Request to delete an image from the active root.

    The image is moved to the root-scoped deleted/ directory
    (not permanently removed), and the operation is logged.
    """

    relative_path: str = Field(..., min_length=1)


class DeleteImageUseCase:
    """
    Safely delete (move to recycle) an image within the active root.

    This use case mirrors the logic in routes/images.py -> delete_image(),
    providing the same behavior through a testable, dependency-injected class.

    In phase 2 of the refactor, the direct service function calls below
    will be replaced with repository abstractions (FileRepository,
    LogRepository, ThumbnailRepository, CacheRepository).
    """

    def __init__(
        self,
        root_context: object,
        thumbnails_dir: Path,
        thumbnail_size: tuple[int, int],
    ):
        """
        Args:
            root_context: A RootContext-like object, providing at minimum
                ``.root`` (Path), ``.deleted_dir`` (Path), ``.thumbnails_dir`` (Path).
            thumbnails_dir: The root-scoped thumbnails directory
                (``RootContext.thumbnails_dir``).
            thumbnail_size: The (width, height) tuple used for thumbnail generation.
        """
        self.ctx = root_context
        self.thumbnails_dir = thumbnails_dir
        self.thumbnail_size = thumbnail_size

    def execute(self, req: DeleteImageRequest) -> dict:
        """
        Execute the delete (move-to-recycle) workflow.

        Returns a dict with keys ``status`` (one of "deleted" or "missing")
        and, when applicable, ``deleted_to`` (str) or ``relative_path`` (str).
        """
        root: Path = self.ctx.root
        relative_path = req.relative_path

        # 1. Safely resolve the image path within the root.
        image_path = resolve_under_root(root, relative_path)

        # 2. File does not exist — clean up stale state and return "missing".
        if not image_path.exists() or not image_path.is_file():
            clear_image_list_cache(root)
            stale_thumb = thumbnail_path_for(self.thumbnails_dir, root, relative_path)
            if stale_thumb.exists():
                stale_thumb.unlink()
            return {"status": "missing", "relative_path": relative_path}

        # 3. Build the target deleted path (timestamp + digest prefix).
        deleted_path = build_deleted_path(self.ctx.deleted_dir, root, relative_path)
        deleted_path.parent.mkdir(parents=True, exist_ok=True)

        # 4. Move the file to the recycle area.
        move_file_preserve_times(image_path, deleted_path)

        # 5. Clear the in-memory image list cache so the gallery refreshes.
        clear_image_list_cache(root)

        # 6. Write delete log entry.
        self._write_log(root, relative_path, deleted_path)

        # 7. Remove the stale thumbnail, if one exists.
        stale_thumb = thumbnail_path_for(self.thumbnails_dir, root, relative_path)
        if stale_thumb.exists():
            stale_thumb.unlink()

        return {"status": "deleted", "deleted_to": str(deleted_path)}

    # ------------------------------------------------------------------
    # Internal helpers – easily replaceable with LogRepository in phase 2
    # ------------------------------------------------------------------

    def _write_log(self, root: Path, relative_path: str, deleted_path: Path) -> None:
        """Append a row to the delete CSV log."""
        log_path = self.ctx.logs_dir / "delete_log.csv"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        import csv

        # Ensure header exists if the file is new.
        if not log_path.exists():
            log_path.parent.mkdir(parents=True, exist_ok=True)
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
                "deleted",
            ])
