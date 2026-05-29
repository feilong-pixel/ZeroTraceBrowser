# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.storage.database import connect, init_root_database


class RecycleRepository:
    def __init__(self, database_path: str | Path):
        self.database_path = init_root_database(database_path)

    def append_record(
        self,
        *,
        timestamp: str,
        root: str,
        relative_path: str,
        deleted_to: str,
        action: str = "deleted",
    ) -> None:
        with connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO recycle_records
                    (timestamp, root, relative_path, deleted_to, action, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(deleted_to) DO UPDATE SET
                    timestamp = excluded.timestamp,
                    root = excluded.root,
                    relative_path = excluded.relative_path,
                    action = excluded.action,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (timestamp, root, relative_path, deleted_to, action),
            )
            connection.commit()

    def list_records(
        self,
        *,
        include_terminal: bool = True,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        where = "" if include_terminal else "WHERE action NOT IN ('restored', 'purged')"
        paging = ""
        params: list[Any] = []
        if limit is not None:
            paging = "LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        with connect(self.database_path) as connection:
            return [
                {
                    "timestamp": row["timestamp"],
                    "root": row["root"],
                    "relative_path": row["relative_path"],
                    "deleted_to": row["deleted_to"],
                    "action": row["action"],
                }
                for row in connection.execute(
                    f"""
                    SELECT * FROM recycle_records
                    {where}
                    ORDER BY timestamp DESC, id DESC
                    {paging}
                    """,
                    params,
                ).fetchall()
            ]

    def count_records(self, *, include_terminal: bool = True) -> int:
        where = "" if include_terminal else "WHERE action NOT IN ('restored', 'purged')"
        with connect(self.database_path) as connection:
            return int(
                connection.execute(
                    f"""
                    SELECT COUNT(*) FROM recycle_records
                    {where}
                    """
                ).fetchone()[0]
            )

    def sync_signature(self) -> tuple[int, str]:
        with connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS count, COALESCE(MAX(updated_at), '') AS updated_at
                FROM recycle_records
                """
            ).fetchone()
            return int(row["count"]), str(row["updated_at"])

    def update_action(self, deleted_to: str, action: str) -> bool:
        with connect(self.database_path) as connection:
            cursor = connection.execute(
                """
                UPDATE recycle_records
                SET action = ?, updated_at = CURRENT_TIMESTAMP
                WHERE deleted_to = ?
                """,
                (action, deleted_to),
            )
            connection.commit()
            return cursor.rowcount > 0

    def clear_records(self, *, actions: set[str] | None = None) -> int:
        with connect(self.database_path) as connection:
            if actions:
                placeholders = ",".join("?" for _ in actions)
                cursor = connection.execute(
                    f"DELETE FROM recycle_records WHERE action IN ({placeholders})",
                    sorted(actions),
                )
            else:
                cursor = connection.execute("DELETE FROM recycle_records")
            connection.commit()
            return cursor.rowcount
