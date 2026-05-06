# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from core.domain.duplicate_group import DuplicateGroup


class DetectDuplicatesRequest(BaseModel):
    """Request to load and query duplicate detection results."""

    json_path: str = Field(default="", description="Path to a duplicates.json file. If empty, auto-discover.")
    offset: int = Field(default=0, ge=0)
    limit: int | None = Field(default=None, gt=0)
    method: str | None = Field(default=None, description="Filter by method: 'strict' or 'phash'")


class DetectDuplicatesUseCase:
    """
    Load, filter, and query duplicate detection results from ``duplicates.json``.

    Unlike the old skeleton that assumed direct hash DB computation (which is
    actually done by ``MediaArchiveOrganizer``), this use case works with
    the output of the task system.

    In future phases this can be extended to also read ``hash_db.json`` and
    generate ad-hoc duplicate reports.
    """

    def __init__(self, root_context: object):
        """
        Args:
            root_context: A RootContext-like object providing ``.root`` (Path),
                ``.duplicates_path`` (Path), ``.logs_dir`` (Path).
        """
        self.ctx = root_context

    def execute(self, req: DetectDuplicatesRequest) -> dict[str, Any]:
        """
        Load and filter duplicate results.

        Returns:
            dict with keys ``available`` (bool), ``groups`` (list),
            ``group_count`` (int), ``has_more`` (bool), etc.
        """
        # 1. Locate the duplicates.json file.
        json_path = self._resolve_json_path(req)
        if json_path is None or not json_path.exists():
            return {
                "available": False,
                "groups": [],
                "group_count": 0,
                "has_more": False,
            }

        # 2. Load and parse the payload.
        with json_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)

        destination_root = str(payload.get("destination_root", ""))
        method_filter = (req.method or "").strip().lower() if req.method else ""

        # 3. Filter and paginate groups.
        raw_groups: list[dict[str, Any]] = payload.get("groups", [])
        if not isinstance(raw_groups, list):
            raw_groups = []

        matched_count = 0
        result_groups: list[dict[str, Any]] = []
        has_more = False

        method_counts: dict[str, int] = {"phash": 0, "strict": 0}

        for raw_group in raw_groups:
            group_method = str(raw_group.get("reason", "-")).strip().lower()
            if group_method in method_counts:
                method_counts[group_method] += 1

            if method_filter and group_method != method_filter:
                continue

            # Build domain object (also validates structure).
            try:
                group = DuplicateGroup.from_json_group(raw_group)
            except (ValueError, TypeError):
                continue

            # At least two available files needed to be meaningful.
            if group.available_count < 2:
                continue

            # Apply offset/limit pagination.
            if req.limit is not None:
                if matched_count < req.offset:
                    matched_count += 1
                    continue
                if len(result_groups) >= req.limit:
                    has_more = True
                    break

            matched_count += 1
            result_groups.append({
                "group_id": group.group_id,
                "reason": group.reason,
                "hash": group.hash,
                "kept_path": group.kept_path,
                "item_count": group.item_count,
                "available_count": group.available_count,
                "items": [item.model_dump() for item in group.items],
                "preview_paths": [item.path for item in group.items if item.exists],
            })

        # 4. Compute total group count.
        if req.limit is None:
            group_count = len(result_groups)
        elif method_filter:
            group_count = method_counts.get(method_filter, 0)
        else:
            group_count = payload.get("group_count", len(raw_groups))
            if not isinstance(group_count, int):
                group_count = len(raw_groups)

        return {
            "available": True,
            "json_path": str(json_path),
            "generated_at": payload.get("generated_at"),
            "destination_root": destination_root,
            "groups": result_groups,
            "group_count": group_count,
            "method_counts": method_counts,
            "page_offset": req.offset,
            "page_limit": req.limit,
            "method_filter": method_filter,
            "has_more": has_more,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_json_path(self, req: DetectDuplicatesRequest) -> Path | None:
        """Determine which duplicates.json to load."""
        if req.json_path.strip():
            candidate = Path(req.json_path.strip()).expanduser().resolve()
            if candidate.exists():
                return candidate

        # Fall back to the root-scoped duplicates.json.
        duplicates_path: Path = self.ctx.duplicates_path
        if duplicates_path.exists():
            return duplicates_path

        return None
