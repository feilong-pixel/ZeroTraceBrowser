import hashlib
from pathlib import Path


class HashCalculator:
    """
    ZeroTraceBrowser 的文件哈希计算器。
    用于重复检测（duplicate detection）。
    """

    def __init__(self, chunk_size: int = 1024 * 1024):
        self.chunk_size = chunk_size

    def compute_hash(self, path: str) -> str:
        """
        计算文件的 SHA1 哈希。
        """
        h = hashlib.sha1()
        p = Path(path)

        with p.open("rb") as f:
            while chunk := f.read(self.chunk_size):
                h.update(chunk)

        return h.hexdigest()
