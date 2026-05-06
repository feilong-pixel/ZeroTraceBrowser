# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ImageEntry(BaseModel):
    """
    ZeroTraceBrowser 的索引条目，对应 index.json / summary.json 中的每一项。

    字段对齐 :func:`image_scan_service.image_metadata_from_path` 的返回结构，
    所有可选字段的默认值与真实代码一致（空字符串或 0 / None）。
    """

    # 相对于 root 的路径（前端展示、删除、恢复都用它）
    relative_path: str = Field(..., description="Relative path from the image root (forward-slash)")

    # 文件路径（绝对路径或相对路径，与 relative_path 相同值）
    path: str = Field("", description="Same as relative_path for backward compatibility")

    # 文件名
    name: str = Field("", description="File base name")

    # 文件大小（字节）
    size: int = Field(0, description="File size in bytes")

    # 拍摄时间（EXIF 或文件时间，ISO 格式）
    captured_at: str = Field("", description="Capture datetime in ISO format, or empty")

    # 文件修改时间（ISO 格式）
    modified_at: str = Field("", description="File modification datetime in ISO format")

    # 时间线展示时间（YYYY-MM-DD HH:MM:SS 格式）
    timeline_time: str = Field("", description="Timeline display time string")

    # 时间线排序时间戳（秒）
    timeline_ts: int = Field(0, description="Timeline sort timestamp (unix epoch seconds)")

    # 时间线来源（"exif" 或 "file"）
    timeline_source: str = Field("", description="Timeline source: 'exif' or 'file'")

    # 文件是否存在（用于缓存标记）
    exists: bool = Field(True, description="Whether the file still exists on disk")

    # 文件的唯一哈希（用于重复检测，仅通过 hash_db 填充）
    hash: str | None = Field(None, description="File content hash (populated by hash DB)")

    # 图像尺寸（仅当读取 EXIF 时可用）
    width: int | None = Field(None, description="Image width in pixels")
    height: int | None = Field(None, description="Image height in pixels")

    # --- helpers ---

    @classmethod
    def from_scan_item(cls, item: dict[str, Any]) -> ImageEntry:
        """
        从 :func:`image_metadata_from_path` 返回的 dict 构建 ImageEntry。

        自动处理缺失字段、类型转换等边界情况。
        """
        return cls(
            relative_path=str(item.get("relative_path", "")),
            path=str(item.get("path") or item.get("relative_path", "")),
            name=str(item.get("name", "")),
            size=int(item.get("size", 0)),
            captured_at=str(item.get("captured_at", "")),
            modified_at=str(item.get("modified_at", "")),
            timeline_time=str(item.get("timeline_time", "")),
            timeline_ts=int(item.get("timeline_ts", 0)),
            timeline_source=str(item.get("timeline_source", "")),
            exists=bool(item.get("exists", True)),
            hash=str(item["hash"]) if item.get("hash") else None,
            width=int(item["width"]) if item.get("width") else None,
            height=int(item["height"]) if item.get("height") else None,
        )

    def to_scan_item(self) -> dict[str, Any]:
        """将 ImageEntry 转回 dict，兼容 image_scan_service 的返回格式。"""
        return {
            "relative_path": self.relative_path,
            "path": self.path,
            "name": self.name,
            "size": self.size,
            "captured_at": self.captured_at,
            "modified_at": self.modified_at,
            "timeline_time": self.timeline_time,
            "timeline_ts": self.timeline_ts,
            "timeline_source": self.timeline_source,
            "exists": self.exists,
        }
