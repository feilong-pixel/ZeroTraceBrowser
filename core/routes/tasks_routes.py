from fastapi import APIRouter
from pydantic import BaseModel

from core.use_cases.create_task import CreateTaskUseCase
from core.use_cases.write_task_log import WriteTaskLogUseCase

from core.repositories.task_repository import TaskRepository
from core.domain.root_context import RootContext
from core.domain.root_config import RootConfig


router = APIRouter()


# -----------------------------
# Request Models
# -----------------------------
class WriteTaskLogRequest(BaseModel):
    task_id: str
    text: str


# -----------------------------
# Dependency wiring
# -----------------------------
def build_dependencies():
    config = RootConfig.load_active()
    ctx = RootContext(config)

    task_repo = TaskRepository(ctx)

    create_task_uc = CreateTaskUseCase(task_repo)
    write_log_uc = WriteTaskLogUseCase(task_repo)

    return create_task_uc, write_log_uc


create_task_uc, write_log_uc = build_dependencies()


# -----------------------------
# Routes
# -----------------------------
@router.post("/api/tasks/create")
def create_task():
    return create_task_uc.execute()


@router.post("/api/tasks/log")
def write_task_log(req: WriteTaskLogRequest):
    return write_log_uc.execute(req.task_id, req.text)
