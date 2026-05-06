from pydantic import BaseModel

class RestoreImageRequest(BaseModel):
    deleted_path: str

class RestoreImageUseCase:
    def __init__(self, file_repo, log_repo):
        self.file_repo = file_repo
        self.log = log_repo

    def execute(self, req):
        restored_path = self.file_repo.restore(req.deleted_path)
        self.log.record("restore", req.deleted_path, restored_path)
        return {"status": "ok", "restored": restored_path}
