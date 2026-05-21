# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.storage.database import connect, init_root_database


class HashDbRepository:
    def __init__(self, database_path: str | Path):
        self.database_path = init_root_database(database_path)

    def save_hash_db(self, payload: dict[str, Any], source_path: str | Path = "") -> None:
        normalized = self._normalize_payload(payload)
        with connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO hash_db_metadata (id, source_path, raw_json, updated_at)
                VALUES (1, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    source_path = excluded.source_path,
                    raw_json = excluded.raw_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    str(source_path),
                    json.dumps(normalized, ensure_ascii=False),
                ),
            )
            connection.execute("DELETE FROM hash_db_records")
            for method, records in normalized.items():
                for hash_value, paths in records.items():
                    for position, path in enumerate(paths):
                        connection.execute(
                            """
                            INSERT OR IGNORE INTO hash_db_records
                                (method, hash, path, position)
                            VALUES (?, ?, ?, ?)
                            """,
                            (method, hash_value, path, position),
                        )
            connection.commit()

    def load_hash_db(self) -> dict[str, dict[str, list[str]]]:
        result = {"phash": {}, "strict": {}}
        with connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT method, hash, path
                FROM hash_db_records
                ORDER BY method, hash, position, id
                """
            ).fetchall()
        for row in rows:
            method = row["method"]
            if method not in result:
                result[method] = {}
            result[method].setdefault(row["hash"], []).append(row["path"])
        return result

    def load_summary(self) -> dict[str, Any]:
        with connect(self.database_path) as connection:
            metadata = connection.execute(
                "SELECT source_path, updated_at FROM hash_db_metadata WHERE id = 1"
            ).fetchone()
            if metadata is None:
                return {"available": False, "record_count": 0, "path_count": 0}
            rows = connection.execute(
                """
                SELECT method, COUNT(DISTINCT hash) AS record_count, COUNT(*) AS path_count
                FROM hash_db_records
                GROUP BY method
                """
            ).fetchall()
        method_counts = {
            row["method"]: {
                "record_count": row["record_count"],
                "path_count": row["path_count"],
            }
            for row in rows
        }
        return {
            "available": True,
            "source_path": metadata["source_path"],
            "updated_at": metadata["updated_at"],
            "record_count": sum(item["record_count"] for item in method_counts.values()),
            "path_count": sum(item["path_count"] for item in method_counts.values()),
            "method_counts": method_counts,
        }

    def clear_hash_db(self) -> None:
        with connect(self.database_path) as connection:
            connection.execute("DELETE FROM hash_db_metadata WHERE id = 1")
            connection.execute("DELETE FROM hash_db_records")
            connection.commit()

    def add_hash_record(self, method: str, hash_value: str, path: str | Path) -> None:
        method_value = str(method).strip()
        hash_value = str(hash_value).strip()
        path_value = str(path).strip()
        if not method_value or not hash_value or not path_value:
            return

        with connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO hash_db_metadata (id, source_path, raw_json, updated_at)
                VALUES (1, ?, '{}', CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET updated_at = CURRENT_TIMESTAMP
                """,
                (str(self.database_path),),
            )
            row = connection.execute(
                """
                SELECT COALESCE(MAX(position), -1) + 1
                FROM hash_db_records
                WHERE method = ? AND hash = ?
                """,
                (method_value, hash_value),
            ).fetchone()
            position = int(row[0] or 0)
            connection.execute(
                """
                INSERT OR IGNORE INTO hash_db_records
                    (method, hash, path, position)
                VALUES (?, ?, ?, ?)
                """,
                (method_value, hash_value, path_value, position),
            )
            connection.commit()

    @staticmethod
    def _normalize_payload(payload: dict[str, Any]) -> dict[str, dict[str, list[str]]]:
        if "phash" in payload or "strict" in payload:
            raw = {
                "phash": payload.get("phash", {}),
                "strict": payload.get("strict", {}),
            }
        else:
            raw = {"phash": payload, "strict": {}}

        normalized: dict[str, dict[str, list[str]]] = {"phash": {}, "strict": {}}
        for method, records in raw.items():
            if not isinstance(records, dict):
                continue
            method_key = str(method)
            normalized.setdefault(method_key, {})
            for hash_value, paths in records.items():
                if not isinstance(paths, list):
                    continue
                clean_paths = [str(path) for path in paths if str(path).strip()]
                if clean_paths:
                    normalized[method_key][str(hash_value)] = clean_paths
        return normalized
