# SPDX-License-Identifier: MIT

import json
import os
import sqlite3


DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "hash_db.json"
)


def get_db_path() -> str:
    return os.environ.get("IMAGE_ORGANIZER_HASH_DB", DEFAULT_DB_PATH)


def get_sqlite_db_path() -> str:
    return os.environ.get("IMAGE_ORGANIZER_HASH_DB_SQLITE", "")


def connect_sqlite_hash_db() -> sqlite3.Connection:
    db_path = get_sqlite_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
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
        """
    )
    return connection


def load_file_hash_cache_entry(path: str, size: int, mtime_ns: int) -> dict[str, str] | None:
    if not get_sqlite_db_path().strip():
        return None

    with connect_sqlite_hash_db() as connection:
        row = connection.execute(
            """
            SELECT strict_hash, phash
            FROM file_hash_cache
            WHERE path = ? AND size = ? AND mtime_ns = ?
            """,
            (os.path.abspath(path), size, mtime_ns),
        ).fetchone()

    if row is None:
        return None

    return {
        "strict": row["strict_hash"] or "",
        "phash": row["phash"] or "",
    }


def upsert_file_hash_cache(
    path: str,
    *,
    size: int,
    mtime_ns: int,
    strict_hash: str | None = None,
    phash: str | None = None,
    source_path: str = "",
) -> None:
    if not get_sqlite_db_path().strip():
        return

    path_abs = os.path.abspath(path)
    source_abs = os.path.abspath(source_path) if source_path else ""
    file_name = os.path.basename(path_abs)
    with connect_sqlite_hash_db() as connection:
        connection.execute(
            """
            INSERT INTO file_hash_cache
                (path, source_path, file_name, size, mtime_ns, strict_hash, phash, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(path) DO UPDATE SET
                source_path = excluded.source_path,
                file_name = excluded.file_name,
                size = excluded.size,
                mtime_ns = excluded.mtime_ns,
                strict_hash = COALESCE(
                    excluded.strict_hash,
                    CASE
                        WHEN file_hash_cache.size = excluded.size
                         AND file_hash_cache.mtime_ns = excluded.mtime_ns
                        THEN file_hash_cache.strict_hash
                    END
                ),
                phash = COALESCE(
                    excluded.phash,
                    CASE
                        WHEN file_hash_cache.size = excluded.size
                         AND file_hash_cache.mtime_ns = excluded.mtime_ns
                        THEN file_hash_cache.phash
                    END
                ),
                updated_at = CURRENT_TIMESTAMP
            """,
            (path_abs, source_abs, file_name, size, mtime_ns, strict_hash, phash),
        )
        connection.commit()


def insert_hash_record(method: str, hash_value: str, path: str) -> None:
    if not get_sqlite_db_path().strip():
        return

    with connect_sqlite_hash_db() as connection:
        row = connection.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 FROM hash_db_records WHERE method = ? AND hash = ?",
            (method, hash_value),
        ).fetchone()
        position = int(row[0] or 0)
        connection.execute(
            """
            INSERT OR IGNORE INTO hash_db_records
                (method, hash, path, position)
            VALUES (?, ?, ?, ?)
            """,
            (method, hash_value, path, position),
        )
        connection.commit()


def record_skipped_existing(
    task_id: str,
    source_path: str,
    existing_path: str,
    strict_hash: str,
    size: int,
) -> None:
    if not get_sqlite_db_path().strip() or not task_id:
        return

    source_abs = os.path.abspath(source_path)
    existing_abs = os.path.abspath(existing_path)
    file_name = os.path.basename(source_abs)
    source_fingerprint = f"{file_name}|{size}|{strict_hash}"
    with connect_sqlite_hash_db() as connection:
        connection.execute(
            """
            INSERT INTO task_skipped_existing
                (task_id, source_path, existing_path, strict_hash, file_name, size)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (task_id, source_abs, existing_abs, strict_hash, file_name, size),
        )
        connection.execute(
            """
            INSERT INTO skipped_existing_index
                (
                    strict_hash, source_fingerprint, source_path, existing_path,
                    file_name, size, first_task_id, last_task_id
                )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(strict_hash, source_fingerprint) DO UPDATE SET
                source_path = excluded.source_path,
                existing_path = excluded.existing_path,
                file_name = excluded.file_name,
                size = excluded.size,
                last_task_id = excluded.last_task_id,
                last_seen_at = CURRENT_TIMESTAMP,
                seen_count = seen_count + 1
            """,
            (
                strict_hash,
                source_fingerprint,
                source_abs,
                existing_abs,
                file_name,
                size,
                task_id,
                task_id,
            ),
        )
        connection.commit()


def update_task_run_counts(
    task_id: str,
    *,
    scanned_count: int,
    saved_count: int,
    skipped_existing_count: int,
    skipped_existing_bytes: int,
    similar_group_count: int,
) -> None:
    if not get_sqlite_db_path().strip() or not task_id:
        return

    with connect_sqlite_hash_db() as connection:
        connection.execute(
            """
            UPDATE task_runs
            SET scanned_count = ?,
                saved_count = ?,
                skipped_existing_count = ?,
                skipped_existing_bytes = ?,
                similar_group_count = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE task_id = ?
            """,
            (
                scanned_count,
                saved_count,
                skipped_existing_count,
                skipped_existing_bytes,
                similar_group_count,
                task_id,
            ),
        )
        connection.commit()


