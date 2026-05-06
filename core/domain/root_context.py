from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from core.domain.root_config import RootConfig


def normalize_root_path(root: str | Path) -> str:
    return str(Path(root).expanduser().resolve())


def root_id_for(root: str | Path) -> str:
    normalized = normalize_root_path(root)
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RootContext:
    """
    Runtime workspace paths for one registered image root.

    The current layout is:
    data/roots/<root_id>/
      root.json
      hash_db.json
      duplicates.json
      deleted/
      indexes/
      logs/
      tasks/
      thumbnails/
    """

    root: Path
    root_id: str
    data_dir: Path

    def __init__(
        self,
        config: RootConfig | None = None,
        data_root: str | Path = "data/roots",
        *,
        root: str | Path | None = None,
        root_id: str | None = None,
        ensure: bool = True,
    ):
        if config is not None:
            root_value = config.root_path
            root_id_value = config.root_id
        elif root is not None:
            root_value = root
            root_id_value = root_id or root_id_for(root)
        else:
            raise ValueError("RootContext requires either config or root")

        normalized_root = Path(normalize_root_path(root_value))
        normalized_root_id = str(root_id_value).strip() or root_id_for(normalized_root)
        data_dir = Path(data_root) / normalized_root_id

        object.__setattr__(self, "root", normalized_root)
        object.__setattr__(self, "root_id", normalized_root_id)
        object.__setattr__(self, "data_dir", data_dir)

        if ensure:
            self.ensure()

    @classmethod
    def from_root(
        cls,
        root: str | Path,
        roots_dir: str | Path,
        *,
        ensure: bool = False,
    ) -> "RootContext":
        return cls(root=root, root_id=root_id_for(root), data_root=roots_dir, ensure=ensure)

    @property
    def root_json_path(self) -> Path:
        return self.data_dir / "root.json"

    @property
    def hash_db_path(self) -> Path:
        return self.data_dir / "hash_db.json"

    @property
    def duplicates_path(self) -> Path:
        return self.data_dir / "duplicates.json"

    @property
    def deleted_dir(self) -> Path:
        return self.data_dir / "deleted"

    @property
    def thumbnails_dir(self) -> Path:
        return self.data_dir / "thumbnails"

    @property
    def indexes_dir(self) -> Path:
        return self.data_dir / "indexes"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def tasks_dir(self) -> Path:
        return self.data_dir / "tasks"

    def ensure(self) -> Path:
        for directory in (
            self.data_dir,
            self.deleted_dir,
            self.indexes_dir,
            self.logs_dir,
            self.tasks_dir,
            self.thumbnails_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        return self.data_dir

    def deleted_path_for(self, src: Path) -> Path:
        rel = src.relative_to(self.root)
        return self.deleted_dir / rel

    def original_path_for(self, deleted: Path) -> Path:
        rel = deleted.relative_to(self.deleted_dir)
        return self.root / rel

    def thumbnail_path_for_hash(self, hash_str: str) -> Path:
        bucket1 = hash_str[:2]
        bucket2 = hash_str[2:4]
        return self.thumbnails_dir / bucket1 / bucket2 / f"{hash_str}.jpg"

    def index_file(self, root_hash: str) -> Path:
        return self.indexes_dir / f"{root_hash}.json"

    def summary_file(self, root_hash: str) -> Path:
        return self.indexes_dir / f"{root_hash}.summary.json"

    def timeline_file(self, root_hash: str) -> Path:
        return self.indexes_dir / f"{root_hash}.timeline.json"

    def copy_log_file(self) -> Path:
        return self.logs_dir / "copy_log.csv"

    def delete_log_file(self) -> Path:
        return self.logs_dir / "delete_log.csv"

    def task_dir(self, task_id: str, *, ensure: bool = True) -> Path:
        directory = self.tasks_dir / task_id
        if ensure:
            directory.mkdir(parents=True, exist_ok=True)
        return directory

    def duplicate_report_file(self, task_id: str) -> Path:
        return self.task_dir(task_id) / "duplicate_report.csv"

    def organizer_log_file(self, task_id: str) -> Path:
        return self.task_dir(task_id) / "organizer.log"
