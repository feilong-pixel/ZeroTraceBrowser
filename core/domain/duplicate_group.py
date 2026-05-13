# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DuplicateItem(BaseModel):
    """A single item within a duplicate group."""

    role: str = Field(..., description="Role: 'kept' or 'duplicate'")
    path: str = Field(..., description="Relative path of the file")
    exists: bool = Field(default=True, description="Whether the file still exists on disk")


class DuplicateGroup(BaseModel):
    """
    Duplicate file group for ZeroTraceBrowser.
    Corresponds to each group persisted in the root database.
    """

    # Group identifier
    group_id: str = Field("", description="Unique group identifier")

    # Duplicate detection method ("strict" or "phash")
    reason: str = Field("-", description="Duplicate detection method: 'strict' or 'phash'")

    # Hash value (key that defines the duplicate group)
    hash: str = Field("", description="Hash value that defines the duplicate group")

    # Relative path of the kept file
    kept_path: str = Field("", description="Relative path of the kept file")

    # All items within this duplicate group
    items: list[DuplicateItem] = Field(default_factory=list, description="Items in the duplicate group")

    # Runtime-only counts (not persisted)
    item_count: int = Field(default=0)
    available_count: int = Field(default=0)

    # --- helpers ---

    @classmethod
    def from_json_group(cls, data: dict[str, Any]) -> DuplicateGroup:
        """Safely build from a duplicate group payload."""
        raw_items: list[dict[str, Any]] = data.get("items", [])
        items = []
        for item in raw_items:
            if isinstance(item, dict) and item.get("path"):
                items.append(
                    DuplicateItem(
                        role=str(item.get("role", "")),
                        path=str(item["path"]),
                        exists=bool(item.get("exists", True)),
                    )
                )
        return cls(
            group_id=str(data.get("group_id", "")),
            reason=str(data.get("reason", "-")),
            hash=str(data.get("hash", "")),
            kept_path=str(data.get("kept_path", "")),
            items=items,
            item_count=len(items),
            available_count=sum(1 for it in items if it.exists),
        )
