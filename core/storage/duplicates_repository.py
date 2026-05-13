# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.storage.database import connect, init_root_database


class DuplicateResultRepository:
    def __init__(self, database_path: str | Path):
        self.database_path = init_root_database(database_path)

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
                    (id, generated_at, destination_root, group_count, source_path, raw_json, updated_at)
                VALUES (1, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    generated_at = excluded.generated_at,
                    destination_root = excluded.destination_root,
                    group_count = excluded.group_count,
                    source_path = excluded.source_path,
                    raw_json = excluded.raw_json,
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
                "groups": groups,
            }

    def load_summary(self) -> dict[str, Any]:
        with connect(self.database_path) as connection:
            result = connection.execute(
                "SELECT generated_at, destination_root, group_count, source_path FROM duplicate_results WHERE id = 1"
            ).fetchone()
            if result is None:
                return {"available": False, "group_count": 0}
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
            return {
                "available": True,
                "generated_at": result["generated_at"],
                "destination_root": result["destination_root"],
                "group_count": result["group_count"],
                "source_path": result["source_path"],
                "method_counts": method_counts,
            }

    def clear_result(self) -> None:
        with connect(self.database_path) as connection:
            connection.execute("DELETE FROM duplicate_results WHERE id = 1")
            connection.commit()
