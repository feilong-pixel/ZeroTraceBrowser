# SPDX-License-Identifier: MIT

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from core.domain.root_context import RootContext

SCHEMA_VERSION = 2


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def root_database_path(root_context: RootContext) -> Path:
    return root_context.database_path


def connect(database_path: str | Path) -> sqlite3.Connection:
    database = Path(database_path)
    database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database, factory=ClosingConnection)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def transaction(connection: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def init_root_database(database_path: str | Path) -> Path:
    database = Path(database_path)
    with connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS duplicate_results (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at TEXT,
                destination_root TEXT NOT NULL DEFAULT '',
                group_count INTEGER NOT NULL DEFAULT 0,
                source_path TEXT NOT NULL DEFAULT '',
                raw_json TEXT NOT NULL DEFAULT '{}',
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

            CREATE TABLE IF NOT EXISTS image_indexes (
                cache_digest TEXT PRIMARY KEY,
                root TEXT NOT NULL,
                generated_at TEXT,
                timeline_generated_at TEXT,
                total INTEGER,
                duplicate_group_count INTEGER,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS image_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cache_digest TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                path TEXT NOT NULL DEFAULT '',
                name TEXT NOT NULL DEFAULT '',
                size INTEGER NOT NULL DEFAULT 0,
                captured_at TEXT NOT NULL DEFAULT '',
                modified_at TEXT NOT NULL DEFAULT '',
                timeline_time TEXT NOT NULL DEFAULT '',
                timeline_ts REAL,
                timeline_source TEXT NOT NULL DEFAULT '',
                file_exists INTEGER NOT NULL DEFAULT 1,
                hash TEXT,
                width INTEGER,
                height INTEGER,
                position INTEGER NOT NULL DEFAULT 0,
                raw_json TEXT NOT NULL DEFAULT '{}',
                UNIQUE(cache_digest, relative_path),
                FOREIGN KEY(cache_digest) REFERENCES image_indexes(cache_digest) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS timeline_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cache_digest TEXT NOT NULL,
                key TEXT NOT NULL,
                label TEXT NOT NULL,
                index_label TEXT NOT NULL,
                position INTEGER NOT NULL DEFAULT 0,
                UNIQUE(cache_digest, key),
                FOREIGN KEY(cache_digest) REFERENCES image_indexes(cache_digest) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS recycle_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                root TEXT NOT NULL DEFAULT '',
                relative_path TEXT NOT NULL DEFAULT '',
                deleted_to TEXT NOT NULL,
                action TEXT NOT NULL DEFAULT 'deleted',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(deleted_to)
            );

            CREATE TABLE IF NOT EXISTS hash_db_metadata (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                source_path TEXT NOT NULL DEFAULT '',
                raw_json TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS hash_db_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                method TEXT NOT NULL,
                hash TEXT NOT NULL,
                path TEXT NOT NULL,
                position INTEGER NOT NULL DEFAULT 0,
                UNIQUE(method, hash, path)
            );
            """
        )
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations(version) VALUES (?)",
            (SCHEMA_VERSION,),
        )
        existing_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(image_indexes)").fetchall()
        }
        if "timeline_generated_at" not in existing_columns:
            connection.execute("ALTER TABLE image_indexes ADD COLUMN timeline_generated_at TEXT")
        connection.commit()
    return database
