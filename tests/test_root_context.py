# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import shutil
import uuid
from pathlib import Path

from core.domain.root_config import RootConfig
from core.domain.root_context import RootContext, normalize_root_path, root_id_for


def make_workspace() -> Path:
    workspace = Path.cwd() / "tests_runtime" / f"root_context_{uuid.uuid4().hex}"
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def test_root_context_uses_current_root_workspace_layout() -> None:
    workspace = make_workspace()
    image_root = workspace / "images"
    roots_dir = workspace / "data" / "roots"
    image_root.mkdir()

    try:
        ctx = RootContext.from_root(image_root, roots_dir)
        expected_root_id = hashlib.sha1(str(image_root.resolve()).encode("utf-8")).hexdigest()

        assert ctx.root == image_root.resolve()
        assert ctx.root_id == expected_root_id
        assert ctx.data_dir == roots_dir / expected_root_id
        assert ctx.root_json_path == ctx.data_dir / "root.json"
        assert ctx.hash_db_path == ctx.data_dir / "hash_db.json"
        assert ctx.duplicates_path == ctx.data_dir / "duplicates.json"
        assert ctx.deleted_dir == ctx.data_dir / "deleted"
        assert ctx.indexes_dir == ctx.data_dir / "indexes"
        assert ctx.logs_dir == ctx.data_dir / "logs"
        assert ctx.tasks_dir == ctx.data_dir / "tasks"
        assert ctx.thumbnails_dir == ctx.data_dir / "thumbnails"
        assert not ctx.data_dir.exists()
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_root_context_ensure_creates_runtime_directories() -> None:
    workspace = make_workspace()
    image_root = workspace / "images"
    roots_dir = workspace / "data" / "roots"
    image_root.mkdir()

    try:
        ctx = RootContext.from_root(image_root, roots_dir, ensure=True)

        assert ctx.data_dir.exists()
        assert ctx.deleted_dir.exists()
        assert ctx.indexes_dir.exists()
        assert ctx.logs_dir.exists()
        assert ctx.tasks_dir.exists()
        assert ctx.thumbnails_dir.exists()
        assert not (workspace / "data" / "root").exists()
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_root_context_keeps_config_constructor_compatible() -> None:
    workspace = make_workspace()
    image_root = workspace / "images"
    roots_dir = workspace / "data" / "roots"
    image_root.mkdir()

    try:
        config = RootConfig(root_id=root_id_for(image_root), root_path=str(image_root))
        ctx = RootContext(config, data_root=roots_dir, ensure=False)

        assert ctx.root == Path(normalize_root_path(image_root))
        assert ctx.data_dir == roots_dir / root_id_for(image_root)
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
