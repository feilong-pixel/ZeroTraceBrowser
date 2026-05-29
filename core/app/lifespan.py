from contextlib import asynccontextmanager
from fastapi import FastAPI

from core.config.app_config import STATIC_DIR, DATA_DIR, ROOT_DATA_DIR
from core.app.prewarm import start_startup_prewarm
from core.context_modules.root_workspace import ensure_directories

try:
    from PIL import Image, ImageOps
except ImportError:
    Image = None
    ImageOps = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_directories()

    if Image is None or ImageOps is None:
        raise RuntimeError(
            "Pillow is required. Install dependencies with: pip install -r requirements.txt"
        )

    route_context = getattr(app.state, "route_context", None)
    if route_context is not None:
        start_startup_prewarm(route_context)

    yield
