from fastapi import APIRouter
from pydantic import BaseModel
from pathlib import Path

from core.use_cases.restore_image import RestoreImageUseCase
from core.repositories.file_repository import FileRepository
from core.repositories.thumbnail_repository import ThumbnailRepository
from core.repositories.log_repository import LogRepository
from core.repositories.cache_repository import CacheRepository

from core.infrastructure.filesystem.file_transfer_adapter import FileTransferAdapter

from core.domain.root_context import RootContext
from core.domain.root_config import RootConfig


router = APIRouter()


# -----------------------------
# Request Models
# -----------------------------
class RestoreRequest(BaseModel):
    deleted_path: str


# -----------------------------
# Dependency wiring
# -----------------------------
def build_dependencies():
    config = RootConfig.load_active()
    ctx = RootContext(config)

    transfer = FileTransferAdapter()
    file_repo = FileRepository(transfer, ctx)
    thumb_repo = ThumbnailRepository(ctx)
    log_repo = LogRepository(ctx)
    cache_repo = CacheRepository(ctx)

    restore_uc = RestoreImageUseCase(file_repo, thumb_repo, log_repo, cache_repo, ctx)

    return restore_uc, ctx


restore_uc, ctx = build_dependencies()


# -----------------------------
# Routes
# -----------------------------
@router.get("/api/recycle/list")
def list_deleted():
    deleted_dir = ctx.deleted_dir
    items = []

    for p in deleted_dir.rglob("*"):
        if p.is_file():
            items.append(str(p))

    return {"status": "ok", "items": items}


@router.post("/api/recycle/restore")
def restore(req: RestoreRequest):
    return restore_uc.execute(req)
