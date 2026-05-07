# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from core.schemas import CopyTargetUpdateRequest, LanguageUpdateRequest, OpenPathRequest, RootAddRequest, RootUpdateRequest
from core.app.security import require_existing_directory, require_open_path_allowed, resolve_path


def create_settings_router(ctx: Any) -> APIRouter:
    router = APIRouter()

    # GET /api/config
    @router.get("/api/config")
    def get_config() -> dict[str, Any]:
        settings = ctx.load_settings()
        root = Path(settings["active_root"])
        duplicates = ctx.load_duplicates_summary()
        root_summary = ctx.get_root_summary(root)
        return {
            **ctx.serialize_settings(settings),
            "supported_extensions": sorted(ctx.SUPPORTED_EXTENSIONS),
            "duplicate_results": {
                "available": duplicates["available"],
                "group_count": duplicates["group_count"] if duplicates["available"] else (root_summary["duplicate_group_count"] or 0),
                "updated_at": root_summary["updated_at"],
            },
            "root_summary": root_summary,
            "active_root_exists": root.exists(),
            "system_recycle_supported": ctx.is_windows(),
        }

    # POST /api/open-path
    @router.post("/api/open-path")
    def open_path(payload: OpenPathRequest) -> dict[str, str]:
        settings = ctx.load_settings()
        target = resolve_path(payload.path)
        if not target.exists():
            raise HTTPException(status_code=404, detail="Path not found")

        require_open_path_allowed(target, ctx.get_safe_open_roots(settings))
        open_target = target if target.is_dir() else target.parent
        ctx.open_path_in_file_manager(open_target)
        return {"status": "opened", "path": str(open_target)}

    # POST /api/settings/language
    @router.post("/api/settings/language")
    def update_language(payload: LanguageUpdateRequest) -> dict[str, Any]:
        settings = ctx.load_settings()
        settings["language"] = ctx.validate_language(payload.language)
        ctx.save_settings(settings)
        return ctx.serialize_settings(settings)

    # POST /api/settings/copy-target
    @router.post("/api/settings/copy-target")
    def update_default_copy_target(payload: CopyTargetUpdateRequest) -> dict[str, Any]:
        settings = ctx.load_settings()
        settings["default_copy_target"] = payload.default_copy_target.strip()
        ctx.save_settings(settings)
        return ctx.serialize_settings(settings)

    # POST /api/settings/roots
    @router.post("/api/settings/roots")
    def add_image_root(payload: RootAddRequest) -> dict[str, Any]:
        candidate = require_existing_directory(resolve_path(payload.path), "Image root")
        settings = ctx.load_settings()
        candidate_str = str(candidate)
        if candidate_str not in settings["image_roots"]:
            settings["image_roots"].append(candidate_str)
        settings["active_root"] = candidate_str
        ctx.ensure_root_workspace(candidate_str)
        ctx.save_settings(settings)
        return ctx.serialize_settings(settings)

    # POST /api/settings/active-root
    @router.post("/api/settings/active-root")
    def set_active_root(payload: RootUpdateRequest) -> dict[str, Any]:
        candidate = str(Path(payload.path).expanduser().resolve())
        settings = ctx.load_settings()
        if candidate not in settings["image_roots"]:
            raise HTTPException(status_code=404, detail="Root not registered")
        settings["active_root"] = candidate
        ctx.ensure_root_workspace(candidate)
        ctx.save_settings(settings)
        return ctx.serialize_settings(settings)

    # POST /api/settings/remove-root
    @router.post("/api/settings/remove-root")
    def remove_root(payload: RootUpdateRequest) -> dict[str, Any]:
        candidate = str(Path(payload.path).expanduser().resolve())
        settings = ctx.load_settings()
        if candidate not in settings["image_roots"]:
            raise HTTPException(status_code=404, detail="Root not registered")
        if len(settings["image_roots"]) == 1:
            raise HTTPException(status_code=400, detail="At least one root must remain")
        settings["image_roots"] = [path for path in settings["image_roots"] if path != candidate]
        if settings["active_root"] == candidate:
            settings["active_root"] = settings["image_roots"][0]
        ctx.save_settings(settings)
        cleanup = ctx.cleanup_root_related_data(candidate) if payload.cleanup_root_data else None
        updated_settings = ctx.load_settings()
        return {**ctx.serialize_settings(updated_settings), "cleanup": cleanup}

    return router
