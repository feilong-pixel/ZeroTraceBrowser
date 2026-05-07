import hashlib
from pathlib import Path

from pydantic import BaseModel


def normalize_root_path(root: str | Path) -> str:
    return str(Path(root).expanduser().resolve())


def root_id_for(root: str | Path) -> str:
    normalized = normalize_root_path(root)
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


class RootConfig(BaseModel):
    root_id: str
    root_path: str

    @staticmethod
    def create(root_path: str):
        return RootConfig(
            root_id=root_id_for(root_path),
            root_path=root_path,
        )
