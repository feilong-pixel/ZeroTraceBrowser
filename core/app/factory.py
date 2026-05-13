from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from core.config.app_config import *
from core.context import *
from core.context_modules.route_facade import build_route_context
from core.app.lifespan import lifespan
from core.app.middleware import StaticNoCacheMiddleware
from core.app.security import cors_origins_from_env, trusted_hosts_from_env

from core.routes.duplicates_route import create_duplicates_router
from core.routes.images_route import create_images_router
from core.routes.recycle_route import create_recycle_router
from core.routes.settings_route import create_settings_router
from core.routes.tasks_route import create_tasks_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="ZeroTraceBrowser",
        version="0.3.0",
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


app = create_app()
