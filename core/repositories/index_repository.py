import json
import hashlib
from pathlib import Path
from core.domain.image_entry import ImageEntry

class IndexRepository:
    def __init__(self, root_context):
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

from core.domain.image_entry import ImageEntry


class IndexRepository:
    def __init__(self, root_context):
        self.ctx = root_context

    def build_entry(self, path: Path, meta: dict | None = None) -> ImageEntry:
        """
        Build an ``ImageEntry`` from a file path and optional metadata dict.

        When ``meta`` is provided, its fields take priority (compatible with image_scan_service output).
        Otherwise, read basic info from the filesystem.
        """
        relative_path = str(path.relative_to(self.ctx.root)).replace("\\", "/")

        if meta:
            # Ensure path and relative_path fields are populated
            enriched = dict(meta)
            enriched.setdefault("path", relative_path)
            enriched.setdefault("relative_path", relative_path)
            return ImageEntry.from_scan_item(enriched)

        # Without meta, read basic info from the filesystem
        stat = path.stat()
        return ImageEntry(
            relative_path=relative_path,
            path=relative_path,
            name=path.name,
            size=stat.st_size,
        )

    def build_entries_from_scan(
        self, items: list[dict[str, Any]]
    ) -> list[ImageEntry]:
        """Convert a batch of scan results (list[dict]) to a list of ``ImageEntry``."""
        return [ImageEntry.from_scan_item(item) for item in items]

    def compute_root_hash(self, entries: list[ImageEntry]) -> str:
        h = hashlib.sha1()
        for e in entries:
            h.update(e.relative_path.encode("utf-8"))
        return h.hexdigest()

    def save_index(self, root_hash: str, entries: list[ImageEntry]) -> None:
        path = self.ctx.index_file(root_hash)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps([e.model_dump() for e in entries], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def load_index(self, root_hash: str) -> list[ImageEntry]:
        """Load and deserialize from a JSON file into a list of ``ImageEntry``."""
        path = self.ctx.index_file(root_hash)
        if not path.exists():
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [ImageEntry(**item) for item in raw]

    def build_entry(self, path: Path, meta: dict):
        return ImageEntry(
            path=str(path),
            relative_path=str(path.relative_to(self.ctx.root)),
            timestamp=meta.get("timestamp"),
            width=meta.get("width"),
            height=meta.get("height"),
            hash=meta.get("hash"),
        )

    def compute_root_hash(self, entries):
        h = hashlib.sha1()
        for e in entries:
            h.update(e.path.encode())
        return h.hexdigest()

    def save_index(self, root_hash, entries):
        path = self.ctx.index_file(root_hash)
        path.write_text(
            json.dumps([e.dict() for e in entries], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
