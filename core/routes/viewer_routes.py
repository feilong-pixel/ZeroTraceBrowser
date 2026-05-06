from fastapi import APIRouter
from pydantic import BaseModel

from core.repositories.index_repository import IndexRepository
from core.repositories.timeline_repository import TimelineRepository

from core.domain.root_context import RootContext
from core.domain.root_config import RootConfig


router = APIRouter()


# -----------------------------
# Request Models
# -----------------------------
class RootHashRequest(BaseModel):
    root_hash: str


# -----------------------------
# Dependency wiring
# -----------------------------
def build_dependencies():
    config = RootConfig.load_active()
    ctx = RootContext(config)

    index_repo = IndexRepository(ctx)
    timeline_repo = TimelineRepository(ctx)

    return index_repo, timeline_repo


index_repo, timeline_repo = build_dependencies()


# -----------------------------
# Routes
# -----------------------------
@router.post("/api/viewer/index")
def get_index(req: RootHashRequest):
    entries = index_repo.load_index(req.root_hash)
    return {"status": "ok", "entries": [e.dict() for e in entries]}


@router.post("/api/viewer/timeline")
def get_timeline(req: RootHashRequest):
    items = timeline_repo.load_timeline(req.root_hash)
    return {"status": "ok", "timeline": [i.dict() for i in items]}
