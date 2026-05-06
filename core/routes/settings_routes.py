from fastapi import APIRouter
from pydantic import BaseModel

from core.use_cases.set_root import SetRootUseCase
from core.repositories.settings_repository import SettingsRepository


router = APIRouter()


# -----------------------------
# Request Models
# -----------------------------
class SetRootRequest(BaseModel):
    root_path: str


# -----------------------------
# Dependency wiring
# -----------------------------
def build_dependencies():
    settings_repo = SettingsRepository()
    set_root_uc = SetRootUseCase(settings_repo)
    return set_root_uc


set_root_uc = build_dependencies()


# -----------------------------
# Routes
# -----------------------------
@router.post("/api/set_root")
def set_root(req: SetRootRequest):
    return set_root_uc.execute(req)
