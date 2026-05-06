from pathlib import Path
import shutil


class CacheRepository:
    """
    Cache management repository for ZeroTraceBrowser.
    Responsible for cache invalidation:
    - image list cache
    - index cache
    - timeline cache
    - Future extensibility: hash DB cache, duplicate cache
    """

    def __init__(self, root_context):
        self.ctx = root_context

    # ---------------------------------------------------------
    # Clear image list cache (legacy ctx.clear_image_list_cache)
    # ---------------------------------------------------------
    def clear_index_cache(self):
        """
        Delete all cache files under the indexes/ directory.
        For example:
        - <hash>.summary.json
        - <hash>.timeline.json
        """
        indexes_dir = self.ctx.indexes_dir

        if not indexes_dir.exists():
            return

        for f in indexes_dir.iterdir():
            # Only remove summary/timeline caches, keep the primary index.json
            if f.name.endswith(".summary.json") or f.name.endswith(".timeline.json"):
                try:
                    f.unlink()
                except Exception:
                    pass

    # ---------------------------------------------------------
    # Clear timeline cache (optional)
    # ---------------------------------------------------------
    def clear_timeline_cache(self):
        """
        Delete the timeline cache file.
        """
        indexes_dir = self.ctx.indexes_dir

        for f in indexes_dir.iterdir():
            if f.name.endswith(".timeline.json"):
                try:
                    f.unlink()
                except Exception:
                    pass

    # ---------------------------------------------------------
    # Clear all caches (optional)
    # ---------------------------------------------------------
    def clear_all(self):
        """
        Clear all caches (for future extension)
        """
        self.clear_index_cache()
        self.clear_timeline_cache()
