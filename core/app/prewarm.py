# SPDX-License-Identifier: MIT

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path
from typing import Any


STARTUP_PREWARM_IMAGE_LIMIT = 48
STARTUP_PREWARM_DELAY_SECONDS = 2.0
STARTUP_TIMELINE_PREWARM_DELAY_SECONDS = 20.0


def prewarm_startup_caches(
    ctx: Any,
    image_limit: int = STARTUP_PREWARM_IMAGE_LIMIT,
    include_timeline: bool = False,
) -> None:
    """Warm lightweight startup caches after the app is already serving pages."""
    started_at = time.perf_counter()
    try:
        root = Path(ctx.get_active_image_root())
        ctx.get_root_summary(root)
        ctx.list_images_cached_page(
            root,
            0,
            image_limit,
            False,
            False,
        )
        if include_timeline:
            ctx.get_timeline_index(root)
    except Exception as exc:
        print(f"[prewarm] startup cache prewarm skipped: {exc}")
        return

    elapsed_ms = (time.perf_counter() - started_at) * 1000
    if elapsed_ms >= 100:
        print(f"[prewarm] startup caches warmed in {elapsed_ms:.1f}ms root={root}")


def _run_startup_prewarm(ctx: Any) -> None:
    time.sleep(STARTUP_PREWARM_DELAY_SECONDS)
    prewarm_startup_caches(ctx)

    time.sleep(STARTUP_TIMELINE_PREWARM_DELAY_SECONDS)
    prewarm_startup_caches(ctx, image_limit=STARTUP_PREWARM_IMAGE_LIMIT, include_timeline=True)


def start_startup_prewarm(ctx: Any) -> threading.Thread | None:
    if os.environ.get("PYTEST_CURRENT_TEST") or "pytest" in sys.modules:
        return None

    thread = threading.Thread(
        target=_run_startup_prewarm,
        args=(ctx,),
        name="zerotrace-startup-prewarm",
        daemon=True,
    )
    thread.start()
    return thread
