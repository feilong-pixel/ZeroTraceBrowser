import csv
from pathlib import Path


class LogRepository:
    """
    ZeroTraceBrowser 操作日志仓库。
    负责写入：
    - logs/delete_log.csv
    - logs/copy_log.csv
    """

# SPDX-License-Identifier: MIT

from __future__ import annotations

import csv
from pathlib import Path


class LogRepository:
    """
    ZeroTraceBrowser 操作日志仓库。
    负责写入：
    - logs/delete_log.csv
    - logs/copy_log.csv
    """

    def __init__(self, root_context):
        self.ctx = root_context

    # ---------------------------------------------------------
    # 内部辅助：确保 CSV header 存在
    # ---------------------------------------------------------

    @staticmethod
    def _ensure_header(log_path: Path, headers: list[str]) -> None:
        """如果文件不存在则写入 header 行。"""
        if log_path.exists():
            return
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(headers)

    # ---------------------------------------------------------
    # 删除日志
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
        追加一条删除（或 restore / purge）日志。

        Args:
            timestamp: ISO 格式时间戳。
            root: 图片根目录路径。
            relative_path: 文件相对于 root 的路径。
            deleted_to: 回收区中的目标路径。
            action: 操作类型，"deleted"、"restored" 或 "purged"。
        """
        log_path = self.ctx.delete_log_file()
        self._ensure_header(log_path, ["timestamp", "root", "relative_path", "deleted_to", "action"])

        with log_path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, root, relative_path, deleted_to, action])

    # ---------------------------------------------------------
    # 复制日志
    # ---------------------------------------------------------

    def append_copy_log(self, timestamp: str, root: str, src: str, dst: str) -> None:
        """
        追加一条复制日志。
        """
        log_path = self.ctx.copy_log_file()
        self._ensure_header(log_path, ["timestamp", "root", "relative_path", "copied_to"])

        with log_path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, root, src, dst])
        self.ctx = root_context

    # ---------------------------------------------------------
    # 删除日志
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
    # 复制日志
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
