from pathlib import Path


class ThumbnailRepository:
    """
    ZeroTraceBrowser 缩略图仓库。
    负责删除缩略图，不负责生成（生成由 ThumbnailGenerator 完成）。
    """

    def __init__(self, root_context):
        self.ctx = root_context

    # ---------------------------------------------------------
    # 删除：根据 relative_path 删除缩略图
    # ---------------------------------------------------------
    def delete_by_relative_path(self, relative_path: str):
        """
        删除某个相对路径对应的缩略图。
        """
        thumb = self.ctx.thumbnail_path_for_relative(relative_path)
        if thumb.exists():
            thumb.unlink()

    # ---------------------------------------------------------
    # 删除：根据 hash 删除缩略图（可选）
    # ---------------------------------------------------------
    def delete_by_hash(self, hash_str: str):
        """
        删除某个哈希对应的缩略图。
        """
        thumb = self.ctx.thumbnail_path_for_hash(hash_str)
        if thumb.exists():
            thumb.unlink()
