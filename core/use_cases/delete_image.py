from pydantic import BaseModel
from datetime import datetime
from pathlib import Path

class DeleteImageRequest(BaseModel):
    path: str


class DeleteImageUseCase:
    def __init__(self, file_repo, thumb_repo, log_repo, cache_repo, root_context):
        self.file_repo = file_repo
        self.thumb_repo = thumb_repo
        self.log_repo = log_repo
        self.cache_repo = cache_repo
        self.ctx = root_context

    def execute(self, req):
        # 1. 解析原始路径
        src = self.ctx.root / req.relative_path

        # 2. 文件不存在 → 清理缓存 + 删除缩略图
        if not src.exists() or not src.is_file():
            self.cache_repo.clear_index_cache()
            self.thumb_repo.delete_thumbnail(req.relative_path)
            return {"status": "missing", "relative_path": req.relative_path}

        # 3. 安全删除（移动到 deleted/）
        deleted_path = self.file_repo.safe_delete(str(src))

        # 4. 清理缓存
        self.cache_repo.clear_index_cache()

        # 5. 写日志
        self.log_repo.append_delete_log(
            timestamp=datetime.now().isoformat(),
            root=str(self.ctx.root),
            relative_path=req.relative_path,
            deleted_to=deleted_path,
        )

        # 6. 删除缩略图
        self.thumb_repo.delete_thumbnail(req.relative_path)

        return {"status": "deleted", "deleted_to": deleted_path}
