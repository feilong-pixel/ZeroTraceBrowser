# SPDX-License-Identifier: MIT

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app as ztb_app
import core.config
import core.context
from core.context_modules import (
    artifact_context,
    base,
    cleanup_context,
    duplicates_context,
    image_context,
    recycle_context,
    root_workspace,
    route_facade,
    settings_context,
    task_context,
)


PATCH_MODULES = (
    ztb_app,
    core.config,
    core.context,
    artifact_context,
    base,
    cleanup_context,
    duplicates_context,
    image_context,
    recycle_context,
    root_workspace,
    route_facade,
    settings_context,
    task_context,
)


def patch_runtime_value(monkeypatch: pytest.MonkeyPatch, name: str, value: object) -> None:
    for module in PATCH_MODULES:
        monkeypatch.setattr(module, name, value, raising=False)


@pytest.fixture()
def api_client(monkeypatch: pytest.MonkeyPatch):
    workspace = Path.cwd() / "tests_runtime" / f"api_{uuid.uuid4().hex}"
    image_root = workspace / "images"
    copy_target = workspace / "copies"
    log_dir = workspace / "logs"
    deleted_dir = workspace / "deleted"
    thumbnail_dir = workspace / "thumbnails"
    image_index_dir = thumbnail_dir / "_indexes"
    artifact_index_dir = workspace / "data" / "roots" / "_indexes"
    image_root.mkdir(parents=True)
    copy_target.mkdir(parents=True)
    deleted_dir.mkdir(parents=True)

    try:
        # Monkeypatch both app and core.config modules
        patch_runtime_value(monkeypatch, "DEFAULT_IMAGE_ROOT", str(image_root))
        
        patch_runtime_value(monkeypatch, "DEFAULT_COPY_TARGET", str(copy_target))
        
        patch_runtime_value(monkeypatch, "DATA_DIR", workspace / "data")
        
        patch_runtime_value(monkeypatch, "ROOT_DATA_DIR", workspace / "data" / "roots")
        
        patch_runtime_value(monkeypatch, "SETTINGS_PATH", workspace / "settings.json")
        
        patch_runtime_value(monkeypatch, "LOG_DIR", log_dir)
        
        patch_runtime_value(monkeypatch, "TASK_LOG_DIR", log_dir / "tasks")
        
        patch_runtime_value(monkeypatch, "DELETED_DIR", deleted_dir)
        
        patch_runtime_value(monkeypatch, "THUMBNAIL_DIR", thumbnail_dir)

        patch_runtime_value(monkeypatch, "IMAGE_INDEX_DIR", image_index_dir)

        patch_runtime_value(monkeypatch, "ARTIFACT_INDEX_DIR", artifact_index_dir)
        
        ztb_app.TASK_REGISTRY.tasks.clear()

        with TestClient(ztb_app.app, base_url="http://localhost") as client:
            yield client, workspace, image_root, copy_target
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
