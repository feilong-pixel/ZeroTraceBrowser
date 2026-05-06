from pydantic import BaseModel

class CopyImageRequest(BaseModel):
    src: str
    dst: str

class CopyImageUseCase:
    def __init__(self, file_repo, log_repo):
        self.file_repo = file_repo
        self.log = log_repo

    def execute(self, req):
        new_path = self.file_repo.copy(req.src, req.dst)
        self.log.record("copy", req.src, new_path)
        return {"status": "ok", "copied": new_path}
