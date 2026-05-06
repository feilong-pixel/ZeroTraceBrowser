# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path
from typing import Optional

from core.services.recycle_paths import build_deleted_path


class FileRepository:
    """
    File operations repository for ZeroTraceBrowser.
    All file operations (copy/move/delete/restore) must go through
    the FileTransferAdapter in the infrastructure layer.
    """

    def __init__(self, file_transfer_adapter, root_context, metadata_reader=None):
        self.transfer = file_transfer_adapter
        self.ctx = root_context
        self.metadata_reader = metadata_reader

    def copy(self, src: str, dst: str) -> str:
        src_p = Path(src)
        dst_p = Path(dst)
        dst_p.parent.mkdir(parents=True, exist_ok=True)
        self.transfer.copy(src_p, dst_p)
        return str(dst_p)

    def move(self, src: str, dst: str) -> str:
        src_p = Path(src)
        dst_p = Path(dst)
        dst_p.parent.mkdir(parents=True, exist_ok=True)
        self.transfer.move(src_p, dst_p)
        return str(dst_p)

    def safe_delete(self, src: str, relative_path: str | None = None) -> str:
        src_p = Path(src)
        root: Path = self.ctx.root
        rel = relative_path or str(src_p.relative_to(root))
        deleted_path = build_deleted_path(self.ctx.deleted_dir, root, rel)
        deleted_path.parent.mkdir(parents=True, exist_ok=True)
        self.transfer.move(src_p, deleted_path)
        return str(deleted_path)

    def restore(self, deleted_path: str, original_path: str | None = None) -> str:
        deleted_p = Path(deleted_path)
        original_p = Path(original_path) if original_path else self.ctx.original_path_for(deleted_p)
        original_p.parent.mkdir(parents=True, exist_ok=True)
        self.transfer.move(deleted_p, original_p)
        return str(original_p)

    def scan_images(self, root_path: str):
        root = Path(root_path)
        exts = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
        for path in root.rglob("*"):
            if path.suffix.lower() in exts and path.is_file():
                yield path

    def read_metadata(self, path: str) -> Optional[dict]:
        if not self.metadata_reader:
            return None
        return self.metadata_reader.read(Path(path))
