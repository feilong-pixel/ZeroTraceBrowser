# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from core.services.recycle_service import read_delete_log_rows, write_delete_log_rows


class ClearDeleteLogsRequest(BaseModel):
    """
    Request to remove log entries with specified actions from the
    root-scoped delete log.
    """

    confirm: bool = Field(default=False)
    actions: list[str] = Field(default_factory=lambda: ["restored", "purged"])


class ClearDeleteLogsUseCase:
    """
    Remove (clear) log rows whose action is in the requested action list.

    This is used by the frontend to clean up "restored" or "purged" entries
    so the log only shows actionable ("deleted") items.
    """

    def __init__(self, logs_dir: Path) -> None:
        self.logs_dir = logs_dir

    def execute(self, req: ClearDeleteLogsRequest) -> dict[str, Any]:
        from fastapi import HTTPException

        if not req.confirm:
            raise HTTPException(status_code=400, detail="Confirmation required")

        allowed_actions = {"restored", "purged"}
        actions = set(req.actions)
        if not actions or not actions.issubset(allowed_actions):
            raise HTTPException(status_code=400, detail="Unsupported log cleanup action")

        rows = read_delete_log_rows(self.logs_dir)
        remaining_rows = [row for row in rows if row.get("action") not in actions]
        removed_count = len(rows) - len(remaining_rows)
        write_delete_log_rows(self.logs_dir, remaining_rows)

        return {
            "status": "cleared_logs",
            "removed_count": removed_count,
            "actions": sorted(actions),
        }
