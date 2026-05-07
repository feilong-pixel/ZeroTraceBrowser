# SPDX-License-Identifier: MIT

from __future__ import annotations
from typing import Any

from pydantic import BaseModel, Field


class TimelineItem(BaseModel):
    """
    Timeline entry for ZeroTraceBrowser.

    Corresponds to each item in the ``entries`` array of the timeline index cache JSON.
    Fields align with the return structure of :func:`image_index_service.build_timeline_index_entries`.
    """

    # Group key, e.g. "2026-04"
    key: str = Field(..., description="Timeline group key, e.g. '2026-04' or 'unknown'")

    # Display label for the group, e.g. "2026-04" or "Unknown date"
    label: str = Field(..., description="Display label for the timeline group")

    # Navigation tick label, e.g. "202604"
    index_label: str = Field(..., description="Navigation tick label, e.g. '202604'")

    # --- helpers ---

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TimelineItem:
        """Safely build from the return value of ``build_timeline_index_entries``."""
        return cls(
            key=str(data.get("key", "")),
            label=str(data.get("label", "")),
            index_label=str(data.get("index_label", "")),
        )

