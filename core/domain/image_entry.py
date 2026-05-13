# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ImageEntry(BaseModel):
    """
    Index entry for ZeroTraceBrowser, corresponding to each indexed image item.

    Fields align with the return structure of :func:`image_scan_service.image_metadata_from_path`,
    All optional field defaults match the production code (empty string, 0, or None).
    """

    # Path relative to the image root (used by frontend, delete, restore)
    relative_path: str = Field(..., description="Relative path from the image root (forward-slash)")

    # File path — same value as relative_path for backward compatibility
    path: str = Field("", description="Same as relative_path for backward compatibility")

    # File base name
    name: str = Field("", description="File base name")

    # File size in bytes
    size: int = Field(0, description="File size in bytes")

    # Capture datetime from EXIF or file timestamp (ISO format)
    captured_at: str = Field("", description="Capture datetime in ISO format, or empty")

    # File modification datetime in ISO format
    modified_at: str = Field("", description="File modification datetime in ISO format")

    # Timeline display time (YYYY-MM-DD HH:MM:SS)
    timeline_time: str = Field("", description="Timeline display time string")

    # Timeline sort timestamp (unix epoch seconds)
    timeline_ts: int = Field(0, description="Timeline sort timestamp (unix epoch seconds)")

    # Timeline source: "exif" or "file"
    timeline_source: str = Field("", description="Timeline source: 'exif' or 'file'")

    # Whether the file still exists on disk (cache marker)
    exists: bool = Field(True, description="Whether the file still exists on disk")

    # File content hash for duplicate detection (populated via hash DB)
    hash: str | None = Field(None, description="File content hash (populated by hash DB)")

    # Image dimensions (only available when EXIF is read)
    width: int | None = Field(None, description="Image width in pixels")
    height: int | None = Field(None, description="Image height in pixels")

    # --- helpers ---

    @classmethod
    def from_scan_item(cls, item: dict[str, Any]) -> ImageEntry:
        """
        Build an ImageEntry from the dict returned by :func:`image_metadata_from_path`.

        Automatically handles missing fields, type coercion, and edge cases.
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
        """Convert ImageEntry back to a dict compatible with image_scan_service output."""
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
