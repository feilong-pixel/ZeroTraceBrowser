# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from core.services.recycle_service import archive_delete_log as archive_log_service


class ArchiveDeleteLogsRequest(BaseModel):
    """
    Request to archive the root-scoped delete log.
    """

    confirm: bool = Field(default=False)


class ArchiveDeleteLogsUseCase:
    """
    Archive the delete log by moving its contents to a timestamped
    backup file and starting a fresh (empty) log.
    """

    def __init__(self, logs_dir: Path) -> None:
        self.logs_dir = logs_dir

    def execute(self, req: ArchiveDeleteLogsRequest) -> dict[str, Any]:
        from fastapi import HTTPException

        if not req.confirm:
            raise HTTPException(status_code=400, detail="Confirmation required")

        result = archive_log_service(self.logs_dir)
        return {
            "status": "archived_logs",
            **result,
        }
