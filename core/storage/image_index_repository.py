# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from core.storage.database import connect, init_root_database


class ImageIndexRepository:
    def __init__(self, database_path: str | Path, *, ensure_schema: bool = True):
        self.database_path = init_root_database(database_path) if ensure_schema else Path(database_path)

    def save_index(
        self,
        cache_digest: str,
        *,
        root: str,
        items: list[dict[str, Any]],
        total: int | None = None,
        generated_at: str | None = None,
        duplicate_group_count: int | None = None,
        timeline_entries: list[dict[str, str]] | None = None,
        delete_missing_items: bool = True,
    ) -> None:
        init_root_database(self.database_path)
        with connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO image_indexes
                    (cache_digest, root, generated_at, timeline_generated_at, total, duplicate_group_count, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(cache_digest) DO UPDATE SET
                    root = excluded.root,
                    generated_at = excluded.generated_at,
                    timeline_generated_at = COALESCE(excluded.timeline_generated_at, image_indexes.timeline_generated_at),
                    total = COALESCE(excluded.total, image_indexes.total),
                    duplicate_group_count = COALESCE(excluded.duplicate_group_count, image_indexes.duplicate_group_count),
                    updated_at = CURRENT_TIMESTAMP
                """,
                (cache_digest, root, generated_at, generated_at if timeline_entries is not None else None, total, duplicate_group_count),
            )
            current_paths: set[str] = set()
            for position, item in enumerate(items):
                if not isinstance(item, dict) or not item.get("relative_path"):
                    continue
                relative_path = str(item["relative_path"])
                current_paths.add(relative_path)
                connection.execute(
                    """
                    INSERT INTO image_items
                        (
                            cache_digest, relative_path, path, name, size, captured_at,
                            modified_at, timeline_time, timeline_ts, timeline_source,
                            file_exists, hash, width, height, position, raw_json
                        )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(cache_digest, relative_path) DO UPDATE SET
                        path = excluded.path,
                        name = excluded.name,
                        size = excluded.size,
                        captured_at = excluded.captured_at,
                        modified_at = excluded.modified_at,
                        timeline_time = excluded.timeline_time,
                        timeline_ts = excluded.timeline_ts,
                        timeline_source = excluded.timeline_source,
                        file_exists = excluded.file_exists,
                        hash = excluded.hash,
                        width = excluded.width,
                        height = excluded.height,
                        position = excluded.position,
                        raw_json = excluded.raw_json
                    """,
                    (
                        cache_digest,
                        relative_path,
                        str(item.get("path") or item["relative_path"]),
                        str(item.get("name", "")),
                        int(item.get("size", 0) or 0),
                        str(item.get("captured_at", "")),
                        str(item.get("modified_at", "")),
                        str(item.get("timeline_time", "")),
                        item.get("timeline_ts") if isinstance(item.get("timeline_ts"), int | float) else None,
                        str(item.get("timeline_source", "")),
                        1 if bool(item.get("exists", True)) else 0,
                        str(item["hash"]) if item.get("hash") else None,
                        int(item["width"]) if item.get("width") else None,
                        int(item["height"]) if item.get("height") else None,
                        position,
                        json.dumps(item, ensure_ascii=False),
                    ),
                )
            if current_paths and delete_missing_items:
                placeholders = ",".join("?" for _ in current_paths)
                connection.execute(
                    f"""
                    DELETE FROM image_items
                    WHERE cache_digest = ?
                      AND relative_path NOT IN ({placeholders})
                    """,
                    (cache_digest, *sorted(current_paths)),
                )
            elif not current_paths and delete_missing_items:
                connection.execute("DELETE FROM image_items WHERE cache_digest = ?", (cache_digest,))

            if timeline_entries is not None:
                connection.execute("DELETE FROM timeline_entries WHERE cache_digest = ?", (cache_digest,))
                for position, entry in enumerate(timeline_entries):
                    if not isinstance(entry, dict) or not entry.get("key"):
                        continue
                    connection.execute(
                        """
                        INSERT INTO timeline_entries
                            (cache_digest, key, label, index_label, position)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            cache_digest,
                            str(entry.get("key", "")),
                            str(entry.get("label", "")),
                            str(entry.get("index_label", "")),
                            position,
                        ),
                    )
            connection.commit()

    def load_summary(self, cache_digest: str) -> dict[str, Any] | None:
        if not self.database_path.exists():
            return None
        try:
            with connect(self.database_path) as connection:
                row = connection.execute(
                    "SELECT * FROM image_indexes WHERE cache_digest = ?",
                    (cache_digest,),
                ).fetchone()
                if row is None:
                    return None
                preview_items = self.list_images(cache_digest, limit=240)
                return {
                    "generated_at": row["generated_at"],
                    "timeline_generated_at": row["timeline_generated_at"],
                    "root": row["root"],
                    "total": row["total"],
                    "duplicate_group_count": row["duplicate_group_count"],
                    "items": preview_items,
                }
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
            return None

    def load_metadata(self, cache_digest: str) -> dict[str, Any] | None:
        if not self.database_path.exists():
            return None
        try:
            with connect(self.database_path) as connection:
                row = connection.execute(
                    "SELECT * FROM image_indexes WHERE cache_digest = ?",
                    (cache_digest,),
                ).fetchone()
                if row is None:
                    return None
                return {
                    "generated_at": row["generated_at"],
                    "timeline_generated_at": row["timeline_generated_at"],
                    "root": row["root"],
                    "total": row["total"],
                    "duplicate_group_count": row["duplicate_group_count"],
                }
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
            return None

    def list_images(self, cache_digest: str, *, offset: int = 0, limit: int | None = None) -> list[dict[str, Any]]:
        if not self.database_path.exists():
            return []
        query = """
            SELECT * FROM image_items
            WHERE cache_digest = ?
            ORDER BY position, id
        """
        params: list[Any] = [cache_digest]
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        try:
            with connect(self.database_path) as connection:
                return [
                    {
                        "relative_path": row["relative_path"],
                        "path": row["path"],
                        "name": row["name"],
                        "size": row["size"],
                        "captured_at": row["captured_at"],
                        "modified_at": row["modified_at"],
                        "timeline_time": row["timeline_time"],
                        "timeline_ts": row["timeline_ts"],
                        "timeline_source": row["timeline_source"],
                        "exists": bool(row["file_exists"]),
                        "hash": row["hash"],
                        "width": row["width"],
                        "height": row["height"],
                    }
                    for row in connection.execute(query, params).fetchall()
                ]
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
            return []

    def load_timeline_entries(self, cache_digest: str) -> list[dict[str, str]]:
        if not self.database_path.exists():
            return []
        try:
            with connect(self.database_path) as connection:
                return [
                    {
                        "key": row["key"],
                        "label": row["label"],
                        "index_label": row["index_label"],
                    }
                    for row in connection.execute(
                        """
                        SELECT * FROM timeline_entries
                        WHERE cache_digest = ?
                        ORDER BY
                            CASE WHEN key = 'unknown' THEN 1 ELSE 0 END,
                            key DESC,
                            id
                        """,
                        (cache_digest,),
                    ).fetchall()
                ]
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
            return []

    def delete_index(self, cache_digest: str) -> None:
        with connect(self.database_path) as connection:
            connection.execute("DELETE FROM timeline_entries WHERE cache_digest = ?", (cache_digest,))
            connection.execute("DELETE FROM image_items WHERE cache_digest = ?", (cache_digest,))
            connection.execute("DELETE FROM image_indexes WHERE cache_digest = ?", (cache_digest,))
            connection.commit()

    def clear_image_items(self, cache_digest: str) -> None:
        with connect(self.database_path) as connection:
            connection.execute("DELETE FROM image_items WHERE cache_digest = ?", (cache_digest,))
            connection.commit()

    def replace_timeline_entries(
        self,
        cache_digest: str,
        *,
        root: str,
        entries: list[dict[str, str]],
        generated_at: str,
        delete_missing: bool = True,
    ) -> None:
        init_root_database(self.database_path)
        with connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO image_indexes
                    (cache_digest, root, generated_at, timeline_generated_at, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(cache_digest) DO UPDATE SET
                    root = excluded.root,
                    timeline_generated_at = excluded.timeline_generated_at,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (cache_digest, root, generated_at, generated_at),
            )
            current_keys: set[str] = set()
            for position, entry in enumerate(entries):
                if not isinstance(entry, dict) or not entry.get("key"):
                    continue
                key = str(entry.get("key", ""))
                current_keys.add(key)
                connection.execute(
                    """
                    INSERT INTO timeline_entries
                        (cache_digest, key, label, index_label, position)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(cache_digest, key) DO UPDATE SET
                        label = excluded.label,
                        index_label = excluded.index_label,
                        position = excluded.position
                    """,
                    (
                        cache_digest,
                        key,
                        str(entry.get("label", "")),
                        str(entry.get("index_label", "")),
                        position,
                    ),
                )
            if current_keys and delete_missing:
                placeholders = ",".join("?" for _ in current_keys)
                connection.execute(
                    f"""
                    DELETE FROM timeline_entries
                    WHERE cache_digest = ?
                      AND key NOT IN ({placeholders})
                    """,
                    (cache_digest, *sorted(current_keys)),
                )
            elif not current_keys and delete_missing:
                connection.execute("DELETE FROM timeline_entries WHERE cache_digest = ?", (cache_digest,))
            connection.commit()
