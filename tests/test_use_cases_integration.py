# SPDX-License-Identifier: MIT

"""
Integration tests for use cases using real RootContext + real filesystem.

These tests do NOT start FastAPI. They test the full orchestration flow:
  - Real ``RootContext`` (workspace layout created on disk)
  - Real file operations (``shutil.move`` / ``shutil.copy2`` patched in)
  - Real ``build_deleted_path``, ``thumbnail_path_for``, CSV log I/O

They verify that after executing a use case the filesystem and log files
are in the expected state.
"""

from __future__ import annotations

import csv
import shutil
import uuid
from pathlib import Path

import pytest

from core.domain.root_context import RootContext
from core.use_cases.copy_image import CopyImageRequest, CopyImageUseCase
from core.use_cases.delete_image import DeleteImageRequest, DeleteImageUseCase
from core.use_cases.restore_image import RestoreImageRequest, RestoreImageUseCase


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def workspace() -> Path:
    tmp = Path.cwd() / "tests_runtime" / f"use_case_int_{uuid.uuid4().hex}"
    tmp.mkdir(parents=True, exist_ok=True)
    try:
        yield tmp
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture()
def roots_dir(workspace: Path) -> Path:
    return workspace / "data" / "roots"


@pytest.fixture()
def image_root(workspace: Path) -> Path:
    root = workspace / "photos"
    root.mkdir()
    return root


@pytest.fixture()
def ctx(roots_dir: Path, image_root: Path) -> RootContext:
    """Real RootContext with runtime directories created."""
    return RootContext.from_root(image_root, roots_dir, ensure=True)


def _touch(path: Path, content: str = "integration-test-data") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ===================================================================
# DeleteImageUseCase integration
# ===================================================================


class TestDeleteImageUseCaseIntegration:
    """Verify the full delete flow against a real filesystem."""

    @pytest.fixture(autouse=True)
    def _patch_move(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Patch move_file_preserve_times with shutil.move."""
        import core.use_cases.delete_image as delete_mod

        def fake_move(src, dst):
            dst.parent.mkdir(parents=True, exist_ok=True)
            # On same filesystem rename is atomic, which simulates the real
            # move_file_preserve_times behaviour.
            if src.exists():
                shutil.move(str(src), str(dst))

        monkeypatch.setattr(delete_mod, "move_file_preserve_times", fake_move)

    @pytest.fixture()
    def use_case(self, ctx: RootContext) -> DeleteImageUseCase:
        return DeleteImageUseCase(
            root_context=ctx,
            thumbnails_dir=ctx.thumbnails_dir,
            thumbnail_size=(256, 256),
        )

    def test_happy_path(self, ctx: RootContext, use_case: DeleteImageUseCase):
        """File is moved under deleted/ with timestamp prefix, log is written."""
        src = _touch(ctx.root / "sub" / "img.jpg")

        result = use_case.execute(DeleteImageRequest(relative_path="sub/img.jpg"))

        assert result["status"] == "deleted"
        deleted_to = Path(result["deleted_to"])
        # Must be under deleted_dir.
        assert deleted_to.is_relative_to(ctx.deleted_dir)
        # Must have a timestamp prefix directory.
        assert len(deleted_to.relative_to(ctx.deleted_dir).parts) >= 2
        # Original file is gone.
        assert not src.exists()
        # File content is preserved.
        assert deleted_to.read_text(encoding="utf-8") == "integration-test-data"

        # Log written.
        rows = _read_csv(ctx.logs_dir / "delete_log.csv")
        assert len(rows) >= 1
        assert rows[-1]["action"] == "deleted"
        assert rows[-1]["relative_path"] == "sub/img.jpg"
        assert rows[-1]["root"] == str(ctx.root)

    def test_missing_file_returns_missing_and_no_file_moved(self, ctx: RootContext, use_case: DeleteImageUseCase):
        """Deleting a non-existent file returns 'missing' and does not create a deleted file."""
        result = use_case.execute(DeleteImageRequest(relative_path="nonexistent.png"))

        assert result == {"status": "missing", "relative_path": "nonexistent.png"}
        # No new files in deleted_dir.
        assert not any(ctx.deleted_dir.iterdir())


# ===================================================================
# CopyImageUseCase integration
# ===================================================================


class TestCopyImageUseCaseIntegration:
    """Verify the full copy flow against a real filesystem."""

    @pytest.fixture(autouse=True)
    def _patch_copy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Patch copy_file_preserve_times with shutil.copy2."""
        import core.use_cases.copy_image as copy_mod

        def fake_copy(src, dst):
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dst))

        monkeypatch.setattr(copy_mod, "copy_file_preserve_times", fake_copy)

    @pytest.fixture()
    def use_case(self, ctx: RootContext, workspace: Path) -> CopyImageUseCase:
        default_target = workspace / "default_copies"
        return CopyImageUseCase(root_context=ctx, default_copy_target=str(default_target))

    def test_happy_path(self, ctx: RootContext, use_case: CopyImageUseCase, workspace: Path):
        """File is copied to target, original untouched, log written."""
        _touch(ctx.root / "photo.jpg")

        target = workspace / "my_copies"
        result = use_case.execute(CopyImageRequest(relative_path="photo.jpg", target_dir=str(target)))

        assert result["status"] == "copied"
        copied_to = Path(result["copied_to"])
        assert copied_to.parent == target.resolve()
        assert copied_to.read_text(encoding="utf-8") == "integration-test-data"
        # Original must still exist.
        assert (ctx.root / "photo.jpg").exists()

        # Log written.
        rows = _read_csv(ctx.logs_dir / "copy_log.csv")
        assert len(rows) == 1
        assert rows[0]["relative_path"] == "photo.jpg"
        assert rows[0]["root"] == str(ctx.root)

    def test_name_collision_produces_unique_filename(
        self, ctx: RootContext, use_case: CopyImageUseCase, workspace: Path
    ):
        """When the target file already exists, the copy appends _1, _2, etc."""
        _touch(ctx.root / "photo.jpg")
        target = workspace / "my_copies"
        target.mkdir(parents=True, exist_ok=True)
        _touch(target / "photo.jpg")
        _touch(target / "photo_1.jpg")

        result = use_case.execute(CopyImageRequest(relative_path="photo.jpg", target_dir=str(target)))

        copied_to = Path(result["copied_to"])
        assert copied_to.name == "photo_2.jpg"

    def test_uses_default_target_when_not_specified(
        self, ctx: RootContext, use_case: CopyImageUseCase, workspace: Path
    ):
        """When target_dir is empty, the default from __init__ is used."""
        _touch(ctx.root / "img.png")
        result = use_case.execute(CopyImageRequest(relative_path="img.png", target_dir=""))

        assert result["status"] == "copied"
        copied_to = Path(result["copied_to"])
        assert copied_to.is_relative_to(workspace / "default_copies")


