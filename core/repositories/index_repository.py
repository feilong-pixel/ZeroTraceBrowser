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
        从文件路径和可选的元数据字典构建 ``ImageEntry``。

        如果提供了 ``meta``，优先使用其字段（兼容 image_scan_service 的返回格式）。
        否则从文件系统读取基本信息。
        """
        relative_path = str(path.relative_to(self.ctx.root)).replace("\\", "/")

        if meta:
            # 确保 path 和 relative_path 字段完整
            enriched = dict(meta)
            enriched.setdefault("path", relative_path)
            enriched.setdefault("relative_path", relative_path)
            return ImageEntry.from_scan_item(enriched)

        # 没有 meta 时，从文件系统读取基本信息
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
        """将一批扫描结果（list[dict]）转为 ``ImageEntry`` 列表。"""
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
        """从 JSON 文件加载并反序列化为 ``ImageEntry`` 列表。"""
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
