# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from core.domain.image_entry import ImageEntry


class IndexRepository:
    def __init__(self, root_context):
        self.ctx = root_context

    def build_entry(self, path: Path, meta: dict | None = None) -> ImageEntry:
        relative_path = str(path.relative_to(self.ctx.root)).replace("\\", "/")

        if meta:
            enriched = dict(meta)
            enriched.setdefault("path", relative_path)
            enriched.setdefault("relative_path", relative_path)
            return ImageEntry.from_scan_item(enriched)

        stat = path.stat()
        return ImageEntry(
            relative_path=relative_path,
            path=relative_path,
            name=path.name,
            size=stat.st_size,
        )

    def build_entries_from_scan(self, items: list[dict[str, Any]]) -> list[ImageEntry]:
        return [ImageEntry.from_scan_item(item) for item in items]

    def compute_root_hash(self, entries: list[ImageEntry]) -> str:
        h = hashlib.sha1()
        for entry in entries:
            h.update(entry.relative_path.encode("utf-8"))
        return h.hexdigest()

    def save_index(self, root_hash: str, entries: list[ImageEntry]) -> None:
        path = self.ctx.index_file(root_hash)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps([entry.model_dump() for entry in entries], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def load_index(self, root_hash: str) -> list[ImageEntry]:
        path = self.ctx.index_file(root_hash)
        if not path.exists():
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [ImageEntry(**item) for item in raw]
