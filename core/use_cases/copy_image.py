# SPDX-License-Identifier: MIT

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from core.services.file_operations import copy_file_preserve_times, resolve_under_root
from core.services.image_scan_service import clear_image_list_cache


class CopyImageRequest(BaseModel):
    """
    Request to copy an image from the active root to a target directory.

    If ``target_dir`` is empty, ``default_copy_target`` from settings is used.
    """

    relative_path: str = Field(..., min_length=1)
    target_dir: str = Field(default="", min_length=0)


class CopyImageUseCase:
    """
    Copy an image from the active root to a target directory.

    This use case mirrors the logic in routes/images.py -> copy_image().
    """

    def __init__(self, root_context: object, default_copy_target: str = ""):
        """
        Args:
            root_context: A RootContext-like object, providing ``.root`` (Path)
                and ``.logs_dir`` (Path).
            default_copy_target: Fallback target directory path from settings.
        """
        self.ctx = root_context
        self.default_copy_target = default_copy_target

    def execute(self, req: CopyImageRequest) -> dict:
        """
        Execute the copy workflow.

        Returns a dict with keys ``status`` ("copied") and ``copied_to`` (str).
        Raises HTTPException(404) if the image is missing or no target is configured.
        """
        from fastapi import HTTPException

        root: Path = self.ctx.root

        # 1. Safely resolve the source image path.
        image_path = resolve_under_root(root, req.relative_path)
        if not image_path.exists() or not image_path.is_file():
            raise HTTPException(status_code=404, detail="Image not found")

        # 2. Determine the target directory.
        target_root_value = req.target_dir.strip() or self.default_copy_target
        if not target_root_value:
            raise HTTPException(status_code=400, detail="No copy target configured")

        target_root = Path(target_root_value).expanduser().resolve()
        target_root.mkdir(parents=True, exist_ok=True)

        # 3. Determine the target file path, avoiding name collisions.
        target_path = target_root / image_path.name
        if target_path.exists():
            stem = target_path.stem
            suffix = target_path.suffix
            counter = 1
            while True:
                candidate = target_root / f"{stem}_{counter}{suffix}"
                if not candidate.exists():
                    target_path = candidate
                    break
                counter += 1

        # 4. Perform the copy.
        copy_file_preserve_times(image_path, target_path)

        # 5. Clear the in-memory image list cache.
        clear_image_list_cache(root)

        # 6. Write copy log entry.
        self._write_log(root, req.relative_path, target_path)

        return {"status": "copied", "copied_to": str(target_path)}

    def _write_log(self, root: Path, relative_path: str, target_path: Path) -> None:
        """Append a row to the copy CSV log."""
        import csv

        log_path = self.ctx.logs_dir / "copy_log.csv"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        if not log_path.exists():
            with log_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "root", "relative_path", "copied_to"])

        with log_path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(),
                str(root),
                relative_path,
                str(target_path),
            ])

