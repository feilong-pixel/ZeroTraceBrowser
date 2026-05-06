from pydantic import BaseModel
from typing import List
from core.domain.image_entry import ImageEntry

class BuildIndexRequest(BaseModel):
    root_path: str

class BuildIndexUseCase:
    def __init__(self, file_repo, index_repo, metadata_reader, root_context):
        self.file_repo = file_repo
        self.index_repo = index_repo
        self.metadata_reader = metadata_reader
        self.ctx = root_context

    def execute(self):
        # 1. 扫描所有图片
        files = list(self.file_repo.scan_images(str(self.ctx.root)))

        # 2. 读取元数据（EXIF、尺寸、时间）
        entries = []
        for f in files:
            meta = self.metadata_reader.read(f)
            entries.append(self.index_repo.build_entry(f, meta))

        # 3. 保存 index.json
        root_hash = self.index_repo.compute_root_hash(entries)
        self.index_repo.save_index(root_hash, entries)

        # 4. 返回 index 信息
        return {"status": "ok", "count": len(entries), "root_hash": root_hash}
