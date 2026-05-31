# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from core.storage.database import connect, init_root_database


class DuplicateResultRepository:
    def __init__(self, database_path: str | Path, *, ensure_schema: bool = True):
        self.database_path = init_root_database(database_path) if ensure_schema else Path(database_path)

    def mark_item_missing(self, path: str) -> int:
        return self._set_item_exists(path, False)

    def mark_item_available(self, path: str) -> int:
        return self._set_item_exists(path, True)

    def mark_items_missing(self, paths: list[str]) -> int:
        return self._set_items_exists(paths, False)

    def mark_items_available(self, paths: list[str]) -> int:
        return self._set_items_exists(paths, True)

    def _set_item_exists(self, path: str, exists: bool) -> int:
        if not self.database_path.exists():
            return 0
        try:
            with connect(self.database_path) as connection:
                cursor = connection.execute(
                    """
                    UPDATE duplicate_items
                    SET file_exists = ?
                    WHERE path = ?
                    """,
                    (1 if exists else 0, path),
                )
                connection.commit()
                return cursor.rowcount
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
            return 0

    def _set_items_exists(self, paths: list[str], exists: bool) -> int:
        normalized_paths = sorted({str(path) for path in paths if str(path).strip()})
        if not normalized_paths or not self.database_path.exists():
            return 0
        try:
            with connect(self.database_path) as connection:
                cursor = connection.executemany(
                    """
                    UPDATE duplicate_items
                    SET file_exists = ?
                    WHERE path = ?
                    """,
                    [(1 if exists else 0, path) for path in normalized_paths],
                )
                connection.commit()
                return cursor.rowcount
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
            return 0

    def save_result(self, payload: dict[str, Any], source_path: str | Path = "") -> None:
        groups = payload.get("groups", [])
        if not isinstance(groups, list):
            groups = []
        group_count = payload.get("group_count")
        if not isinstance(group_count, int):
            group_count = len(groups)

        with connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO duplicate_results
                    (id, generated_at, destination_root, group_count, source_path, raw_json, dirty, dirty_reason, dirty_at, updated_at)
                VALUES (1, ?, ?, ?, ?, ?, 0, '', NULL, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    generated_at = excluded.generated_at,
                    destination_root = excluded.destination_root,
                    group_count = excluded.group_count,
                    source_path = excluded.source_path,
                    raw_json = excluded.raw_json,
                    dirty = 0,
                    dirty_reason = '',
                    dirty_at = NULL,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    payload.get("generated_at"),
                    str(payload.get("destination_root", "")),
                    group_count,
                    str(source_path),
                    json.dumps(payload, ensure_ascii=False),
                ),
            )
            connection.execute("DELETE FROM duplicate_groups WHERE result_id = 1")
            for group_position, group in enumerate(groups):
                if not isinstance(group, dict):
                    continue
                group_id = str(group.get("group_id") or f"group_{group_position:06d}")
                cursor = connection.execute(
                    """
                    INSERT INTO duplicate_groups
                        (result_id, group_id, reason, hash, kept_path, item_count, position, raw_json)
                    VALUES (1, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        group_id,
                        str(group.get("reason", "-")),
                        str(group.get("hash", "")),
                        str(group.get("kept_path", "")),
                        len(group.get("items", [])) if isinstance(group.get("items"), list) else 0,
                        group_position,
                        json.dumps(group, ensure_ascii=False),
                    ),
                )
                group_row_id = cursor.lastrowid
                items = group.get("items", [])
                if not isinstance(items, list):
                    continue
                for item_position, item in enumerate(items):
                    if not isinstance(item, dict) or not item.get("path"):
                        continue
                    connection.execute(
                        """
                        INSERT INTO duplicate_items
                            (group_row_id, role, path, file_exists, position, raw_json)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            group_row_id,
                            str(item.get("role", "")),
                            str(item["path"]),
                            1 if bool(item.get("exists", True)) else 0,
                            item_position,
                            json.dumps(item, ensure_ascii=False),
                        ),
                    )
            connection.commit()

    def load_result(self) -> dict[str, Any] | None:
        if not self.database_path.exists():
            return None
        try:
            with connect(self.database_path) as connection:
                result = connection.execute("SELECT * FROM duplicate_results WHERE id = 1").fetchone()
                if result is None:
                    return None
                groups = []
                group_rows = connection.execute(
                    """
                    SELECT * FROM duplicate_groups
                    WHERE result_id = 1
                    ORDER BY position, id
                    """
                ).fetchall()
                for group in group_rows:
                    items = [
                        {
                            "role": item["role"],
                            "path": item["path"],
                            "exists": bool(item["file_exists"]),
                        }
                        for item in connection.execute(
                            """
                            SELECT * FROM duplicate_items
                            WHERE group_row_id = ?
                            ORDER BY position, id
                            """,
                            (group["id"],),
                        ).fetchall()
                    ]
                    groups.append(
                        {
                            "group_id": group["group_id"],
                            "reason": group["reason"],
                            "hash": group["hash"],
                            "kept_path": group["kept_path"],
                            "item_count": group["item_count"],
                            "items": items,
                        }
                    )
                return {
                    "generated_at": result["generated_at"],
                    "destination_root": result["destination_root"],
                    "group_count": result["group_count"],
                    "source_path": result["source_path"],
                    "dirty": bool(result["dirty"]),
                    "dirty_reason": result["dirty_reason"],
                    "dirty_at": result["dirty_at"],
                    "groups": groups,
                }
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
            return None

    def load_result_page(
        self,
        *,
        offset: int,
        limit: int,
        method: str = "",
    ) -> dict[str, Any] | None:
        if not self.database_path.exists():
            return None
        try:
            with connect(self.database_path) as connection:
                result = connection.execute("SELECT * FROM duplicate_results WHERE id = 1").fetchone()
                if result is None:
                    return None

                method_counts = {
                    row["reason"]: row["count"]
                    for row in connection.execute(
                        """
                        SELECT reason, COUNT(*) AS count
                        FROM duplicate_groups
                        WHERE result_id = 1
                        GROUP BY reason
                        """
                    ).fetchall()
                }
                query = """
                    SELECT * FROM duplicate_groups
                    WHERE result_id = 1
                """
                params: list[Any] = []
                if method:
                    query += " AND lower(reason) = ?"
                    params.append(method.lower())
                query += " ORDER BY position, id LIMIT ? OFFSET ?"
                params.extend([limit, offset])

                groups = []
                for group in connection.execute(query, params).fetchall():
                    items = [
                        {
                            "role": item["role"],
                            "path": item["path"],
                            "exists": bool(item["file_exists"]),
                        }
                        for item in connection.execute(
                            """
                            SELECT * FROM duplicate_items
                            WHERE group_row_id = ?
                            ORDER BY position, id
                            """,
                            (group["id"],),
                        ).fetchall()
                    ]
                    groups.append(
                        {
                            "group_id": group["group_id"],
                            "reason": group["reason"],
                            "hash": group["hash"],
                            "kept_path": group["kept_path"],
                            "item_count": group["item_count"],
                            "items": items,
                        }
                    )

                return {
                    "generated_at": result["generated_at"],
                    "destination_root": result["destination_root"],
                    "group_count": result["group_count"],
                    "source_path": result["source_path"],
                    "dirty": bool(result["dirty"]),
                    "dirty_reason": result["dirty_reason"],
                    "dirty_at": result["dirty_at"],
                    "method_counts": method_counts,
                    "groups": groups,
                }
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
            return None

    def load_remaining_result_page(
        self,
        *,
        offset: int,
        limit: int,
        method: str = "",
    ) -> dict[str, Any] | None:
        if not self.database_path.exists():
            return None
        try:
            with connect(self.database_path) as connection:
                result = connection.execute("SELECT * FROM duplicate_results WHERE id = 1").fetchone()
                if result is None:
                    return None

                method_counts = self._load_remaining_method_counts(connection)
                query = """
                    SELECT g.*
                    FROM duplicate_groups g
                    WHERE g.result_id = 1
                      AND (
                          SELECT COUNT(*)
                          FROM duplicate_items i
                          WHERE i.group_row_id = g.id
                            AND i.file_exists = 1
                      ) >= 2
                """
                params: list[Any] = []
                if method:
                    query += " AND lower(g.reason) = ?"
                    params.append(method.lower())
                query += " ORDER BY g.position, g.id LIMIT ? OFFSET ?"
                params.extend([limit, offset])

                groups = [self._group_from_row(connection, group) for group in connection.execute(query, params).fetchall()]

                return {
                    "generated_at": result["generated_at"],
                    "destination_root": result["destination_root"],
                    "group_count": sum(method_counts.values()),
                    "source_path": result["source_path"],
                    "dirty": bool(result["dirty"]),
                    "dirty_reason": result["dirty_reason"],
                    "dirty_at": result["dirty_at"],
                    "method_counts": method_counts,
                    "groups": groups,
                }
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
            return None

    def load_summary(self) -> dict[str, Any]:
        if not self.database_path.exists():
            return {"available": False, "group_count": 0, "dirty": False}
        try:
            with connect(self.database_path) as connection:
                result = connection.execute(
                    "SELECT generated_at, destination_root, group_count, source_path, dirty, dirty_reason, dirty_at, updated_at FROM duplicate_results WHERE id = 1"
                ).fetchone()
                if result is None:
                    return {"available": False, "group_count": 0, "dirty": False}
                method_counts = {
                    row["reason"]: row["count"]
                    for row in connection.execute(
                        """
                        SELECT remaining.reason, COUNT(*) AS count
                        FROM (
                            SELECT g.id, g.reason
                            FROM duplicate_groups g
                            JOIN duplicate_items i ON i.group_row_id = g.id
                            WHERE g.result_id = 1
                              AND g.reason IN ('strict', 'phash')
                              AND i.file_exists = 1
                            GROUP BY g.id
                            HAVING COUNT(i.id) >= 2
                        ) remaining
                        GROUP BY remaining.reason
                        """
                    ).fetchall()
                }
                return {
                    "available": True,
                    "generated_at": result["generated_at"],
                    "destination_root": result["destination_root"],
                    "group_count": sum(method_counts.values()),
                    "source_path": result["source_path"],
                    "dirty": bool(result["dirty"]),
                    "dirty_reason": result["dirty_reason"],
                    "dirty_at": result["dirty_at"],
                    "updated_at": result["updated_at"],
                    "method_counts": method_counts,
                }
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
            return {"available": False, "group_count": 0, "dirty": False}

    def clear_result(self) -> None:
        with connect(self.database_path) as connection:
            connection.execute("DELETE FROM duplicate_results WHERE id = 1")
            connection.commit()

    def mark_dirty(self, destination_root: str | Path, reason: str = "hash_db_changed") -> None:
        with connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO duplicate_results
                    (id, generated_at, destination_root, group_count, source_path, raw_json, dirty, dirty_reason, dirty_at, updated_at)
                VALUES (1, NULL, ?, 0, ?, '{}', 1, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    destination_root = excluded.destination_root,
                    dirty = 1,
                    dirty_reason = excluded.dirty_reason,
                    dirty_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (str(destination_root), str(self.database_path), reason),
            )
            connection.commit()

    def clear_dirty(self) -> None:
        with connect(self.database_path) as connection:
            connection.execute(
                """
                UPDATE duplicate_results
                SET dirty = 0,
                    dirty_reason = '',
                    dirty_at = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
                """
            )
            connection.commit()

    def _load_remaining_method_counts(self, connection: sqlite3.Connection) -> dict[str, int]:
        return {
            row["reason"]: row["count"]
            for row in connection.execute(
                """
                SELECT remaining.reason, COUNT(*) AS count
                FROM (
                    SELECT g.id, g.reason
                    FROM duplicate_groups g
                    JOIN duplicate_items i ON i.group_row_id = g.id
                    WHERE g.result_id = 1
                      AND i.file_exists = 1
                    GROUP BY g.id
                    HAVING COUNT(i.id) >= 2
                ) remaining
                GROUP BY remaining.reason
                """
            ).fetchall()
        }

    def _group_from_row(self, connection: sqlite3.Connection, group: sqlite3.Row) -> dict[str, Any]:
        items = [
            {
                "role": item["role"],
                "path": item["path"],
                "exists": bool(item["file_exists"]),
            }
            for item in connection.execute(
                """
                SELECT * FROM duplicate_items
                WHERE group_row_id = ?
                ORDER BY position, id
                """,
                (group["id"],),
            ).fetchall()
        ]
        return {
            "group_id": group["group_id"],
            "reason": group["reason"],
            "hash": group["hash"],
            "kept_path": group["kept_path"],
            "item_count": group["item_count"],
            "items": items,
        }
