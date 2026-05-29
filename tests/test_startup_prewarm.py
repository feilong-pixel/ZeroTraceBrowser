# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path

from core.app.prewarm import prewarm_startup_caches, start_startup_prewarm
from core.app.factory import create_app


class FakeRouteContext:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.calls: list[tuple[object, ...]] = []

    def get_active_image_root(self) -> Path:
        self.calls.append(("get_active_image_root",))
        return self.root

    def get_root_summary(self, root: Path) -> dict[str, object]:
        self.calls.append(("get_root_summary", root))
        return {"image_count": 0, "duplicate_group_count": 0, "updated_at": ""}

    def list_images_cached_page(
        self,
        root: Path,
        offset: int,
        limit: int,
        refresh: bool,
        include_total: bool,
    ) -> dict[str, object]:
        self.calls.append(("list_images_cached_page", root, offset, limit, refresh, include_total))
        return {"items": [], "count": 0}

    def get_timeline_index(self, root: Path) -> dict[str, object]:
        self.calls.append(("get_timeline_index", root))
        return {"entries": [], "available": False}


class FailingRouteContext:
    def get_active_image_root(self) -> Path:
        raise RuntimeError("active root unavailable")


def test_startup_prewarm_reads_first_page_without_refresh_scan(tmp_path: Path) -> None:
    ctx = FakeRouteContext(tmp_path / "images")

    prewarm_startup_caches(ctx, image_limit=12)

    assert ctx.calls == [
        ("get_active_image_root",),
        ("get_root_summary", ctx.root),
        ("list_images_cached_page", ctx.root, 0, 12, False, False),
    ]


def test_startup_prewarm_can_warm_timeline_later(tmp_path: Path) -> None:
    ctx = FakeRouteContext(tmp_path / "images")

    prewarm_startup_caches(ctx, image_limit=12, include_timeline=True)

    assert ctx.calls == [
        ("get_active_image_root",),
        ("get_root_summary", ctx.root),
        ("list_images_cached_page", ctx.root, 0, 12, False, False),
        ("get_timeline_index", ctx.root),
    ]


def test_startup_prewarm_skips_when_active_root_is_unavailable() -> None:
    prewarm_startup_caches(FailingRouteContext())


def test_create_app_exposes_route_context_for_lifespan() -> None:
    app = create_app()

    assert app.state.route_context is not None


def test_startup_prewarm_thread_is_disabled_under_pytest(tmp_path: Path) -> None:
    assert start_startup_prewarm(FakeRouteContext(tmp_path / "images")) is None
