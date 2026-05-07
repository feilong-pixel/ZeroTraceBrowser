# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path

from core.services.thumbnail_service import thumbnail_path_for


class ThumbnailRepository:
    """
    Thumbnail repository for ZeroTraceBrowser.
    Responsible for deleting thumbnails; generation is handled by ThumbnailGenerator.
    """

    def __init__(self, root_context, thumbnails_dir: Path | None = None):
        """
        Args:
            root_context: RootContext instance providing ``.root``, ``.thumbnails_dir``, etc.
            thumbnails_dir: Optional thumbnail root directory. If None, uses
                ``root_context.thumbnails_dir``。
        """
        self.ctx = root_context
        self.thumbnails_dir = thumbnails_dir or root_context.thumbnails_dir

    # ---------------------------------------------------------
    # Delete: remove thumbnail by relative_path
    # ---------------------------------------------------------
    def delete_by_relative_path(self, relative_path: str) -> None:
        """
        Delete the thumbnail corresponding to a given relative path.

        Uses the same hashing algorithm as ``thumbnail_service.thumbnail_path_for``
        to locate the thumbnail.
        """
        root: Path = self.ctx.root
        thumb = thumbnail_path_for(self.thumbnails_dir, root, relative_path)
        if thumb.exists():
            thumb.unlink()

    # ---------------------------------------------------------
    # Delete: remove thumbnail by hash (optional)
    # ---------------------------------------------------------
    def delete_by_hash(self, hash_str: str) -> None:
        """
        Delete the thumbnail for a given hash via RootContext.thumbnail_path_for_hash.
        """
        thumb = self.ctx.thumbnail_path_for_hash(hash_str)
        if thumb.exists():
            thumb.unlink()

