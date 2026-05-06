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
