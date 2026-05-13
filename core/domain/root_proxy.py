# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path
from typing import Any


def build_root_proxy(ctx: Any, active_root: Path) -> object:
    """
    Create a lightweight namespace object that provides the four
    properties use cases expect from a "root context":

    - ``.root`` – the active image root path
    - ``.deleted_dir`` – root-scoped deleted/ directory
    - ``.logs_dir`` – root-scoped logs/ directory
    - ``.thumbnails_dir`` – root-scoped thumbnails/ directory
    - ``.database_path`` – root-scoped SQLite database path

    This replaces the repetitive inline ``class _XxxRootProxy``
    definitions that were duplicated in every route handler.
    """
    return _RootProxy(
        root=active_root,
        deleted_dir=ctx.root_deleted_dir(active_root),
        logs_dir=ctx.root_log_dir(active_root),
        thumbnails_dir=ctx.root_thumbnail_dir(active_root),
        database_path=ctx.root_database_path(active_root),
    )


class _RootProxy:
    """
    Simple data holder to satisfy use-case root context duck-typing.
    Not intended for direct instantiation outside of ``build_root_proxy``.
    """

    def __init__(
        self,
        root: Path,
        deleted_dir: Path,
        logs_dir: Path,
        thumbnails_dir: Path,
        database_path: Path,
    ) -> None:
        self.root = root
        self.deleted_dir = deleted_dir
        self.logs_dir = logs_dir
        self.thumbnails_dir = thumbnails_dir
        self.database_path = database_path