def clear_sqlite_hash_records() -> None:
    if not get_sqlite_db_path().strip():
        return

    with connect_sqlite_hash_db() as connection:
        connection.execute("DELETE FROM hash_db_metadata WHERE id = 1")
        connection.execute("DELETE FROM hash_db_records")
        connection.commit()


def _normalize_db(db: dict) -> dict[str, dict[str, list[str]]]:
    # Upgrade the legacy flat structure into per-method buckets.
    if "phash" in db or "strict" in db:
        return {
            "phash": db.get("phash", {}),
            "strict": db.get("strict", {}),
        }

    return {
        "phash": db,
        "strict": {},
    }


def load_hash_db() -> dict[str, dict[str, list[str]]]:
    # Load the persisted hash database and remove missing file references.
    if get_sqlite_db_path().strip():
        with connect_sqlite_hash_db() as connection:
            rows = connection.execute(
                """
                SELECT method, hash, path
                FROM hash_db_records
                ORDER BY method, hash, position, id
                """
            ).fetchall()
        db: dict[str, dict[str, list[str]]] = {"phash": {}, "strict": {}}
        for row in rows:
            method = row["method"]
            db.setdefault(method, {})
            db[method].setdefault(row["hash"], []).append(row["path"])
        return clean_hash_db(db)

    db_path = get_db_path()
    if not os.path.exists(db_path):
        return {"phash": {}, "strict": {}}

    try:
        with open(db_path, "r", encoding="utf-8") as file_obj:
            db = json.load(file_obj)
    except Exception:
        return {"phash": {}, "strict": {}}

    return clean_hash_db(_normalize_db(db))


def save_hash_db(db: dict[str, dict[str, list[str]]]) -> None:
    # Persist the cleaned database to disk.
    db = clean_hash_db(db)
    if get_sqlite_db_path().strip():
        with connect_sqlite_hash_db() as connection:
            connection.execute(
                """
                INSERT INTO hash_db_metadata (id, source_path, raw_json, updated_at)
                VALUES (1, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    source_path = excluded.source_path,
                    raw_json = excluded.raw_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (get_sqlite_db_path(), json.dumps(db, ensure_ascii=False)),
            )
            connection.execute("DELETE FROM hash_db_records")
            for method, records in db.items():
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
        return

    db_path = get_db_path()

    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with open(db_path, "w", encoding="utf-8") as file_obj:
        json.dump(db, file_obj, indent=2, ensure_ascii=False)


def clean_hash_db(db: dict[str, dict[str, list[str]]]) -> dict[str, dict[str, list[str]]]:
    # Drop entries whose recorded files no longer exist.
    cleaned = {"phash": {}, "strict": {}}

    for method, records in db.items():
        method_records = {}
        for hash_value, paths in records.items():
            valid_paths = [path for path in paths if os.path.exists(path)]
            if valid_paths:
                method_records[hash_value] = valid_paths
        cleaned[method] = method_records

    return cleaned


def add_hash_record(db: dict[str, dict[str, list[str]]], method: str, hash_value: str, path: str) -> None:
    # Record a file path under the selected duplicate detection method.
    db.setdefault(method, {})
    db[method].setdefault(hash_value, [])

    if path not in db[method][hash_value]:
        db[method][hash_value].append(path)

    insert_hash_record(method, hash_value, path)


def create_empty_hash_db() -> dict[str, dict[str, list[str]]]:
    return {"phash": {}, "strict": {}}


def is_path_within_root(path: str, root_dir: str) -> bool:
    path_abs = os.path.abspath(path)
    root_abs = os.path.abspath(root_dir)

    path_drive = os.path.splitdrive(path_abs)[0].lower()
    root_drive = os.path.splitdrive(root_abs)[0].lower()
    if path_drive != root_drive:
        return False

    return os.path.commonpath([path_abs, root_abs]) == root_abs


def get_valid_original_paths(
    db: dict[str, dict[str, list[str]]],
    method: str,
    hash_value: str,
    dst_root: str,
    threshold: int = 0,
) -> list[str]:
    """
    Return matching files recorded under the current destination root only.

    The hash database is used as a hint, not as authority to redirect files
    outside the destination requested by the current run.
    """
    records = db.get(method, {})
    matches: list[str] = []

    if method == "strict":
        for path in records.get(hash_value, []):
            if os.path.exists(path) and is_path_within_root(path, dst_root):
                matches.append(path)
        return matches

    if method == "phash":
        from .duplicate_detector import phash_distance

        for recorded_hash, paths in records.items():
            if phash_distance(recorded_hash, hash_value) > threshold:
                continue

            for path in paths:
                if os.path.exists(path) and is_path_within_root(path, dst_root):
                    matches.append(path)

    return matches
