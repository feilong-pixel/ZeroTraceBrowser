import json
import hashlib
from pathlib import Path
from core.domain.image_entry import ImageEntry

class IndexRepository:
    def __init__(self, root_context):
        self.ctx = root_context

    def build_entry(self, path: Path, meta: dict):
        return ImageEntry(
            path=str(path),
            relative_path=str(path.relative_to(self.ctx.root)),
            timestamp=meta.get("timestamp"),
            width=meta.get("width"),
            height=meta.get("height"),
            hash=meta.get("hash"),
        )

    def compute_root_hash(self, entries):
        h = hashlib.sha1()
        for e in entries:
            h.update(e.path.encode())
        return h.hexdigest()

    def save_index(self, root_hash, entries):
        path = self.ctx.index_file(root_hash)
        path.write_text(
            json.dumps([e.dict() for e in entries], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
