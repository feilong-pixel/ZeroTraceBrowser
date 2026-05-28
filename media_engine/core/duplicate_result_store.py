# SPDX-License-Identifier: MIT

import json
import os
import sqlite3


def load_duplicate_payload_sqlite(db_path: str) -> dict | None:
    try:
        with sqlite3.connect(db_path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute("SELECT raw_json FROM duplicate_results WHERE id = 1").fetchone()
        if row is None:
            return None
        payload = json.loads(row["raw_json"])
    except (OSError, json.JSONDecodeError, sqlite3.Error):
        return None

    return payload if isinstance(payload, dict) else None


def save_duplicate_payload_sqlite(db_path: str, payload: dict) -> None:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        _ensure_duplicate_result_schema(connection)
        groups = payload.get("groups", [])
        if not isinstance(groups, list):
            groups = []
        group_count = payload.get("group_count")
        if not isinstance(group_count, int):
            group_count = len(groups)
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
                db_path,
                json.dumps(payload, ensure_ascii=False),
            ),
        )
        connection.execute("DELETE FROM duplicate_groups WHERE result_id = 1")
        connection.execute(
            """
            DELETE FROM duplicate_items
            WHERE group_row_id NOT IN (SELECT id FROM duplicate_groups)
            """
        )
        _insert_duplicate_groups(connection, groups)
        connection.commit()


def _ensure_duplicate_result_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS duplicate_results (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            generated_at TEXT,
            destination_root TEXT NOT NULL DEFAULT '',
            group_count INTEGER NOT NULL DEFAULT 0,
            source_path TEXT NOT NULL DEFAULT '',
            raw_json TEXT NOT NULL DEFAULT '{}',
            dirty INTEGER NOT NULL DEFAULT 0,
            dirty_reason TEXT NOT NULL DEFAULT '',
            dirty_at TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS duplicate_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            result_id INTEGER NOT NULL DEFAULT 1,
            group_id TEXT NOT NULL,
            reason TEXT NOT NULL DEFAULT '-',
            hash TEXT NOT NULL DEFAULT '',
            kept_path TEXT NOT NULL DEFAULT '',
            item_count INTEGER NOT NULL DEFAULT 0,
            position INTEGER NOT NULL DEFAULT 0,
            raw_json TEXT NOT NULL DEFAULT '{}',
            UNIQUE(result_id, group_id),
            FOREIGN KEY(result_id) REFERENCES duplicate_results(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS duplicate_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_row_id INTEGER NOT NULL,
            role TEXT NOT NULL DEFAULT '',
            path TEXT NOT NULL,
            file_exists INTEGER NOT NULL DEFAULT 1,
            position INTEGER NOT NULL DEFAULT 0,
            raw_json TEXT NOT NULL DEFAULT '{}',
            UNIQUE(group_row_id, path, role, position),
            FOREIGN KEY(group_row_id) REFERENCES duplicate_groups(id) ON DELETE CASCADE
        );
        """
    )
    duplicate_result_columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(duplicate_results)").fetchall()
    }
    if "dirty" not in duplicate_result_columns:
        connection.execute("ALTER TABLE duplicate_results ADD COLUMN dirty INTEGER NOT NULL DEFAULT 0")
    if "dirty_reason" not in duplicate_result_columns:
        connection.execute("ALTER TABLE duplicate_results ADD COLUMN dirty_reason TEXT NOT NULL DEFAULT ''")
    if "dirty_at" not in duplicate_result_columns:
        connection.execute("ALTER TABLE duplicate_results ADD COLUMN dirty_at TEXT")


def _insert_duplicate_groups(connection: sqlite3.Connection, groups: list) -> None:
    for group_position, group in enumerate(groups):
        if not isinstance(group, dict):
            continue
        items = group.get("items", [])
        if not isinstance(items, list):
            items = []
        cursor = connection.execute(
            """
            INSERT INTO duplicate_groups
                (result_id, group_id, reason, hash, kept_path, item_count, position, raw_json)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(group.get("group_id") or f"group_{group_position:06d}"),
                str(group.get("reason", "-")),
                str(group.get("hash", "")),
                str(group.get("kept_path", "")),
                len(items),
                group_position,
                json.dumps(group, ensure_ascii=False),
            ),
        )
        group_row_id = cursor.lastrowid
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
                    1,
                    item_position,
                    json.dumps(item, ensure_ascii=False),
                ),
            )
