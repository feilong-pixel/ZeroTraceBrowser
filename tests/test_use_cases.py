# SPDX-License-Identifier: MIT

from __future__ import annotations

import csv
import hashlib
import shutil
import uuid
from datetime import datetime
from pathlib import Path

import pytest
from fastapi import HTTPException

from core.use_cases.copy_image import CopyImageRequest, CopyImageUseCase
from core.use_cases.delete_image import DeleteImageRequest, DeleteImageUseCase
from core.use_cases.restore_image import RestoreImageRequest, RestoreImageUseCase
from core.use_cases.purge_image import PurgeImageRequest, PurgeImageUseCase
from core.use_cases.clear_recycle import ClearRecycleRequest, ClearRecycleUseCase


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def workspace() -> Path:
    """Yield a temporary directory and clean it up afterwards."""
    tmp = Path.cwd() / "tests_runtime" / f"use_cases_{uuid.uuid4().hex}"
    tmp.mkdir(parents=True, exist_ok=True)
    try:
        yield tmp
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


class FakeRootContext:
    """Minimal stand-in for RootContext – just enough to satisfy the use cases."""

    def __init__(self, root: Path, deleted_dir: Path, logs_dir: Path, thumbnails_dir: Path):
        self.root = root
        self.deleted_dir = deleted_dir
        self.logs_dir = logs_dir
        self.thumbnails_dir = thumbnails_dir


