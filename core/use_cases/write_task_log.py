class WriteTaskLogUseCase:
    def __init__(self, task_repo):
        self.task_repo = task_repo

    def execute(self, task_id: str, text: str):
        self.task_repo.write_log(task_id, text)
        return {"status": "ok"}
