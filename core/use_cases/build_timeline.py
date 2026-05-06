# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field

from core.domain.image_entry import ImageEntry
from core.domain.timeline_item import TimelineItem
from core.repositories.index_repository import IndexRepository


class BuildTimelineRequest(BaseModel):
    """Request to build the timeline index for a root."""

    root_hash: str = Field(default="", description="Root hash from BuildIndexUseCase. If empty, load index from ctx.")


class BuildTimelineUseCase:
    """
    Build the timeline index (timeline.json) from ``ImageEntry`` items.

    This use case orchestrates:
    1. Loading entries from the index (via ``IndexRepository`` or a provided list)
    2. Grouping entries by month using ``build_timeline_fn``
    3. Saving the ``TimelineItem`` list

    ``build_timeline_fn`` can be any callable with the signature:
        ``(items: list[dict[str, Any]]) -> list[dict[str, str]]``
    and is expected to return entries in the same format as
    ``image_index_service.build_timeline_index_entries()``.

    If not provided, the real ``core.services.image_index_service.build_timeline_index_entries``
    will be used.
    """

    def __init__(
        self,
        index_repo: IndexRepository,
        root_context: object,
        build_timeline_fn: Callable | None = None,
    ):
        """
        Args:
            index_repo: An ``IndexRepository`` instance bound to the root context.
            root_context: A RootContext-like object providing ``.root`` (Path),
                ``.indexes_dir`` (Path).
            build_timeline_fn: Optional callable that builds timeline entries
                from a list of dict-based scan items.
        """
        self.index_repo = index_repo
        self.ctx = root_context
        self.build_timeline_fn = build_timeline_fn

    def execute(self, req: BuildTimelineRequest | None = None) -> dict[str, Any]:
        """
        Build the timeline index.

        Returns:
            dict with keys ``status`` ("ok" or "empty"),
            ``count`` (int), and ``entries`` (list[TimelineItem]).
        """
        root_path: Path = self.ctx.root
        root_hash = (req.root_hash.strip()) if req and req.root_hash.strip() else ""

        # 1. Load entries.
        if root_hash:
            entries = self.index_repo.load_index(root_hash)
        else:
            entries = []
            # Try loading from the index if there's a default hash.
            default_root_hash = self._find_default_hash()
            if default_root_hash:
                entries = self.index_repo.load_index(default_root_hash)

        if not entries:
            return {"status": "empty", "count": 0, "entries": []}

        # 2. Build timeline entries from the ImageEntry list.
        scan_items = [entry.to_scan_item() for entry in entries]

        if self.build_timeline_fn is not None:
            raw_entries = self.build_timeline_fn(scan_items)
        else:
            raw_entries = self._default_build(scan_items)

        # 3. Convert to TimelineItem domain objects.
        timeline_items = [TimelineItem.from_dict(e) for e in raw_entries]

        return {
            "status": "ok",
            "count": len(timeline_items),
            "entries": [item.model_dump() for item in timeline_items],
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_default_hash(self) -> str | None:
        """Look for an existing saved index in indexes_dir."""
        indexes_dir: Path = self.ctx.indexes_dir
        if not indexes_dir.exists():
            return None
        for child in indexes_dir.iterdir():
            if child.suffix == ".json" and child.stem:
                return child.stem
        return None

    @staticmethod
    def _default_build(items: list[dict[str, Any]]) -> list[dict[str, str]]:
        """Use the real timeline builder from image_index_service."""
        from core.services.image_index_service import build_timeline_index_entries

        return build_timeline_index_entries(items)
