from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from core.config import STATIC_DIR
from core.context import build_route_context
from core.lifespan import lifespan
from core.middleware import StaticNoCacheMiddleware
from core.security import cors_origins_from_env, trusted_hosts_from_env

from core.routes.duplicates import create_duplicates_router
from core.routes.images import create_images_router
from core.routes.recycle import create_recycle_router
from core.routes.settings import create_settings_router
from core.routes.tasks import create_tasks_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="ZeroTraceBrowser",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=trusted_hosts_from_env(),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins_from_env(),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(StaticNoCacheMiddleware)

    @app.get("/favicon.ico")
    async def favicon():
        return FileResponse("favicon.ico")

    ctx = build_route_context()

    app.include_router(create_settings_router(ctx))
    app.include_router(create_tasks_router(ctx))
    app.include_router(create_duplicates_router(ctx))
    app.include_router(create_recycle_router(ctx))
    app.include_router(create_images_router(ctx))

    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

    return app
