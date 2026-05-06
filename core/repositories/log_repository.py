# SPDX-License-Identifier: MIT

from __future__ import annotations

import csv
from pathlib import Path


class LogRepository:
    """
    Operation log repository for ZeroTraceBrowser.
    Responsible for writing:
    - logs/delete_log.csv
    - logs/copy_log.csv
    """

    def __init__(self, root_context):
        self.ctx = root_context

    @staticmethod
    def _ensure_header(log_path: Path, headers: list[str]) -> None:
        if log_path.exists():
            return
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(headers)

    def append_delete_log(
        self,
        timestamp: str,
        root: str,
        relative_path: str,
        deleted_to: str,
        action: str = "deleted",
    ) -> None:
        log_path = self.ctx.delete_log_file()
        self._ensure_header(log_path, ["timestamp", "root", "relative_path", "deleted_to", "action"])
        with log_path.open("a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([timestamp, root, relative_path, deleted_to, action])

    def append_copy_log(self, timestamp: str, root: str, src: str, dst: str) -> None:
        log_path = self.ctx.copy_log_file()
        self._ensure_header(log_path, ["timestamp", "root", "relative_path", "copied_to"])
        with log_path.open("a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([timestamp, root, src, dst])