# ===================================================================
# RestoreImageUseCase integration
# ===================================================================


class TestRestoreImageUseCaseIntegration:
    """Verify the full restore flow against a real filesystem."""

    @pytest.fixture(autouse=True)
    def _patch_move(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Patch move_file_preserve_times with shutil.move."""
        import core.use_cases.restore_image as restore_mod

        def fake_move(src, dst):
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.exists():
                shutil.move(str(src), str(dst))

        monkeypatch.setattr(restore_mod, "move_file_preserve_times", fake_move)

    @pytest.fixture()
    def use_case(self, ctx: RootContext) -> RestoreImageUseCase:
        return RestoreImageUseCase(
            root_context=ctx,
            thumbnails_dir=ctx.thumbnails_dir,
        )

    def _prepare_deleted(self, ctx: RootContext, rel: str = "album/photo.jpg") -> Path:
        """Create a deleted file and seed the log. Returns the deleted path."""
        # Use the real build_deleted_path to get the timestamped path.
        from core.services.recycle_paths import build_deleted_path

        deleted_path = build_deleted_path(ctx.deleted_dir, ctx.root, rel)
        _touch(deleted_path, "restore-me")

        log_path = ctx.logs_dir / "delete_log.csv"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["timestamp", "root", "relative_path", "deleted_to", "action"])
            w.writerow(["2026-04-26T12:00:00", str(ctx.root), rel, str(deleted_path), "deleted"])
        return deleted_path

    def test_happy_path(self, ctx: RootContext, use_case: RestoreImageUseCase):
        """File is moved back to original location, log updated, deleted dir cleaned."""
        deleted_path = self._prepare_deleted(ctx)

        result = use_case.execute(RestoreImageRequest(deleted_to=str(deleted_path)))

        assert result["status"] == "restored"
        restored_to = Path(result["restored_to"])
        assert restored_to == (ctx.root / "album" / "photo.jpg").resolve()
        assert restored_to.read_text(encoding="utf-8") == "restore-me"
        # Deleted file is gone.
        assert not deleted_path.exists()

        # Log contains both the original 'deleted' row and the new 'restored' row.
        rows = _read_csv(ctx.logs_dir / "delete_log.csv")
        assert len(rows) == 2
        assert rows[-1]["action"] == "restored"
        assert rows[-1]["relative_path"] == "album/photo.jpg"

    def test_restore_creates_parent_directory_if_needed(self, ctx: RootContext, use_case: RestoreImageUseCase):
        """If the original parent directory is missing, it should be created."""
        deleted_path = self._prepare_deleted(ctx)

        use_case.execute(RestoreImageRequest(deleted_to=str(deleted_path)))

        restored_to = ctx.root / "album" / "photo.jpg"
        assert restored_to.exists()
        # Parent directory should exist.
        assert restored_to.parent.exists()

    def test_restore_fails_when_original_exists(self, ctx: RootContext, use_case: RestoreImageUseCase):
        """If the original file already exists, restore raises 409."""
        deleted_path = self._prepare_deleted(ctx, "existing.jpg")
        _touch(ctx.root / "existing.jpg", "original-content")

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            use_case.execute(RestoreImageRequest(deleted_to=str(deleted_path)))
        assert exc.value.status_code == 409
        assert "Original path already exists" in exc.value.detail
