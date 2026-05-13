# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.storage.database import connect, init_root_database


class ExifRepository:
    def __init__(self, database_path: str | Path):
        self.database_path = init_root_database(database_path)

    def load_exif(self, relative_path: str, *, file_size: int, mtime_ns: int) -> dict[str, Any] | None:
        with connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT raw_json
                FROM image_exif_cache
                WHERE relative_path = ? AND file_size = ? AND mtime_ns = ?
                """,
                (relative_path, file_size, mtime_ns),
            ).fetchone()
        if row is None:
            return None
        try:
            payload = json.loads(row["raw_json"])
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    def save_exif(
        self,
        relative_path: str,
        payload: dict[str, Any],
        *,
        file_size: int,
        mtime_ns: int,
    ) -> None:
        with connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO image_exif_cache
                    (relative_path, file_size, mtime_ns, raw_json, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(relative_path) DO UPDATE SET
                    file_size = excluded.file_size,
                    mtime_ns = excluded.mtime_ns,
                    raw_json = excluded.raw_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (relative_path, file_size, mtime_ns, json.dumps(payload, ensure_ascii=False)),
            )
            connection.commit()
