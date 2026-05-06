from fastapi import APIRouter
from pydantic import BaseModel

from core.use_cases.build_index import BuildIndexUseCase
from core.use_cases.build_timeline import BuildTimelineUseCase

from core.repositories.index_repository import IndexRepository
from core.repositories.timeline_repository import TimelineRepository
from core.repositories.file_repository import FileRepository

from core.infrastructure.imaging.metadata_reader import MetadataReader
from core.infrastructure.filesystem.file_transfer_adapter import FileTransferAdapter

from core.domain.root_context import RootContext
from core.domain.root_config import RootConfig


router = APIRouter()


# -----------------------------
# Request Models
# -----------------------------
class TimelineRequest(BaseModel):
    root_hash: str


# -----------------------------
# Dependency wiring
# -----------------------------
def build_dependencies():
    config = RootConfig.load_active()
    ctx = RootContext(config)

    transfer = FileTransferAdapter()
    file_repo = FileRepository(transfer, ctx)

    index_repo = IndexRepository(ctx)
    timeline_repo = TimelineRepository(ctx)

    metadata_reader = MetadataReader()

    build_index_uc = BuildIndexUseCase(
        file_repo=file_repo,
        index_repo=index_repo,
        metadata_reader=metadata_reader,
        root_context=ctx,
    )

    build_timeline_uc = BuildTimelineUseCase(
        index_repo=index_repo,
        timeline_repo=timeline_repo,
        root_context=ctx,
    )

    return build_index_uc, build_timeline_uc


build_index_uc, build_timeline_uc = build_dependencies()


# -----------------------------
# Routes
# -----------------------------
@router.post("/api/build_index")
def build_index():
    return build_index_uc.execute()


@router.post("/api/build_timeline")
def build_timeline(req: TimelineRequest):
    return build_timeline_uc.execute(req.root_hash)
