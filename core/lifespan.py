from contextlib import asynccontextmanager
from fastapi import FastAPI

from core.config import STATIC_DIR, DATA_DIR, ROOT_DATA_DIR
from core.context import ensure_directories

try:
    from PIL import Image, ImageOps
except ImportError:
    Image = None
    ImageOps = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_directories()

    if Image is None or ImageOps is None:
        raise RuntimeError(
            "Pillow is required. Install dependencies with: pip install -r requirements.txt"
        )

    yield
