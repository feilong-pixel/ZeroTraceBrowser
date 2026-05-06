from fastapi import APIRouter
from pydantic import BaseModel

from core.use_cases.detect_duplicates import DetectDuplicatesUseCase
from core.use_cases.create_task import CreateTaskUseCase

from core.repositories.index_repository import IndexRepository
from core.repositories.duplicate_repository import DuplicateRepository
from core.repositories.task_repository import TaskRepository

from core.infrastructure.hashing.hash_calculator import HashCalculator
from core.domain.root_context import RootContext
from core.domain.root_config import RootConfig


router = APIRouter()


# -----------------------------
# Request Models
# -----------------------------
class DuplicateRequest(BaseModel):
    root_hash: str
    task_id: str


# -----------------------------
# Dependency wiring
# -----------------------------
def build_dependencies():
    config = RootConfig.load_active()
    ctx = RootContext(config)

    index_repo = IndexRepository(ctx)
    dup_repo = DuplicateRepository(ctx)
    task_repo = TaskRepository(ctx)

    hash_calc = HashCalculator()

    detect_uc = DetectDuplicatesUseCase(
        index_repo=index_repo,
        dup_repo=dup_repo,
        task_repo=task_repo,
        hash_calculator=hash_calc,
        root_context=ctx,
    )

    create_task_uc = CreateTaskUseCase(task_repo)

    return detect_uc, create_task_uc


detect_uc, create_task_uc = build_dependencies()


# -----------------------------
# Routes
# -----------------------------
@router.post("/api/create_task")
def create_task():
    return create_task_uc.execute()


@router.post("/api/detect_duplicates")
def detect_duplicates(req: DuplicateRequest):
    return detect_uc.execute(req.root_hash, req.task_id)
