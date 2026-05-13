# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.storage.database import connect, init_root_database


class ImageIndexRepository:
    def __init__(self, database_path: str | Path):
        self.database_path = init_root_database(database_path)

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
                    total = excluded.total,
                    duplicate_group_count = excluded.duplicate_group_count,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (cache_digest, root, generated_at, generated_at if timeline_entries is not None else None, total, duplicate_group_count),
            )
            connection.execute("DELETE FROM image_items WHERE cache_digest = ?", (cache_digest,))
            for position, item in enumerate(items):
                if not isinstance(item, dict) or not item.get("relative_path"):
                    continue
                connection.execute(
                    """
                    INSERT INTO image_items
                        (
                            cache_digest, relative_path, path, name, size, captured_at,
                            modified_at, timeline_time, timeline_ts, timeline_source,
                            file_exists, hash, width, height, position, raw_json
                        )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cache_digest,
                        str(item["relative_path"]),
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

            connection.execute("DELETE FROM timeline_entries WHERE cache_digest = ?", (cache_digest,))
            for position, entry in enumerate(timeline_entries or []):
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

    def load_metadata(self, cache_digest: str) -> dict[str, Any] | None:
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

    def list_images(self, cache_digest: str, *, offset: int = 0, limit: int | None = None) -> list[dict[str, Any]]:
        query = """
            SELECT * FROM image_items
            WHERE cache_digest = ?
            ORDER BY position, id
        """
        params: list[Any] = [cache_digest]
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
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

    def load_timeline_entries(self, cache_digest: str) -> list[dict[str, str]]:
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
                    ORDER BY position, id
                    """,
                    (cache_digest,),
                ).fetchall()
            ]

    def replace_timeline_entries(
        self,
        cache_digest: str,
        *,
        root: str,
        entries: list[dict[str, str]],
        generated_at: str,
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
            connection.execute("DELETE FROM timeline_entries WHERE cache_digest = ?", (cache_digest,))
            for position, entry in enumerate(entries):
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
