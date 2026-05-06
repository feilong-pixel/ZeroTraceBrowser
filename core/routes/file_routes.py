from fastapi import APIRouter
from pydantic import BaseModel

# use_cases
from core.use_cases.delete_image import DeleteImageUseCase
from core.use_cases.restore_image import RestoreImageUseCase
from core.use_cases.copy_image import CopyImageUseCase

# repositories
from core.repositories.file_repository import FileRepository
from core.repositories.thumbnail_repository import ThumbnailRepository
from core.repositories.log_repository import LogRepository
from core.repositories.cache_repository import CacheRepository

# domain
from core.domain.root_context import RootContext
from core.domain.root_config import RootConfig

# infrastructure
from core.infrastructure.filesystem.file_transfer_adapter import FileTransferAdapter


router = APIRouter()


# -----------------------------
# Request Models
# -----------------------------
class FileActionRequest(BaseModel):
    relative_path: str


class CopyRequest(BaseModel):
    src: str
    dst: str


# -----------------------------
# Dependency wiring
# -----------------------------
def build_dependencies():
    # 1. 加载 root.json
    config = RootConfig.load_active()  # 你需要在 RootConfig 中实现 load_active()

    # 2. 构建 RootContext
    ctx = RootContext(config)

    # 3. 构建基础设施
    transfer = FileTransferAdapter()

    # 4. 构建 repositories
    file_repo = FileRepository(transfer, ctx)
    thumb_repo = ThumbnailRepository(ctx)
    log_repo = LogRepository(ctx)
    cache_repo = CacheRepository(ctx)

    # 5. 构建 use_cases
    delete_uc = DeleteImageUseCase(file_repo, thumb_repo, log_repo, cache_repo, ctx)
    restore_uc = RestoreImageUseCase(file_repo, thumb_repo, log_repo, cache_repo, ctx)
    copy_uc = CopyImageUseCase(file_repo, log_repo)

    return delete_uc, restore_uc, copy_uc


delete_uc, restore_uc, copy_uc = build_dependencies()


# -----------------------------
# Routes
# -----------------------------
@router.post("/api/delete")
def delete_image(req: FileActionRequest):
    return delete_uc.execute(req)


@router.post("/api/restore")
def restore_image(req: FileActionRequest):
    return restore_uc.execute(req)


@router.post("/api/copy")
def copy_image(req: CopyRequest):
    return copy_uc.execute(req)
