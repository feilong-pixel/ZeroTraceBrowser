import csv
from pathlib import Path


class LogRepository:
    """
    Operation log repository for ZeroTraceBrowser.
    Responsible for writing:
    - logs/delete_log.csv
    - logs/copy_log.csv
    """

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

    # ---------------------------------------------------------
    # Internal helper: ensure CSV header exists
    # ---------------------------------------------------------

    @staticmethod
    def _ensure_header(log_path: Path, headers: list[str]) -> None:
        """Write the header row if the file does not exist."""
        if log_path.exists():
            return
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(headers)

    # ---------------------------------------------------------
    # Delete log
    # ---------------------------------------------------------

    def append_delete_log(
        self,
        timestamp: str,
        root: str,
        relative_path: str,
        deleted_to: str,
        action: str = "deleted",
    ) -> None:
        """
        Append a delete (or restore / purge) log entry.

        Args:
            timestamp: ISO-format timestamp.
            root: Image root directory path.
            relative_path: Path of the file relative to the root.
            deleted_to: Target path in the recycle area.
            action: Operation type: "deleted", "restored", or "purged".
        """
        log_path = self.ctx.delete_log_file()
        self._ensure_header(log_path, ["timestamp", "root", "relative_path", "deleted_to", "action"])

        with log_path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, root, relative_path, deleted_to, action])

    # ---------------------------------------------------------
    # Copy log
    # ---------------------------------------------------------

    def append_copy_log(self, timestamp: str, root: str, src: str, dst: str) -> None:
        """
        Append a copy operation log entry.
        """
        log_path = self.ctx.copy_log_file()
        self._ensure_header(log_path, ["timestamp", "root", "relative_path", "copied_to"])

        with log_path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, root, src, dst])
        self.ctx = root_context

    # ---------------------------------------------------------
    # Delete log
    # ---------------------------------------------------------
    def append_delete_log(self, timestamp: str, root: str, relative_path: str, deleted_to: str):
        log_path = self.ctx.delete_log_file()
        log_path.parent.mkdir(parents=True, exist_ok=True)

        with open(log_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp,
                root,
                relative_path,
                deleted_to,
                "deleted",
            ])

    # ---------------------------------------------------------
    # Copy log
    # ---------------------------------------------------------
    def append_copy_log(self, timestamp: str, root: str, src: str, dst: str):
        log_path = self.ctx.copy_log_file()
        log_path.parent.mkdir(parents=True, exist_ok=True)

        with open(log_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp,
                root,
                src,
                dst,
                "copied",
            ])
