import uuid

class CreateTaskUseCase:
    def __init__(self, task_repo):
        self.task_repo = task_repo

    def execute(self):
        task_id = uuid.uuid4().hex[:12]
        self.task_repo.create_task_dir(task_id)
        return {"status": "ok", "task_id": task_id}
