import hashlib
from pathlib import Path


class HashCalculator:
    """
    File hash calculator for ZeroTraceBrowser.
    Used for duplicate detection.
    """

    def __init__(self, chunk_size: int = 1024 * 1024):
        self.chunk_size = chunk_size

    def compute_hash(self, path: str) -> str:
        """
        Compute the SHA1 hash of a file.
        """
        h = hashlib.sha1()
        p = Path(path)

        with p.open("rb") as f:
            while chunk := f.read(self.chunk_size):
                h.update(chunk)

        return h.hexdigest()
