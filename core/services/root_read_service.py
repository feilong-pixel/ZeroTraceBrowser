# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.config.app_config import ROOT_DATA_DIR
from core.domain.root_context import RootContext
from core.storage.duplicates_repository import DuplicateResultRepository
from core.storage.hash_db_repository import HashDbRepository


@dataclass(frozen=True)
class RootReadService:
    root: Path
    context: RootContext

    @classmethod
    def from_root(cls, root: str | Path, root_data_dir: str | Path = ROOT_DATA_DIR) -> "RootReadService":
        normalized_root = Path(root).expanduser().resolve()
        return cls(
            root=normalized_root,
            context=RootContext.from_root(normalized_root, Path(root_data_dir), ensure=True),
        )

    @property
    def database_path(self) -> Path:
        return self.context.database_path

    @property
    def indexes_dir(self) -> Path:
        return self.context.indexes_dir

    def duplicate_repository(self, *, ensure_schema: bool = True) -> DuplicateResultRepository:
        return DuplicateResultRepository(self.database_path, ensure_schema=ensure_schema)

    def hash_repository(self) -> HashDbRepository:
        return HashDbRepository(self.database_path)

    def load_duplicate_result(self) -> dict[str, Any] | None:
        return self.duplicate_repository(ensure_schema=False).load_result()

    def load_duplicate_result_page(
        self,
        *,
        offset: int,
        limit: int,
        method: str,
    ) -> dict[str, Any] | None:
        return self.duplicate_repository(ensure_schema=False).load_result_page(
            offset=offset,
            limit=limit,
            method=method,
        )

    def load_remaining_duplicate_result_page(
        self,
        *,
        offset: int,
        limit: int,
        method: str,
    ) -> dict[str, Any] | None:
        return self.duplicate_repository(ensure_schema=False).load_remaining_result_page(
            offset=offset,
            limit=limit,
            method=method,
        )

    def load_duplicate_summary(self) -> dict[str, Any]:
        return self.duplicate_repository(ensure_schema=False).load_summary()

    def load_hash_db(self) -> dict[str, dict[str, list[str]]]:
        return self.hash_repository().load_hash_db()
