# SPDX-License-Identifier: MIT

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from core.domain.root_context import RootContext

SCHEMA_VERSION = 11


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
    connection = sqlite3.connect(database, timeout=5.0, factory=ClosingConnection)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
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

            CREATE INDEX IF NOT EXISTS idx_image_items_cache_position
                ON image_items(cache_digest, position, id);

            CREATE INDEX IF NOT EXISTS idx_image_items_cache_timeline
                ON image_items(cache_digest, timeline_time, position, id);

            CREATE INDEX IF NOT EXISTS idx_duplicate_items_path
                ON duplicate_items(path);

            CREATE INDEX IF NOT EXISTS idx_duplicate_items_group_exists
                ON duplicate_items(group_row_id, file_exists);

            CREATE INDEX IF NOT EXISTS idx_timeline_entries_cache_key
                ON timeline_entries(cache_digest, key DESC, id);

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

            CREATE TABLE IF NOT EXISTS file_hash_cache (
                path TEXT PRIMARY KEY,
                source_path TEXT NOT NULL DEFAULT '',
                file_name TEXT NOT NULL DEFAULT '',
                size INTEGER NOT NULL,
                mtime_ns INTEGER NOT NULL,
                strict_hash TEXT,
                phash TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_file_hash_cache_source_path
                ON file_hash_cache(source_path);

            CREATE INDEX IF NOT EXISTS idx_file_hash_cache_file_signature
                ON file_hash_cache(file_name, size, mtime_ns);

            CREATE TABLE IF NOT EXISTS task_runs (
                task_id TEXT PRIMARY KEY,
                task_type TEXT NOT NULL DEFAULT 'organizer',
                status TEXT NOT NULL DEFAULT 'running',
                source_root TEXT NOT NULL DEFAULT '',
                destination_root TEXT NOT NULL DEFAULT '',
                mode TEXT NOT NULL DEFAULT 'copy',
                duplicate_detection TEXT NOT NULL DEFAULT 'phash',
                phash_threshold INTEGER NOT NULL DEFAULT 4,
                skip_existing_exact INTEGER NOT NULL DEFAULT 1,
                scanned_count INTEGER NOT NULL DEFAULT 0,
                saved_count INTEGER NOT NULL DEFAULT 0,
                skipped_existing_count INTEGER NOT NULL DEFAULT 0,
                skipped_existing_bytes INTEGER NOT NULL DEFAULT 0,
                similar_group_count INTEGER NOT NULL DEFAULT 0,
                log_path TEXT NOT NULL DEFAULT '',
                duplicate_report_path TEXT NOT NULL DEFAULT '',
                error TEXT,
                started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                finished_at TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS task_skipped_existing (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                source_path TEXT NOT NULL,
                existing_path TEXT NOT NULL,
                strict_hash TEXT NOT NULL,
                file_name TEXT NOT NULL DEFAULT '',
                size INTEGER NOT NULL DEFAULT 0,
                recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(task_id) REFERENCES task_runs(task_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_task_skipped_existing_task_id
                ON task_skipped_existing(task_id);

            CREATE INDEX IF NOT EXISTS idx_task_skipped_existing_strict_hash
                ON task_skipped_existing(strict_hash);

            CREATE TABLE IF NOT EXISTS skipped_existing_index (
                strict_hash TEXT NOT NULL,
                source_fingerprint TEXT NOT NULL,
                source_path TEXT NOT NULL DEFAULT '',
                existing_path TEXT NOT NULL,
                file_name TEXT NOT NULL DEFAULT '',
                size INTEGER NOT NULL DEFAULT 0,
                first_task_id TEXT NOT NULL DEFAULT '',
                last_task_id TEXT NOT NULL DEFAULT '',
                first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                seen_count INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (strict_hash, source_fingerprint)
            );

            CREATE INDEX IF NOT EXISTS idx_skipped_existing_index_existing_path
                ON skipped_existing_index(existing_path);

            CREATE INDEX IF NOT EXISTS idx_skipped_existing_index_last_seen_at
                ON skipped_existing_index(last_seen_at);

            CREATE TABLE IF NOT EXISTS image_exif_cache (
                relative_path TEXT PRIMARY KEY,
                file_size INTEGER NOT NULL DEFAULT 0,
                mtime_ns INTEGER NOT NULL DEFAULT 0,
                raw_json TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS similarity_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                relative_path TEXT NOT NULL UNIQUE,
                absolute_path TEXT NOT NULL DEFAULT '',
                file_name TEXT NOT NULL DEFAULT '',
                size INTEGER NOT NULL DEFAULT 0,
                mtime_ns INTEGER NOT NULL DEFAULT 0,
                media_type TEXT NOT NULL DEFAULT 'image',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_similarity_files_signature
                ON similarity_files(relative_path, size, mtime_ns);

            CREATE TABLE IF NOT EXISTS similarity_features (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER NOT NULL,
                method TEXT NOT NULL,
                model TEXT NOT NULL DEFAULT '',
                version INTEGER NOT NULL DEFAULT 1,
                value_text TEXT NOT NULL DEFAULT '',
                value_blob BLOB,
                dimension INTEGER NOT NULL DEFAULT 0,
                keypoint_count INTEGER NOT NULL DEFAULT 0,
                detector TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(file_id, method, model, version),
                FOREIGN KEY(file_id) REFERENCES similarity_files(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_similarity_features_method
                ON similarity_features(method, model, version);

            CREATE TABLE IF NOT EXISTS mobile_devices (
                device_type TEXT NOT NULL DEFAULT 'iphone',
                device_id TEXT NOT NULL,
                name TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'mtp',
                dcim_available INTEGER NOT NULL DEFAULT 0,
                album_count INTEGER NOT NULL DEFAULT 0,
                media_count INTEGER NOT NULL DEFAULT 0,
                indexed_at TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(device_type, device_id)
            );

            CREATE TABLE IF NOT EXISTS mobile_photo_index (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_type TEXT NOT NULL DEFAULT 'iphone',
                device_id TEXT NOT NULL,
                album TEXT NOT NULL DEFAULT '',
                filename TEXT NOT NULL,
                size INTEGER NOT NULL DEFAULT 0,
                modified_at TEXT NOT NULL DEFAULT '',
                strict_hash TEXT NOT NULL DEFAULT '',
                phash TEXT NOT NULL DEFAULT '',
                indexed_at TEXT NOT NULL DEFAULT '',
                raw_json TEXT NOT NULL DEFAULT '{}',
                UNIQUE(device_type, device_id, album, filename),
                FOREIGN KEY(device_type, device_id) REFERENCES mobile_devices(device_type, device_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS mobile_import_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_type TEXT NOT NULL DEFAULT 'iphone',
                device_id TEXT NOT NULL,
                device_name TEXT NOT NULL DEFAULT '',
                album TEXT NOT NULL DEFAULT '',
                filename TEXT NOT NULL,
                mobile_ref TEXT NOT NULL DEFAULT '',
                size INTEGER NOT NULL DEFAULT 0,
                modified_at TEXT NOT NULL DEFAULT '',
                strict_hash TEXT NOT NULL DEFAULT '',
                phash TEXT NOT NULL DEFAULT '',
                save_state TEXT NOT NULL DEFAULT 'device_only'
                    CHECK(save_state IN ('device_only', 'local_only', 'both')),
                import_status TEXT NOT NULL DEFAULT 'indexed',
                local_path TEXT NOT NULL DEFAULT '',
                existing_local_path TEXT NOT NULL DEFAULT '',
                deleted_from_device_at TEXT NOT NULL DEFAULT '',
                indexed_at TEXT NOT NULL DEFAULT '',
                imported_at TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                raw_json TEXT NOT NULL DEFAULT '{}',
                UNIQUE(device_type, device_id, album, filename),
                FOREIGN KEY(device_type, device_id) REFERENCES mobile_devices(device_type, device_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_mobile_import_records_device_state
                ON mobile_import_records(device_type, device_id, save_state);

            CREATE INDEX IF NOT EXISTS idx_mobile_import_records_strict_hash
                ON mobile_import_records(strict_hash);

            CREATE INDEX IF NOT EXISTS idx_mobile_import_records_phash
                ON mobile_import_records(phash);

            CREATE TABLE IF NOT EXISTS mobile_pairings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id TEXT NOT NULL,
                root_id TEXT NOT NULL,
                device_type TEXT NOT NULL DEFAULT 'iphone',
                device_id TEXT NOT NULL,
                device_name TEXT NOT NULL DEFAULT '',
                device_model TEXT NOT NULL DEFAULT '',
                platform TEXT NOT NULL DEFAULT '',
                app_id TEXT NOT NULL DEFAULT '',
                app_version TEXT NOT NULL DEFAULT '',
                owner_label TEXT NOT NULL DEFAULT '',
                destination_root TEXT NOT NULL DEFAULT '',
                pairing_status TEXT NOT NULL DEFAULT 'paired',
                sync_token_hash TEXT NOT NULL DEFAULT '',
                token_expires_at TEXT NOT NULL DEFAULT '',
                paired_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                capabilities_json TEXT NOT NULL DEFAULT '{}',
                raw_json TEXT NOT NULL DEFAULT '{}',
                UNIQUE(server_id, root_id, device_type, device_id)
            );

            CREATE INDEX IF NOT EXISTS idx_mobile_pairings_device
                ON mobile_pairings(device_type, device_id);

            CREATE TABLE IF NOT EXISTS mobile_sync_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL UNIQUE,
                server_id TEXT NOT NULL,
                root_id TEXT NOT NULL,
                device_type TEXT NOT NULL DEFAULT 'iphone',
                device_id TEXT NOT NULL,
                destination_root TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'ready',
                sync_token_hash TEXT NOT NULL DEFAULT '',
                token_expires_at TEXT NOT NULL DEFAULT '',
                client_cursor TEXT NOT NULL DEFAULT '',
                server_cursor TEXT NOT NULL DEFAULT '',
                battery_state TEXT NOT NULL DEFAULT '',
                network_type TEXT NOT NULL DEFAULT '',
                started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                finished_at TEXT NOT NULL DEFAULT '',
                raw_json TEXT NOT NULL DEFAULT '{}'
            );

            CREATE INDEX IF NOT EXISTS idx_mobile_sync_sessions_device
                ON mobile_sync_sessions(server_id, root_id, device_type, device_id);

            CREATE TABLE IF NOT EXISTS import_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL UNIQUE,
                channel TEXT NOT NULL DEFAULT 'phone_sync',
                server_id TEXT NOT NULL DEFAULT '',
                root_id TEXT NOT NULL DEFAULT '',
                source_label TEXT NOT NULL DEFAULT '',
                device_type TEXT NOT NULL DEFAULT 'iphone',
                device_id TEXT NOT NULL DEFAULT '',
                destination_root TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'running',
                started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                finished_at TEXT NOT NULL DEFAULT '',
                raw_json TEXT NOT NULL DEFAULT '{}'
            );

            CREATE INDEX IF NOT EXISTS idx_import_runs_device
                ON import_runs(server_id, root_id, device_type, device_id);

            CREATE TABLE IF NOT EXISTS import_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL DEFAULT '',
                session_id TEXT NOT NULL DEFAULT '',
                upload_batch_id TEXT NOT NULL DEFAULT '',
                source_ref TEXT NOT NULL DEFAULT '',
                server_id TEXT NOT NULL DEFAULT '',
                root_id TEXT NOT NULL DEFAULT '',
                device_type TEXT NOT NULL DEFAULT 'iphone',
                device_id TEXT NOT NULL DEFAULT '',
                item_id TEXT NOT NULL DEFAULT '',
                original_filename TEXT NOT NULL DEFAULT '',
                media_type TEXT NOT NULL DEFAULT '',
                mime_type TEXT NOT NULL DEFAULT '',
                size INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT '',
                modified_at TEXT NOT NULL DEFAULT '',
                timezone TEXT NOT NULL DEFAULT '',
                album TEXT NOT NULL DEFAULT '',
                width INTEGER NOT NULL DEFAULT 0,
                height INTEGER NOT NULL DEFAULT 0,
                duration_ms INTEGER NOT NULL DEFAULT 0,
                strict_hash TEXT NOT NULL DEFAULT '',
                phash TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'manifested',
                local_path TEXT NOT NULL DEFAULT '',
                existing_local_path TEXT NOT NULL DEFAULT '',
                error TEXT NOT NULL DEFAULT '',
                manifest_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                imported_at TEXT NOT NULL DEFAULT '',
                raw_json TEXT NOT NULL DEFAULT '{}',
                UNIQUE(server_id, root_id, device_type, device_id, item_id)
            );

            CREATE INDEX IF NOT EXISTS idx_import_items_session
                ON import_items(session_id, upload_batch_id);

            CREATE INDEX IF NOT EXISTS idx_import_items_hash
                ON import_items(strict_hash);

            CREATE TABLE IF NOT EXISTS local_deleted_markers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strict_hash TEXT NOT NULL,
                relative_path TEXT NOT NULL DEFAULT '',
                original_path TEXT NOT NULL DEFAULT '',
                deleted_to TEXT NOT NULL DEFAULT '',
                delete_source TEXT NOT NULL DEFAULT 'local_gallery',
                deleted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                raw_json TEXT NOT NULL DEFAULT '{}',
                UNIQUE(strict_hash, delete_source)
            );

            CREATE INDEX IF NOT EXISTS idx_local_deleted_markers_strict_hash
                ON local_deleted_markers(strict_hash);
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
        duplicate_result_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(duplicate_results)").fetchall()
        }
        if "dirty" not in duplicate_result_columns:
            connection.execute("ALTER TABLE duplicate_results ADD COLUMN dirty INTEGER NOT NULL DEFAULT 0")
        if "dirty_reason" not in duplicate_result_columns:
            connection.execute("ALTER TABLE duplicate_results ADD COLUMN dirty_reason TEXT NOT NULL DEFAULT ''")
        if "dirty_at" not in duplicate_result_columns:
            connection.execute("ALTER TABLE duplicate_results ADD COLUMN dirty_at TEXT")
        connection.commit()
    return database
