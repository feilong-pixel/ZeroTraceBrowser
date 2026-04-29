# SPDX-License-Identifier: MIT

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app as ztb_app


@pytest.fixture()
def api_client(monkeypatch: pytest.MonkeyPatch):
    workspace = Path.cwd() / "tests_runtime" / f"api_{uuid.uuid4().hex}"
    image_root = workspace / "images"
    copy_target = workspace / "copies"
    log_dir = workspace / "logs"
    deleted_dir = workspace / "deleted"
    thumbnail_dir = workspace / "thumbnails"
    image_root.mkdir(parents=True)
    copy_target.mkdir(parents=True)

    try:
        monkeypatch.setattr(ztb_app, "DEFAULT_IMAGE_ROOT", str(image_root))
        monkeypatch.setattr(ztb_app, "DEFAULT_COPY_TARGET", str(copy_target))
        monkeypatch.setattr(ztb_app, "DATA_DIR", workspace / "data")
        monkeypatch.setattr(ztb_app, "ROOT_DATA_DIR", workspace / "data" / "roots")
        monkeypatch.setattr(ztb_app, "SETTINGS_PATH", workspace / "settings.json")
        monkeypatch.setattr(ztb_app, "LOG_DIR", log_dir)
        monkeypatch.setattr(ztb_app, "TASK_LOG_DIR", log_dir / "tasks")
        monkeypatch.setattr(ztb_app, "DELETED_DIR", deleted_dir)
        monkeypatch.setattr(ztb_app, "THUMBNAIL_DIR", thumbnail_dir)
        ztb_app.TASK_REGISTRY.tasks.clear()

        with TestClient(ztb_app.app, base_url="http://localhost") as client:
            yield client, workspace, image_root, copy_target
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
