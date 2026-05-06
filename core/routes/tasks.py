# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import sys
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from core.schemas import OrganizerTaskRequest, RebuildHashDbTaskRequest
from core.security import require_existing_directory, require_not_same_or_child, resolve_path
from core.services.settings_service import normalize_task_lang


def create_tasks_router(ctx: Any) -> APIRouter:
    router = APIRouter()

    @router.post("/api/tasks/run-organizer")
    def run_organizer(payload: OrganizerTaskRequest) -> dict[str, Any]:
        if payload.mode not in {"copy", "move"}:
            raise HTTPException(status_code=400, detail="Unsupported organizer mode")
        if payload.duplicate_detection not in {"off", "phash", "strict"}:
            raise HTTPException(status_code=400, detail="Unsupported duplicate detection mode")
        if not ctx.ORGANIZER_MAIN.exists():
            raise HTTPException(status_code=404, detail="MediaArchiveOrganizer not found")

        lang = normalize_task_lang(payload.lang)
        src_path = require_existing_directory(resolve_path(payload.src), "Source")
        dst_path = resolve_path(payload.dst)
        task_id = uuid.uuid4().hex[:12]
        log_path = ctx.build_task_log_path(task_id, dst_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        outputs = ctx.build_task_outputs(log_path, dst_path, publish_duplicates=False)
        require_not_same_or_child(
            dst_path,
            src_path,
            "Destination directory must not be the source directory or one of its children",
        )
        ctx.remember_task_defaults(payload)
        ctx.clear_duplicates_path_cache()

        command = [
            sys.executable,
            "-u",
            str(ctx.ORGANIZER_MAIN),
            "--src",
            str(src_path),
            "--dst",
            str(dst_path),
            "--mode",
            payload.mode,
            "--duplicate-detection",
            payload.duplicate_detection,
            "--phash-threshold",
            str(payload.phash_threshold),
            "--lang",
            lang,
            "--log-path",
            str(log_path),
            "--duplicates-json-path",
            outputs["duplicates_json_path"],
        ]

        task_env = {"IMAGE_ORGANIZER_HASH_DB": outputs["hash_db_path"]}

        task = {
            "task_id": task_id,
            "task_type": "organizer",
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "params": payload.model_dump(),
            "outputs": outputs,
            "output_lines": [],
            "error": None,
            "return_code": None,
        }
        if not ctx.TASK_REGISTRY.add_if_idle(task):
            raise HTTPException(status_code=409, detail="Another organizer task is already running")

        thread = threading.Thread(
            target=ctx.run_organizer_task,
            args=(task_id, command, ctx.ORGANIZER_DIR, task_env),
            daemon=True,
        )
        thread.start()
        return ctx.serialize_task(task)

    @router.post("/api/tasks/rebuild-hash-db")
    def rebuild_hash_db_task(payload: RebuildHashDbTaskRequest) -> dict[str, Any]:
        if payload.rebuild_mode not in {"replace", "append"}:
            raise HTTPException(status_code=400, detail="Unsupported rebuild mode")
        if payload.hash_method not in {"strict", "phash", "both"}:
            raise HTTPException(status_code=400, detail="Unsupported hash method")
        if not ctx.ORGANIZER_MAIN.exists():
            raise HTTPException(status_code=404, detail="MediaArchiveOrganizer not found")

        root = str(require_existing_directory(resolve_path(payload.root), "Rebuild root"))
        lang = normalize_task_lang(payload.lang)
        task_id = uuid.uuid4().hex[:12]
        log_path = ctx.build_task_log_path(task_id, root)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        outputs = ctx.build_task_outputs(log_path, root, publish_duplicates=True)
        ctx.remember_rebuild_root(root)
        ctx.clear_duplicates_path_cache()

        command = [
            sys.executable,
            "-u",
            str(ctx.ORGANIZER_MAIN),
            "--rebuild-hash-db-root",
            root,
            "--rebuild-hash-db-mode",
            payload.rebuild_mode,
            "--rebuild-hash-method",
            payload.hash_method,
            "--phash-threshold",
            "4",
            "--duplicates-json-path",
            outputs["duplicates_json_path"],
            "--lang",
            lang,
        ]

        task_env = {"IMAGE_ORGANIZER_HASH_DB": outputs["hash_db_path"]}

        task = {
            "task_id": task_id,
            "task_type": "rebuild_hash_db",
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "params": payload.model_dump(),
            "outputs": outputs,
            "output_lines": [],
            "error": None,
            "return_code": None,
        }
        if not ctx.TASK_REGISTRY.add_if_idle(task):
            raise HTTPException(status_code=409, detail="Another organizer task is already running")

        thread = threading.Thread(
            target=ctx.run_organizer_task,
            args=(task_id, command, ctx.ORGANIZER_DIR, task_env),
            daemon=True,
        )
        thread.start()
        return ctx.serialize_task(task)

    @router.get("/api/tasks/running")
    def get_running_task() -> dict[str, Any]:
        task = ctx.get_running_task()
        return {"task": ctx.serialize_task(task) if task is not None else None}

    @router.get("/api/tasks/{task_id}")
    def get_task(task_id: str) -> dict[str, Any]:
        task = ctx.TASK_REGISTRY.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return ctx.serialize_task(task)

    @router.get("/api/tasks/{task_id}/duplicates")
    def get_task_duplicates(task_id: str) -> dict[str, Any]:
        task = ctx.TASK_REGISTRY.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")

        json_path = Path(task["outputs"]["duplicates_json_path"])
        if not json_path.exists():
            raise HTTPException(status_code=404, detail="duplicates.json not found")

        with json_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    return router
