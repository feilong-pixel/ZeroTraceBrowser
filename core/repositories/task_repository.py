from pathlib import Path

class TaskRepository:
    def __init__(self, root_context):
        self.ctx = root_context

    def create_task_dir(self, task_id: str) -> Path:
        d = self.ctx.task_dir(task_id)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def write_log(self, task_id: str, text: str):
        path = self.ctx.organizer_log_file(task_id)
        path.write_text(text, encoding="utf-8")

    def write_report(self, task_id: str, csv_text: str):
        path = self.ctx.duplicate_report_file(task_id)
        path.write_text(csv_text, encoding="utf-8")