def touch(path: Path, content: str = "dummy-image-content") -> Path:
    """Create a file at *path* (including parent directories) and return it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def read_csv(path: Path) -> list[dict[str, str]]:
    """Return all rows from a CSV file as a list of dicts."""
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ===================================================================
# DeleteImageUseCase
# ===================================================================


class TestDeleteImageUseCase:
    """Tests for DeleteImageUseCase.

    Strategy: use real filesystem operations but mock the expensive/
    side-effect-heavy service functions (move_file_preserve_times,
    copy_file_preserve_times, clear_image_list_cache).
    """

    @pytest.fixture(autouse=True)
    def _inject_mocks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.moved: list[tuple[Path, Path]] = []
        self.cache_cleared: list[Path] = []

        def fake_move(src, dst):
            self.moved.append((Path(src), Path(dst)))
            # Simulate what a real move does (source disappears).
            if Path(src).exists():
                Path(src).rename(dst)

        def fake_clear_cache(root=None):
            self.cache_cleared.append(Path(root) if root else None)

        monkeypatch.setattr(
            "core.use_cases.delete_image.move_file_preserve_times", fake_move
        )
        monkeypatch.setattr(
            "core.use_cases.delete_image.clear_image_list_cache", fake_clear_cache
        )

    @pytest.fixture()
    def ctx(self, workspace: Path) -> FakeRootContext:
        root = workspace / "photos"
        root.mkdir()
        deleted_dir = workspace / "data" / "roots" / "test_root" / "deleted"
        logs_dir = workspace / "data" / "roots" / "test_root" / "logs"
        thumbnails_dir = workspace / "data" / "roots" / "test_root" / "thumbnails"
        return FakeRootContext(root, deleted_dir, logs_dir, thumbnails_dir)

    @pytest.fixture()
    def use_case(self, ctx: FakeRootContext) -> DeleteImageUseCase:
        return DeleteImageUseCase(
            root_context=ctx,
            thumbnails_dir=ctx.thumbnails_dir,
            thumbnail_size=(512, 512),
        )

    # ---------------------------------------------------------------
    # Happy path: existing file
    # ---------------------------------------------------------------

    def test_delete_existing_file_moves_to_recycle(self, ctx, use_case):
        """An existing file should be moved under deleted/ and logged."""
        src = touch(ctx.root / "subdir" / "photo.jpg")
        req = DeleteImageRequest(relative_path="subdir/photo.jpg")

        result = use_case.execute(req)

        assert result["status"] == "deleted"
        deleted_to = Path(result["deleted_to"])
        # The deleted path should live under ctx.deleted_dir.
        assert deleted_to.is_relative_to(ctx.deleted_dir)
        # The file content should have been moved.
        assert deleted_to.read_text(encoding="utf-8") == "dummy-image-content"
        assert not src.exists()

        # move_file_preserve_times should have been called once.
        assert len(self.moved) == 1
        moved_src, moved_dst = self.moved[0]
        assert moved_src == src
        assert moved_dst == deleted_to

        # clear_image_list_cache should have been called.
        assert ctx.root in self.cache_cleared

    def test_delete_log_is_written(self, ctx, use_case):
        """After a successful delete a row should exist in delete_log.csv."""
        touch(ctx.root / "photo.jpg")
        req = DeleteImageRequest(relative_path="photo.jpg")

        use_case.execute(req)

        rows = read_csv(ctx.logs_dir / "delete_log.csv")
        assert len(rows) == 1
        row = rows[0]
        assert row["action"] == "deleted"
        assert row["relative_path"] == "photo.jpg"
        assert row["root"] == str(ctx.root)
        assert "deleted_to" in row

    def test_delete_file_thumbnail_is_cleaned_up(self, ctx, use_case):
        """A stale thumbnail should be removed after delete."""
        touch(ctx.root / "photo.jpg")

        # Create a stale thumbnail at the expected path.
        digest = hashlib.sha1(f"{ctx.root}|photo.jpg".encode("utf-8")).hexdigest()
        thumb = ctx.thumbnails_dir / digest[:2] / digest[2:4] / f"{digest}.jpg"
        touch(thumb, "stale-thumb")
        assert thumb.exists()

        req = DeleteImageRequest(relative_path="photo.jpg")
        use_case.execute(req)

        assert not thumb.exists()

    # ---------------------------------------------------------------
    # Missing file
    # ---------------------------------------------------------------

    def test_delete_missing_file_returns_missing_status(self, ctx, use_case):
        """Deleting a file that does not exist returns status 'missing'."""
        req = DeleteImageRequest(relative_path="nonexistent.jpg")

        result = use_case.execute(req)

        assert result == {"status": "missing", "relative_path": "nonexistent.jpg"}
        # No file should have been moved.
        assert len(self.moved) == 0
        # Cache should still be cleared.
        assert ctx.root in self.cache_cleared

    def test_delete_missing_file_cleans_up_stale_thumbnail(self, ctx, use_case):
        """Even when the source is gone, a stale thumbnail should be removed."""
        digest = hashlib.sha1(f"{ctx.root}|gone.jpg".encode("utf-8")).hexdigest()
        thumb = ctx.thumbnails_dir / digest[:2] / digest[2:4] / f"{digest}.jpg"
        touch(thumb, "stale")
        assert thumb.exists()

        req = DeleteImageRequest(relative_path="gone.jpg")
        result = use_case.execute(req)

        assert result["status"] == "missing"
        assert not thumb.exists()

    # ---------------------------------------------------------------
    # Path traversal
    # ---------------------------------------------------------------

    def test_delete_rejects_path_traversal(self, ctx, use_case):
        """A relative_path with '..' should raise 400."""
        req = DeleteImageRequest(relative_path="../outside.txt")

        with pytest.raises(HTTPException) as exc:
            use_case.execute(req)
        assert exc.value.status_code == 400
        assert "Path escapes configured root" in exc.value.detail

    # ---------------------------------------------------------------
    # Edge cases
    # ---------------------------------------------------------------

    def test_delete_empty_relative_path_is_rejected(self):
        """relative_path must have at least 1 character (Pydantic validation)."""
        with pytest.raises(Exception):  # noqa: B017 – Pydantic validation error
            DeleteImageRequest(relative_path="")


# ===================================================================
# CopyImageUseCase
# ===================================================================


class TestCopyImageUseCase:
    @pytest.fixture(autouse=True)
    def _inject_mocks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.copied: list[tuple[Path, Path]] = []
        self.cache_cleared: list[Path] = []

        def fake_copy(src, dst):
            self.copied.append((Path(src), Path(dst)))
            # Simulate what a real copy does.
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

        def fake_clear_cache(root=None):
            self.cache_cleared.append(Path(root) if root else None)

        monkeypatch.setattr(
            "core.use_cases.copy_image.copy_file_preserve_times", fake_copy
        )
        monkeypatch.setattr(
            "core.use_cases.copy_image.clear_image_list_cache", fake_clear_cache
        )

    @pytest.fixture()
    def ctx(self, workspace: Path) -> FakeRootContext:
        root = workspace / "photos"
        root.mkdir()
        logs_dir = workspace / "data" / "roots" / "test_root" / "logs"
        return FakeRootContext(root, deleted_dir=workspace / "deleted", logs_dir=logs_dir, thumbnails_dir=workspace / "thumbnails")

    @pytest.fixture()
    def use_case(self, ctx: FakeRootContext) -> CopyImageUseCase:
        return CopyImageUseCase(root_context=ctx, default_copy_target="")

    # ---------------------------------------------------------------
    # Happy path
    # ---------------------------------------------------------------

    def test_copy_existing_file_to_target(self, ctx, use_case, workspace: Path):
        """Copying an existing file should place a copy in the target dir."""
        touch(ctx.root / "photo.jpg")
        target = workspace / "copies"

        req = CopyImageRequest(relative_path="photo.jpg", target_dir=str(target))
        result = use_case.execute(req)

        assert result["status"] == "copied"
        copied_to = Path(result["copied_to"])
        assert copied_to.parent == target.resolve()
        assert copied_to.read_text(encoding="utf-8") == "dummy-image-content"
        # Original must still exist.
        assert (ctx.root / "photo.jpg").exists()

    def test_copy_uses_default_target_when_not_specified(self, ctx, workspace: Path):
        """When target_dir is empty, the default_copy_target from __init__ should be used."""
        touch(ctx.root / "img.png")
        default_target = workspace / "default_copies"

        uc = CopyImageUseCase(root_context=ctx, default_copy_target=str(default_target))
        req = CopyImageRequest(relative_path="img.png", target_dir="")

        result = uc.execute(req)

        assert result["status"] == "copied"
        assert Path(result["copied_to"]).is_relative_to(default_target.resolve())

    def test_copy_raises_when_no_target_configured(self, ctx, use_case):
        """Missing target_dir and empty default should raise 400."""
        touch(ctx.root / "img.png")
        req = CopyImageRequest(relative_path="img.png", target_dir="")

        with pytest.raises(HTTPException) as exc:
            use_case.execute(req)
        assert exc.value.status_code == 400
        assert "No copy target configured" in exc.value.detail

    def test_copy_raises_when_source_missing(self, ctx, use_case, workspace: Path):
        """Copying a non-existent file should raise 404."""
        target = workspace / "copies"
        req = CopyImageRequest(relative_path="missing.jpg", target_dir=str(target))

        with pytest.raises(HTTPException) as exc:
            use_case.execute(req)
        assert exc.value.status_code == 404
        assert "Image not found" in exc.value.detail

    # ---------------------------------------------------------------
    # Name collision
    # ---------------------------------------------------------------

    def test_copy_auto_renames_when_target_exists(self, ctx, use_case, workspace: Path):
        """If the target file already exists, the copy should append _1, _2, ..."""
        touch(ctx.root / "photo.jpg")
        target = workspace / "copies"
        target.mkdir(parents=True, exist_ok=True)
        # Pre-create the first two collision targets.
        touch(target / "photo.jpg")
        touch(target / "photo_1.jpg")

        req = CopyImageRequest(relative_path="photo.jpg", target_dir=str(target))
        result = use_case.execute(req)

        copied_to = Path(result["copied_to"])
        assert copied_to.name == "photo_2.jpg"

    # ---------------------------------------------------------------
    # Path traversal
    # ---------------------------------------------------------------

    def test_copy_rejects_path_traversal(self, ctx, use_case, workspace: Path):
        """A relative_path with '..' should raise 400."""
        req = CopyImageRequest(relative_path="../outside.txt", target_dir=str(workspace))

        with pytest.raises(HTTPException) as exc:
            use_case.execute(req)
        assert exc.value.status_code == 400
        assert "Path escapes configured root" in exc.value.detail

    # ---------------------------------------------------------------
    # Logging
    # ---------------------------------------------------------------

    def test_copy_log_is_written(self, ctx, use_case, workspace: Path):
        """A successful copy should write a row to copy_log.csv."""
        touch(ctx.root / "photo.jpg")
        target = workspace / "copies"

        req = CopyImageRequest(relative_path="photo.jpg", target_dir=str(target))
        use_case.execute(req)

        rows = read_csv(ctx.logs_dir / "copy_log.csv")
        assert len(rows) == 1
        row = rows[0]
        assert row["relative_path"] == "photo.jpg"
        assert row["root"] == str(ctx.root)
        assert "copied_to" in row


# ===================================================================
# RestoreImageUseCase
# ===================================================================


class TestRestoreImageUseCase:
    @pytest.fixture(autouse=True)
    def _inject_mocks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.moved: list[tuple[Path, Path]] = []
        self.cache_cleared: list[Path] = []

        def fake_move(src, dst):
            self.moved.append((Path(src), Path(dst)))
            if Path(src).exists():
                Path(src).rename(dst)

        def fake_clear_cache(root=None):
            self.cache_cleared.append(Path(root) if root else None)

        monkeypatch.setattr(
            "core.use_cases.restore_image.move_file_preserve_times", fake_move
        )
        monkeypatch.setattr(
            "core.use_cases.restore_image.clear_image_list_cache", fake_clear_cache
        )

    @pytest.fixture()
    def ctx(self, workspace: Path) -> FakeRootContext:
        root = workspace / "photos"
        root.mkdir()
        deleted_dir = workspace / "data" / "roots" / "test_root" / "deleted"
        logs_dir = workspace / "data" / "roots" / "test_root" / "logs"
        thumbnails_dir = workspace / "data" / "roots" / "test_root" / "thumbnails"
        return FakeRootContext(root, deleted_dir, logs_dir, thumbnails_dir)

    @pytest.fixture()
    def use_case(self, ctx: FakeRootContext) -> RestoreImageUseCase:
        return RestoreImageUseCase(root_context=ctx, thumbnails_dir=ctx.thumbnails_dir)

    # ---------------------------------------------------------------
    # Helper: create a deleted file and seed the log
    # ---------------------------------------------------------------

    def _prepare_deleted(self, ctx: FakeRootContext, rel: str = "photo.jpg") -> Path:
        """Create a deleted file and write a matching log row. Returns the deleted path."""
        deleted_path = ctx.deleted_dir / "20260426_a1b2c3d4e5" / Path(rel).name
        touch(deleted_path, "restore-me")
        log_path = ctx.logs_dir / "delete_log.csv"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["timestamp", "root", "relative_path", "deleted_to", "action"])
            w.writerow(["2026-04-26T12:00:00", str(ctx.root), rel, str(deleted_path), "deleted"])
        return deleted_path

    # ---------------------------------------------------------------
    # Happy path
    # ---------------------------------------------------------------

    def test_restore_moves_file_back(self, ctx, use_case):
        """A deleted file should be moved back to its original location."""
        deleted_path = self._prepare_deleted(ctx)

        req = RestoreImageRequest(deleted_to=str(deleted_path))
        result = use_case.execute(req)

        assert result["status"] == "restored"
        restored_to = Path(result["restored_to"])
        assert restored_to == (ctx.root / "photo.jpg").resolve()
        assert restored_to.read_text(encoding="utf-8") == "restore-me"
        assert not deleted_path.exists()

    def test_restore_log_is_written(self, ctx, use_case):
        """After a successful restore a 'restored' row should appear in the log."""
        deleted_path = self._prepare_deleted(ctx)
        req = RestoreImageRequest(deleted_to=str(deleted_path))

        use_case.execute(req)

        rows = read_csv(ctx.logs_dir / "delete_log.csv")
        # The original "deleted" row plus the new "restored" row.
        assert len(rows) == 2
        assert rows[1]["action"] == "restored"
        assert rows[1]["relative_path"] == "photo.jpg"

    def test_restore_clears_stale_deleted_thumbnail(self, ctx, use_case):
        """The thumbnail for the deleted file should be removed after restore."""
        deleted_path = self._prepare_deleted(ctx)
        # Create a stale thumbnail for the original file.
        digest = hashlib.sha1(f"{ctx.root}|photo.jpg".encode("utf-8")).hexdigest()
        thumb = ctx.thumbnails_dir / digest[:2] / digest[2:4] / f"{digest}.jpg"
        touch(thumb, "stale")
        assert thumb.exists()

        req = RestoreImageRequest(deleted_to=str(deleted_path))
        use_case.execute(req)

        assert not thumb.exists()

    # ---------------------------------------------------------------
    # Validation errors
    # ---------------------------------------------------------------

    def test_restore_rejects_path_outside_deleted_dir(self, ctx, use_case):
        """A path that is not under deleted_dir should raise 400."""
        outside = ctx.root / "not_deleted.txt"
        req = RestoreImageRequest(deleted_to=str(outside))

        with pytest.raises(HTTPException) as exc:
            use_case.execute(req)
        assert exc.value.status_code == 400
        assert "Invalid deleted file path" in exc.value.detail

    def test_restore_raises_when_deleted_file_missing(self, ctx, use_case):
        """A non-existent deleted path should raise 404."""
        fake_deleted = ctx.deleted_dir / "20260426_a1b2c3d4e5" / "photo.jpg"
        req = RestoreImageRequest(deleted_to=str(fake_deleted))

        with pytest.raises(HTTPException) as exc:
            use_case.execute(req)
        assert exc.value.status_code == 404
        assert "Deleted file not found" in exc.value.detail

    def test_restore_raises_when_log_entry_missing(self, ctx, use_case):
        """A deleted file with no log entry should raise 400."""
        deleted_path = ctx.deleted_dir / "20260426_x1y2z3" / "orphan.jpg"
        touch(deleted_path)
        req = RestoreImageRequest(deleted_to=str(deleted_path))

        with pytest.raises(HTTPException) as exc:
            use_case.execute(req)
        assert exc.value.status_code == 400
        assert "No restore target found in delete log" in exc.value.detail

    def test_restore_raises_when_original_path_already_exists(self, ctx, use_case):
        """If the original file already exists, restore should raise 409."""
        deleted_path = self._prepare_deleted(ctx, "existing.jpg")
        touch(ctx.root / "existing.jpg", "original-data")
        req = RestoreImageRequest(deleted_to=str(deleted_path))

        with pytest.raises(HTTPException) as exc:
            use_case.execute(req)
        assert exc.value.status_code == 409
        assert "Original path already exists" in exc.value.detail

    # ---------------------------------------------------------------
    # Cache clearing
    # ---------------------------------------------------------------

    def test_restore_clears_cache_for_original_root(self, ctx, use_case):
        """clear_image_list_cache should be called with the original root."""
        deleted_path = self._prepare_deleted(ctx)
        req = RestoreImageRequest(deleted_to=str(deleted_path))

        use_case.execute(req)

        assert ctx.root.resolve() in {p.resolve() for p in self.cache_cleared}


# ===================================================================
# PurgeImageUseCase
# ===================================================================


class TestPurgeImageUseCase:
    """Tests for PurgeImageUseCase.

    Injects a fake ``dispose_fn`` that records what is disposed and
    deletes the file permanently (simulating the non-Windows path).
    """

    @pytest.fixture(autouse=True)
    def _inject_mocks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.disposed: list[Path] = []

        def fake_move(src, dst):
            if Path(src).exists():
                Path(src).rename(dst)

        monkeypatch.setattr(
            "core.services.file_operations.move_file_preserve_times", fake_move
        )

    @pytest.fixture()
    def ctx(self, workspace: Path) -> FakeRootContext:
        root = workspace / "photos"
        root.mkdir()
        deleted_dir = workspace / "data" / "roots" / "test_root" / "deleted"
        logs_dir = workspace / "data" / "roots" / "test_root" / "logs"
        thumbnails_dir = workspace / "data" / "roots" / "test_root" / "thumbnails"
        return FakeRootContext(root, deleted_dir, logs_dir, thumbnails_dir)

    @pytest.fixture()
    def use_case(self, ctx: FakeRootContext) -> PurgeImageUseCase:
        def fake_dispose(p: Path) -> None:
            self.disposed.append(p)
            if p.exists():
                p.unlink()

        return PurgeImageUseCase(
            root_context=ctx,
            thumbnails_dir=ctx.thumbnails_dir,
            dispose_fn=fake_dispose,
        )

    # ---------------------------------------------------------------
    # Helper: seed a deleted file with log
    # ---------------------------------------------------------------

    def _prepare_deleted(
        self,
        ctx: FakeRootContext,
        rel: str = "photo.jpg",
        content: str = "purge-me",
    ) -> Path:
        deleted_path = ctx.deleted_dir / "20260426_a1b2c3d4e5" / Path(rel).name
        touch(deleted_path, content)
        log_path = ctx.logs_dir / "delete_log.csv"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["timestamp", "root", "relative_path", "deleted_to", "action"])
            w.writerow(["2026-04-26T12:00:00", str(ctx.root), rel, str(deleted_path), "deleted"])
        return deleted_path

    # ---------------------------------------------------------------
    # Happy path
    # ---------------------------------------------------------------

    def test_purge_disposes_file(self, ctx, use_case):
        deleted_path = self._prepare_deleted(ctx)
        assert deleted_path.exists()

        req = PurgeImageRequest(deleted_to=str(deleted_path))
        result = use_case.execute(req)

        assert result["status"] == "purged"
        assert Path(result["deleted_to"]) == deleted_path.resolve()
        assert not deleted_path.exists()
        assert deleted_path in self.disposed

    def test_purge_writes_log(self, ctx, use_case):
        deleted_path = self._prepare_deleted(ctx)

        req = PurgeImageRequest(deleted_to=str(deleted_path))
        use_case.execute(req)

        rows = read_csv(ctx.logs_dir / "delete_log.csv")
        assert len(rows) == 2
        assert rows[1]["action"] == "purged"
        assert rows[1]["deleted_to"] == str(deleted_path)

    def test_purge_removes_stale_thumbnail(self, ctx, use_case):
        deleted_path = self._prepare_deleted(ctx, rel="thumb_test.jpg")
        from core.services.thumbnail_service import deleted_thumbnail_path_for
        thumb = deleted_thumbnail_path_for(ctx.thumbnails_dir, deleted_path)
        touch(thumb, "stale-thumb")
        assert thumb.exists()

        req = PurgeImageRequest(deleted_to=str(deleted_path))
        use_case.execute(req)

        assert not thumb.exists()

    def test_purge_renames_to_original_name_before_disposal(self, ctx, use_case):
        """If the deleted filename is a hash, rename back to original name."""
        deleted_dir = ctx.deleted_dir / "20260426_x1y2z3"
        deleted_path = touch(deleted_dir / "a1b2c3d4.jpg", "orig")
        log_path = ctx.logs_dir / "delete_log.csv"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["timestamp", "root", "relative_path", "deleted_to", "action"])
            w.writerow(["2026-04-26T12:00:00", str(ctx.root), "sub/nature.jpg", str(deleted_path), "deleted"])

        req = PurgeImageRequest(deleted_to=str(deleted_path))
        result = use_case.execute(req)

        assert result["status"] == "purged"
        renamed_path = deleted_dir / "nature.jpg"
        assert renamed_path in self.disposed
        assert not (deleted_dir / "a1b2c3d4.jpg").exists()

    # ---------------------------------------------------------------
    # Error cases
    # ---------------------------------------------------------------

    def test_purge_rejects_path_outside_deleted_dir(self, ctx, use_case):
        outside = ctx.root / "not_deleted.txt"
        req = PurgeImageRequest(deleted_to=str(outside))

        with pytest.raises(HTTPException) as exc:
            use_case.execute(req)
        assert exc.value.status_code == 400
        assert "Invalid deleted file path" in exc.value.detail

    def test_purge_raises_when_file_missing(self, ctx, use_case):
        fake = ctx.deleted_dir / "20260426_a1b2c3d4e5" / "missing.jpg"
        req = PurgeImageRequest(deleted_to=str(fake))

        with pytest.raises(HTTPException) as exc:
            use_case.execute(req)
        assert exc.value.status_code == 404
        assert "Deleted file not found" in exc.value.detail

    def test_purge_handles_missing_log(self, ctx, use_case):
        deleted_path = ctx.deleted_dir / "20260426_orphan" / "orphan.jpg"
        touch(deleted_path, "orphan-data")

        req = PurgeImageRequest(deleted_to=str(deleted_path))
        result = use_case.execute(req)

        assert result["status"] == "purged"
        assert not deleted_path.exists()
        rows = read_csv(ctx.logs_dir / "delete_log.csv")
        assert len(rows) == 1
        assert rows[0]["action"] == "purged"
        assert rows[0]["root"] == ""
        assert rows[0]["relative_path"] == ""


# ===================================================================
# ClearRecycleUseCase
# ===================================================================


class TestClearRecycleUseCase:
    """Tests for ClearRecycleUseCase.

    Uses real service calls for ``list_recycle_items`` and
    ``read_delete_log_rows``.  The ``archive_delete_log`` and
    ``remove_empty_deleted_parent`` helpers are monkeypatched.
    File disposal is injected via a fake ``dispose_fn``.
    """

    @pytest.fixture(autouse=True)
    def _inject_mocks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.disposed: list[Path] = []

        def fake_archive(log_dir: Path) -> dict:
            return {
                "archived": False,
                "archive_path": "",
                "archived_count": 0,
            }

        monkeypatch.setattr(
            "core.use_cases.clear_recycle.archive_log_service", fake_archive
        )
        monkeypatch.setattr(
            "core.use_cases.clear_recycle.remove_empty_deleted_parent",
            lambda _deleted_dir, _p: None,
        )

    @pytest.fixture()
    def ctx(self, workspace: Path) -> FakeRootContext:
        root = workspace / "photos"
        root.mkdir()
        deleted_dir = workspace / "data" / "roots" / "test_root" / "deleted"
        logs_dir = workspace / "data" / "roots" / "test_root" / "logs"
        thumbnails_dir = workspace / "data" / "roots" / "test_root" / "thumbnails"
        return FakeRootContext(root, deleted_dir, logs_dir, thumbnails_dir)

    @pytest.fixture()
    def use_case(self, ctx: FakeRootContext) -> ClearRecycleUseCase:
        def fake_dispose(p: Path) -> None:
            self.disposed.append(p)
            if p.exists():
                p.unlink()

        return ClearRecycleUseCase(
            root_context=ctx,
            thumbnails_dir=ctx.thumbnails_dir,
            dispose_fn=fake_dispose,
        )

    # ---------------------------------------------------------------
    # Helper: seed a deleted file
    # ---------------------------------------------------------------

    def _seed_deleted(self, ctx: FakeRootContext, rel: str, content: str = "data") -> Path:
        deleted_path = ctx.deleted_dir / "20260426_clear" / Path(rel).name
        touch(deleted_path, content)
        log_path = ctx.logs_dir / "delete_log.csv"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if log_path.stat().st_size == 0:
                w.writerow(["timestamp", "root", "relative_path", "deleted_to", "action"])
            w.writerow(["2026-04-26T12:00:00", str(ctx.root), rel, str(deleted_path), "deleted"])
        return deleted_path

    # ---------------------------------------------------------------
    # Validation
    # ---------------------------------------------------------------

    def test_clear_requires_confirmation(self, ctx, use_case):
        req = ClearRecycleRequest(confirm=False)

        with pytest.raises(HTTPException) as exc:
            use_case.execute(req)
        assert exc.value.status_code == 400
        assert "Confirmation required" in exc.value.detail

    # ---------------------------------------------------------------
    # Happy path
    # ---------------------------------------------------------------

    def test_clear_single_item(self, ctx, use_case):
        deleted_path = self._seed_deleted(ctx, "single.jpg")
        assert deleted_path.exists()

        req = ClearRecycleRequest(confirm=True)
        result = use_case.execute(req)

        assert result["status"] == "cleared"
        assert result["removed_count"] == 1
        assert not deleted_path.exists()
        assert deleted_path in self.disposed

    def test_clear_multiple_items(self, ctx, use_case):
        p1 = self._seed_deleted(ctx, "a.jpg")
        p2 = self._seed_deleted(ctx, "b.jpg")
        p3 = self._seed_deleted(ctx, "sub/c.jpg")

        req = ClearRecycleRequest(confirm=True)
        result = use_case.execute(req)

        assert result["removed_count"] == 3
        assert all(p in self.disposed for p in (p1, p2, p3))
        assert all(not p.exists() for p in (p1, p2, p3))

    def test_clear_skips_gitkeep(self, ctx, use_case):
        self._seed_deleted(ctx, "photo.jpg")
        gitkeep = ctx.deleted_dir / "20260426_clear" / ".gitkeep"
        touch(gitkeep, "keep")

        req = ClearRecycleRequest(confirm=True)
        result = use_case.execute(req)

        assert result["removed_count"] == 1
        assert gitkeep.exists()

    def test_clear_writes_purge_log_entries(self, ctx, use_case):
        self._seed_deleted(ctx, "logme.jpg")

        req = ClearRecycleRequest(confirm=True)
        use_case.execute(req)

        rows = read_csv(ctx.logs_dir / "delete_log.csv")
        assert len(rows) == 2
        purged = [r for r in rows if r.get("action") == "purged"]
        assert len(purged) == 1
        assert purged[0]["relative_path"] == "logme.jpg"

    def test_clear_empty_recycle_bin(self, ctx, use_case):
        req = ClearRecycleRequest(confirm=True)
        result = use_case.execute(req)

        assert result["status"] == "cleared"
        assert result["removed_count"] == 0
        assert result["log_archive"]["archived"] is False

    def test_clear_handles_orphan_files(self, ctx, use_case):
        orphan = ctx.deleted_dir / "20260426_orphan" / "orphan.jpg"
        touch(orphan, "orphan-data")
        self._seed_deleted(ctx, "legit.jpg")

        req = ClearRecycleRequest(confirm=True)
        result = use_case.execute(req)

        assert result["removed_count"] == 2
        assert not orphan.exists()

# ===================================================================
# ClearDeleteLogsUseCase
# ===================================================================


class TestClearDeleteLogsUseCase:
    """Tests for ClearDeleteLogsUseCase.

    Uses the real service functions (read/write CSV) but only operates
    on a temporary ``logs_dir``.
    """

    @pytest.fixture()
    def logs_dir(self, workspace: Path) -> Path:
        d = workspace / "logs"
        d.mkdir(parents=True)
        return d

    @pytest.fixture()
    def use_case(self, logs_dir: Path):
        from core.use_cases.clear_delete_logs import ClearDeleteLogsUseCase
        return ClearDeleteLogsUseCase(logs_dir=logs_dir)

    # ---------------------------------------------------------------
    # Helper: seed log rows
    # ---------------------------------------------------------------

    @staticmethod
    def _seed_log(logs_dir: Path, rows: list[dict[str, str]]) -> None:
        from core.services.recycle_service import write_delete_log_rows
        write_delete_log_rows(logs_dir, rows)

    # ---------------------------------------------------------------
    # Validation
    # ---------------------------------------------------------------

    def test_requires_confirmation(self, use_case):
        from core.use_cases.clear_delete_logs import ClearDeleteLogsRequest
        req = ClearDeleteLogsRequest(confirm=False)

        with pytest.raises(HTTPException) as exc:
            use_case.execute(req)
        assert exc.value.status_code == 400
        assert "Confirmation required" in exc.value.detail

    def test_rejects_unknown_actions(self, use_case):
        from core.use_cases.clear_delete_logs import ClearDeleteLogsRequest
        req = ClearDeleteLogsRequest(confirm=True, actions=["deleted"])

        with pytest.raises(HTTPException) as exc:
            use_case.execute(req)
        assert exc.value.status_code == 400
        assert "Unsupported log cleanup action" in exc.value.detail

    # ---------------------------------------------------------------
    # Happy path
    # ---------------------------------------------------------------

    def test_removes_matching_rows(self, logs_dir, use_case):
        self._seed_log(logs_dir, [
            {"timestamp": "2026-01-01T00:00:00", "root": "", "relative_path": "a.jpg", "deleted_to": "/d/a.jpg", "action": "deleted"},
            {"timestamp": "2026-01-02T00:00:00", "root": "", "relative_path": "b.jpg", "deleted_to": "/d/b.jpg", "action": "restored"},
            {"timestamp": "2026-01-03T00:00:00", "root": "", "relative_path": "c.jpg", "deleted_to": "/d/c.jpg", "action": "purged"},
        ])
        from core.use_cases.clear_delete_logs import ClearDeleteLogsRequest

        req = ClearDeleteLogsRequest(confirm=True, actions=["restored", "purged"])
        result = use_case.execute(req)

        assert result["status"] == "cleared_logs"
        assert result["removed_count"] == 2

        remaining = read_csv(logs_dir / "delete_log.csv")
        assert len(remaining) == 1
        assert remaining[0]["action"] == "deleted"

    def test_removes_only_requested_action(self, logs_dir, use_case):
        self._seed_log(logs_dir, [
            {"timestamp": "2026-01-01T00:00:00", "root": "", "relative_path": "a.jpg", "deleted_to": "/d/a.jpg", "action": "deleted"},
            {"timestamp": "2026-01-02T00:00:00", "root": "", "relative_path": "b.jpg", "deleted_to": "/d/b.jpg", "action": "restored"},
            {"timestamp": "2026-01-03T00:00:00", "root": "", "relative_path": "c.jpg", "deleted_to": "/d/c.jpg", "action": "purged"},
        ])
        from core.use_cases.clear_delete_logs import ClearDeleteLogsRequest

        req = ClearDeleteLogsRequest(confirm=True, actions=["purged"])
        result = use_case.execute(req)

        assert result["removed_count"] == 1

        remaining = read_csv(logs_dir / "delete_log.csv")
        assert len(remaining) == 2
        assert {r["action"] for r in remaining} == {"deleted", "restored"}

    def test_empty_log(self, logs_dir, use_case):
        from core.use_cases.clear_delete_logs import ClearDeleteLogsRequest
        req = ClearDeleteLogsRequest(confirm=True, actions=["purged"])
        result = use_case.execute(req)

        assert result["removed_count"] == 0


# ===================================================================
# ArchiveDeleteLogsUseCase
# ===================================================================


class TestArchiveDeleteLogsUseCase:
    """Tests for ArchiveDeleteLogsUseCase."""

    @pytest.fixture()
    def logs_dir(self, workspace: Path) -> Path:
        d = workspace / "logs"
        d.mkdir(parents=True)
        return d

    @pytest.fixture()
    def use_case(self, logs_dir: Path):
        from core.use_cases.archive_delete_logs import ArchiveDeleteLogsUseCase
        return ArchiveDeleteLogsUseCase(logs_dir=logs_dir)

    # ---------------------------------------------------------------
    # Validation
    # ---------------------------------------------------------------

    def test_requires_confirmation(self, use_case):
        from core.use_cases.archive_delete_logs import ArchiveDeleteLogsRequest
        req = ArchiveDeleteLogsRequest(confirm=False)

        with pytest.raises(HTTPException) as exc:
            use_case.execute(req)
        assert exc.value.status_code == 400
        assert "Confirmation required" in exc.value.detail

    # ---------------------------------------------------------------
    # Happy path
    # ---------------------------------------------------------------

    def test_archives_non_empty_log(self, logs_dir, use_case):
        from core.services.recycle_service import write_delete_log_rows
        write_delete_log_rows(logs_dir, [
            {"timestamp": "2026-01-01T00:00:00", "root": "", "relative_path": "a.jpg", "deleted_to": "/d/a.jpg", "action": "deleted"},
        ])

        from core.use_cases.archive_delete_logs import ArchiveDeleteLogsRequest
        req = ArchiveDeleteLogsRequest(confirm=True)
        result = use_case.execute(req)

        assert result["status"] == "archived_logs"
        assert result["archived"] is True
        assert result["archived_count"] == 1

        # The current log should now be empty (only header).
        remaining = read_csv(logs_dir / "delete_log.csv")
        assert len(remaining) == 0

        # An archive file should exist.
        archive_files = list(logs_dir.glob("delete_log_*.csv"))
        assert len(archive_files) >= 1

    def test_archive_empty_log(self, logs_dir, use_case):
        from core.use_cases.archive_delete_logs import ArchiveDeleteLogsRequest
        req = ArchiveDeleteLogsRequest(confirm=True)
        result = use_case.execute(req)

        assert result["status"] == "archived_logs"
        assert result["archived"] is False
        assert result["archived_count"] == 0
