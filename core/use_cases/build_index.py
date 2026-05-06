# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field

from core.domain.image_entry import ImageEntry
from core.repositories.index_repository import IndexRepository


class BuildIndexRequest(BaseModel):
    """Request to build / rebuild the full image index for the active root."""

    root_path: str = Field(default="", description="If empty, use the active root from RootContext")


class BuildIndexUseCase:
    """
    Build the full image index (index.json + summary + timeline) for a root.

    This use case orchestrates:
    1. Scanning image files via a provided scan iterator
    2. Reading metadata for each file (EXIF, dimensions, timestamps)
    3. Building ``ImageEntry`` instances and saving them via ``IndexRepository``

    ``scan_fn`` can be any callable with the signature:
        ``(root: Path) -> Iterable[dict[str, Any]]``
    and is expected to return items in the same format as
    ``image_scan_service.image_metadata_from_path()``.

    If ``scan_fn`` is not provided, a default implementation using
    ``image_scan_service.iter_image_files`` + ``image_metadata_from_path``
    will be used when ``execute()`` is called.
    """

    def __init__(
        self,
        index_repo: IndexRepository,
        root_context: object,
        scan_fn: Callable | None = None,
    ):
        """
        Args:
            index_repo: An ``IndexRepository`` instance bound to the root context.
            root_context: A RootContext-like object providing ``.root`` (Path),
                ``.indexes_dir`` (Path).
            scan_fn: Optional callable that yields dict-based scan items.
                      If None, the use case will fall back to a simple scan
                      at execution time.
        """
        self.index_repo = index_repo
        self.ctx = root_context
        self.scan_fn = scan_fn

    def execute(self, req: BuildIndexRequest | None = None) -> dict[str, Any]:
        """
        Build the index.

        Returns:
            dict with keys ``status`` ("ok" or "empty"),
            ``count`` (int), and ``root_hash`` (str).
        """
        root: Path = self.ctx.root

        # 1. Scan images — use the provided callable or fall back.
        if self.scan_fn is not None:
            scan_items: list[dict[str, Any]] = list(self.scan_fn(root))
        else:
            scan_items = self._default_scan(root)

        if not scan_items:
            return {"status": "empty", "count": 0, "root_hash": ""}

        # 2. Build ImageEntry list.
        entries = [ImageEntry.from_scan_item(item) for item in scan_items]

        # 3. Compute root hash and save.
        root_hash = self.index_repo.compute_root_hash(entries)
        self.index_repo.save_index(root_hash, entries)

        return {"status": "ok", "count": len(entries), "root_hash": root_hash}

    # ------------------------------------------------------------------
    # Default scan — used when no scan_fn was injected
    # ------------------------------------------------------------------

    @staticmethod
    def _default_scan(root: Path) -> list[dict[str, Any]]:
        """
        Minimal scan using the real ``image_scan_service`` functions.

        This is a convenience for direct usage; injected ``scan_fn`` is
        preferred for testability.
        """
        from core.services.image_scan_service import (
            image_metadata_from_path,
            iter_image_files,
        )
        from core.config.app_config import SUPPORTED_EXTENSIONS, SKIP_SCAN_DIR_NAMES

        return [
            image_metadata_from_path(root, file_path, include_exif=True)
            for file_path in sorted(
                iter_image_files(root, SUPPORTED_EXTENSIONS, SKIP_SCAN_DIR_NAMES),
                key=lambda p: str(p).lower(),
            )
        ]
