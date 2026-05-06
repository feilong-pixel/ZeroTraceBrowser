from pathlib import Path
from typing import Optional


class FileRepository:
    """
    File operations repository for ZeroTraceBrowser.
    All file operations (copy/move/delete/restore) must go through
    the FileTransferAdapter in the infrastructure layer (which calls transfer_file).
    """

    def __init__(self, file_transfer_adapter, root_context, metadata_reader=None):
        self.transfer = file_transfer_adapter
# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path
from typing import Optional

from core.services.recycle_paths import build_deleted_path, resolve_deleted_file
from core.services.file_operations import move_file_preserve_times

from MediaArchiveOrganizer.core.file_transfer import transfer_file


class FileRepository:
    """
    File operations repository for ZeroTraceBrowser.
    All file operations (copy/move/delete/restore) must go through
    the FileTransferAdapter in the infrastructure layer (which calls transfer_file).
    """

    def __init__(self, file_transfer_adapter, root_context, metadata_reader=None):
        self.transfer = file_transfer_adapter
        self.ctx = root_context
        self.metadata_reader = metadata_reader  # Optional: for reading EXIF, dimensions, etc.

    # ---------------------------------------------------------
    # Basic operation: copy
    # ---------------------------------------------------------
    def copy(self, src: str, dst: str) -> str:
        """
        Copy a file (uses transfer_file internally)
        """
        src_p = Path(src)
        dst_p = Path(dst)

        dst_p.parent.mkdir(parents=True, exist_ok=True)
        self.transfer.copy(src_p, dst_p)

        return str(dst_p)

    # ---------------------------------------------------------
    # Basic operation: move
    # ---------------------------------------------------------
    def move(self, src: str, dst: str) -> str:
        """
        Move a file (uses transfer_file internally)
        """
        src_p = Path(src)
        dst_p = Path(dst)

        dst_p.parent.mkdir(parents=True, exist_ok=True)
        self.transfer.move(src_p, dst_p)

        return str(dst_p)

    # ---------------------------------------------------------
    # Safe delete: move to recycle bin with timestamp + digest prefix
    # ---------------------------------------------------------
    def safe_delete(self, src: str, relative_path: str | None = None) -> str:
        """
        ZeroTraceBrowser's "delete" moves files to the deleted/ directory.

        Uses ``build_deleted_path`` to generate paths with timestamp and digest prefix,
        e.g. ``deleted/20260426_abcd1234/photo.jpg``, instead of a simple
        ``deleted_dir / relative_path``.

        Args:
            src: Absolute path of the source file.
            relative_path: Path relative to the root. If None, inferred from src.
        """
        src_p = Path(src)
        root: Path = self.ctx.root
        rel = relative_path or str(src_p.relative_to(root))

        deleted_path = build_deleted_path(self.ctx.deleted_dir, root, rel)
        deleted_path.parent.mkdir(parents=True, exist_ok=True)
        self.transfer.move(src_p, deleted_path)

        return str(deleted_path)

    # ---------------------------------------------------------
    # Restore file: move from recycle bin back to original path
    # ---------------------------------------------------------
    def restore(self, deleted_path: str, original_path: str | None = None) -> str:
        """
        Restore a file from deleted/ back to its original path.

        Args:
            deleted_path: Path of the file in the recycle area.
            original_path: Target restore path. If None, inferred via
                ``RootContext.original_path_for``.
        """
        deleted_p = Path(deleted_path)

        if original_path:
            original_p = Path(original_path)
        else:
            original_p = self.ctx.original_path_for(deleted_p)

        original_p.parent.mkdir(parents=True, exist_ok=True)
        self.transfer.move(deleted_p, original_p)

        return str(original_p)

    # ---------------------------------------------------------
    # Scan images (for index building)
    # ---------------------------------------------------------
    def scan_images(self, root_path: str):
        """
        Scan for all image files under a directory.
        """
        root = Path(root_path)
        exts = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}

        for p in root.rglob("*"):
            if p.suffix.lower() in exts and p.is_file():
                yield p

    # ---------------------------------------------------------
    # Read metadata (optional)
    # ---------------------------------------------------------
    def read_metadata(self, path: str) -> Optional[dict]:
        """
        Read image metadata if a metadata_reader is available
        """
        if not self.metadata_reader:
            return None
        return self.metadata_reader.read(Path(path))

    def _ensure_parent_exists(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.metadata_reader = metadata_reader  # Optional: for reading EXIF, dimensions, etc.

    # ---------------------------------------------------------
    # Basic operation: copy
    # ---------------------------------------------------------
    def copy(self, src: str, dst: str) -> str:
        """
        Copy a file (uses transfer_file internally)
        """
        src_p = Path(src)
        dst_p = Path(dst)

        dst_p.parent.mkdir(parents=True, exist_ok=True)
        # self._ensure_parent_exists(dst_p)
        self.transfer.copy(src_p, dst_p)

        return str(dst_p)

    # ---------------------------------------------------------
    # Basic operation: move
    # ---------------------------------------------------------
    def move(self, src: str, dst: str) -> str:
        """
        Move a file (uses transfer_file internally)
        """
        src_p = Path(src)
        dst_p = Path(dst)

        dst_p.parent.mkdir(parents=True, exist_ok=True)
        # self._ensure_parent_exists(dst_p)
        self.transfer.move(src_p, dst_p)

        return str(dst_p)

    # ---------------------------------------------------------
    # Safe delete: move to recycle bin
    # ---------------------------------------------------------
    def safe_delete(self, src: str) -> str:
        """
        ZeroTraceBrowser's "delete" moves files to the deleted/ directory.
        """
        src_p = Path(src)
        deleted_path = self.ctx.deleted_path_for(src_p)

        deleted_path.parent.mkdir(parents=True, exist_ok=True)
        # self._ensure_parent_exists(deleted_path)
        self.transfer.move(src_p, deleted_path)

        return str(deleted_path)

    # ---------------------------------------------------------
    # Restore file: from recycle bin to original path
    # ---------------------------------------------------------
    def restore(self, deleted_path: str) -> str:
        """
        Restore a file from deleted/ back to its original path.
        """
        deleted_p = Path(deleted_path)
        original_path = self.ctx.original_path_for(deleted_p)

        original_path.parent.mkdir(parents=True, exist_ok=True)
        # self._ensure_parent_exists(original_path)
        self.transfer.move(deleted_p, original_path)

        return str(original_path)

    # ---------------------------------------------------------
    # Scan images (for index building)
    # ---------------------------------------------------------
    def scan_images(self, root_path: str):
        """
        Scan for all image files under a directory.
        """
        root = Path(root_path)
        exts = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}

        for p in root.rglob("*"):
            if p.suffix.lower() in exts and p.is_file():
                yield p

    # ---------------------------------------------------------
    # Read metadata (optional)
    # ---------------------------------------------------------
    def read_metadata(self, path: str) -> Optional[dict]:
        """
        Read image metadata if a metadata_reader is available
        """
        if not self.metadata_reader:
            return None
        return self.metadata_reader.read(Path(path))

    # ---------------------------------------------------------
    # Utility functions
    # ---------------------------------------------------------
    def _ensure_parent_exists(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
