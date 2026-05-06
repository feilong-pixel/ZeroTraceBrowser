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
        monkeypatch.setattr(ztb_app, "DEFAULT_IMAGE_ROOT", str(image_root))
        monkeypatch.setattr(core.config, "DEFAULT_IMAGE_ROOT", str(image_root))
        monkeypatch.setattr(core.context, "DEFAULT_IMAGE_ROOT", str(image_root))
        
        monkeypatch.setattr(ztb_app, "DEFAULT_COPY_TARGET", str(copy_target))
        monkeypatch.setattr(core.config, "DEFAULT_COPY_TARGET", str(copy_target))
        monkeypatch.setattr(core.context, "DEFAULT_COPY_TARGET", str(copy_target))
        
        monkeypatch.setattr(ztb_app, "DATA_DIR", workspace / "data")
        monkeypatch.setattr(core.config, "DATA_DIR", workspace / "data")
        monkeypatch.setattr(core.context, "DATA_DIR", workspace / "data")
        
        monkeypatch.setattr(ztb_app, "ROOT_DATA_DIR", workspace / "data" / "roots")
        monkeypatch.setattr(core.config, "ROOT_DATA_DIR", workspace / "data" / "roots")
        monkeypatch.setattr(core.context, "ROOT_DATA_DIR", workspace / "data" / "roots")
        
        monkeypatch.setattr(ztb_app, "SETTINGS_PATH", workspace / "settings.json")
        monkeypatch.setattr(core.config, "SETTINGS_PATH", workspace / "settings.json")
        monkeypatch.setattr(core.context, "SETTINGS_PATH", workspace / "settings.json")
        
        monkeypatch.setattr(ztb_app, "LOG_DIR", log_dir)
        monkeypatch.setattr(core.config, "LOG_DIR", log_dir)
        monkeypatch.setattr(core.context, "LOG_DIR", log_dir)
        
        monkeypatch.setattr(ztb_app, "TASK_LOG_DIR", log_dir / "tasks")
        monkeypatch.setattr(core.config, "TASK_LOG_DIR", log_dir / "tasks")
        monkeypatch.setattr(core.context, "TASK_LOG_DIR", log_dir / "tasks")
        
        monkeypatch.setattr(ztb_app, "DELETED_DIR", deleted_dir)
        monkeypatch.setattr(core.config, "DELETED_DIR", deleted_dir)
        monkeypatch.setattr(core.context, "DELETED_DIR", deleted_dir)
        
        monkeypatch.setattr(ztb_app, "THUMBNAIL_DIR", thumbnail_dir)
        monkeypatch.setattr(core.config, "THUMBNAIL_DIR", thumbnail_dir)
        monkeypatch.setattr(core.context, "THUMBNAIL_DIR", thumbnail_dir)

        monkeypatch.setattr(ztb_app, "IMAGE_INDEX_DIR", image_index_dir)
        monkeypatch.setattr(core.config, "IMAGE_INDEX_DIR", image_index_dir)
        monkeypatch.setattr(core.context, "IMAGE_INDEX_DIR", image_index_dir)

        monkeypatch.setattr(ztb_app, "ARTIFACT_INDEX_DIR", artifact_index_dir)
        monkeypatch.setattr(core.config, "ARTIFACT_INDEX_DIR", artifact_index_dir)
        monkeypatch.setattr(core.context, "ARTIFACT_INDEX_DIR", artifact_index_dir)
        
        ztb_app.TASK_REGISTRY.tasks.clear()

        with TestClient(ztb_app.app, base_url="http://localhost") as client:
            yield client, workspace, image_root, copy_target
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
