from pathlib import Path
import shutil


class CacheRepository:
    """
    ZeroTraceBrowser 的缓存管理仓库。
    负责清理：
    - image list cache
    - index cache
    - timeline cache
    - 未来可扩展：hash_db cache、duplicate cache
    """

    def __init__(self, root_context):
        self.ctx = root_context

    # ---------------------------------------------------------
    # 清理图片列表缓存（旧系统的 ctx.clear_image_list_cache）
    # ---------------------------------------------------------
    def clear_index_cache(self):
        """
        删除 indexes/ 目录下的所有缓存文件。
        例如：
        - <hash>.summary.json
        - <hash>.timeline.json
        """
        indexes_dir = self.ctx.indexes_dir

        if not indexes_dir.exists():
            return

        for f in indexes_dir.iterdir():
            # 只删除 summary / timeline，不删除主 index.json
            if f.name.endswith(".summary.json") or f.name.endswith(".timeline.json"):
                try:
                    f.unlink()
                except Exception:
                    pass

    # ---------------------------------------------------------
    # 清理 timeline 缓存（可选）
    # ---------------------------------------------------------
    def clear_timeline_cache(self):
        """
        删除 timeline 缓存文件。
        """
        indexes_dir = self.ctx.indexes_dir

        for f in indexes_dir.iterdir():
            if f.name.endswith(".timeline.json"):
                try:
                    f.unlink()
                except Exception:
                    pass

    # ---------------------------------------------------------
    # 清理所有缓存（可选）
    # ---------------------------------------------------------
    def clear_all(self):
        """
        清理所有缓存（未来扩展用）
        """
        self.clear_index_cache()
        self.clear_timeline_cache()
