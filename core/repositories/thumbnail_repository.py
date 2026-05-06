# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path

from core.services.thumbnail_service import thumbnail_path_for


class ThumbnailRepository:
    """
    ZeroTraceBrowser 缩略图仓库。
    负责删除缩略图，不负责生成（生成由 ThumbnailGenerator 完成）。
    """

    def __init__(self, root_context, thumbnails_dir: Path | None = None):
        """
        Args:
            root_context: RootContext 实例，提供 ``.root``、``.thumbnails_dir`` 等属性。
            thumbnails_dir: 可选的缩略图根目录。如果为 None，则使用
                ``root_context.thumbnails_dir``。
        """
        self.ctx = root_context
        self.thumbnails_dir = thumbnails_dir or root_context.thumbnails_dir

    # ---------------------------------------------------------
    # 删除：根据 relative_path 删除缩略图
    # ---------------------------------------------------------
    def delete_by_relative_path(self, relative_path: str) -> None:
        """
        删除某个相对路径对应的缩略图。

        使用与 ``thumbnail_service.thumbnail_path_for`` 相同的哈希算法
        定位缩略图。
        """
        root: Path = self.ctx.root
        thumb = thumbnail_path_for(self.thumbnails_dir, root, relative_path)
        if thumb.exists():
            thumb.unlink()

    # ---------------------------------------------------------
    # 删除：根据 hash 删除缩略图（可选）
    # ---------------------------------------------------------
    def delete_by_hash(self, hash_str: str) -> None:
        """
        删除某个哈希对应的缩略图（通过 RootContext.thumbnail_path_for_hash）。
        """
        thumb = self.ctx.thumbnail_path_for_hash(hash_str)
        if thumb.exists():
            thumb.unlink()

