# SPDX-License-Identifier: MIT

from __future__ import annotations
from typing import Any

from pydantic import BaseModel, Field


class TimelineItem(BaseModel):
    """
    ZeroTraceBrowser 的时间线条目。

    对应 ``timeline_index_cache_path`` 所写 JSON 中 ``entries`` 数组的每一项。
    字段对齐 :func:`image_index_service.build_timeline_index_entries` 的返回结构。
    """

    # 分组 key（如 "2026-04"）
    key: str = Field(..., description="Timeline group key, e.g. '2026-04' or 'unknown'")

    # 分组展示标签（如 "2026-04" 或 "Unknown date"）
    label: str = Field(..., description="Display label for the timeline group")

    # 索引标签（用于导航刻度，如 "202604"）
    index_label: str = Field(..., description="Navigation tick label, e.g. '202604'")

    # --- helpers ---

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TimelineItem:
        """从 ``build_timeline_index_entries`` 的返回值安全构建。"""
        return cls(
            key=str(data.get("key", "")),
            label=str(data.get("label", "")),
            index_label=str(data.get("index_label", "")),
        )

