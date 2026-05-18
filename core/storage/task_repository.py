# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.storage.database import connect, init_root_database


def build_source_fingerprint(file_name: str, size: int, strict_hash: str) -> str:
    return f"{file_name}|{size}|{strict_hash}"


class TaskRunRepository:
    def __init__(self, database_path: str | Path):
        self.database_path = init_root_database(database_path)

    def save_task_started(self, task: dict[str, Any]) -> None:
        params = task.get("params", {})
        if not isinstance(params, dict):
            params = {}
        outputs = task.get("outputs", {})
        if not isinstance(outputs, dict):
            outputs = {}

        task_type = str(task.get("task_type", "organizer"))
        source_root = str(params.get("src", "")).strip()
        destination_root = str(params.get("dst" if task_type == "organizer" else "root", "")).strip()

        with connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO task_runs
                    (
                        task_id, task_type, status, source_root, destination_root,
                        mode, duplicate_detection, phash_threshold, skip_existing_exact,
                        log_path, duplicate_report_path, error, started_at, finished_at, updated_at
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(task_id) DO UPDATE SET
                    task_type = excluded.task_type,
                    status = excluded.status,
                    source_root = excluded.source_root,
                    destination_root = excluded.destination_root,
                    mode = excluded.mode,
                    duplicate_detection = excluded.duplicate_detection,
                    phash_threshold = excluded.phash_threshold,
                    skip_existing_exact = excluded.skip_existing_exact,
                    log_path = excluded.log_path,
                    duplicate_report_path = excluded.duplicate_report_path,
                    error = excluded.error,
                    started_at = excluded.started_at,
                    finished_at = excluded.finished_at,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    str(task["task_id"]),
                    task_type,
                    str(task.get("status", "running")),
                    source_root,
                    destination_root,
                    str(params.get("mode", "copy")),
                    str(params.get("duplicate_detection", params.get("hash_method", "phash"))),
                    int(params.get("phash_threshold", 4) or 0),
                    1 if params.get("skip_existing_exact", True) is not False else 0,
                    str(outputs.get("log_path", "")),
                    str(outputs.get("duplicate_report_path", "")),
                    task.get("error"),
                    str(task.get("started_at", "")),
                    task.get("finished_at"),
                ),
            )
            connection.commit()

    def update_task_finished(
        self,
        task: dict[str, Any],
        *,
        scanned_count: int | None = None,
        saved_count: int | None = None,
        skipped_existing_count: int | None = None,
        skipped_existing_bytes: int | None = None,
        similar_group_count: int | None = None,
    ) -> None:
        updates = {
            "scanned_count": scanned_count,
            "saved_count": saved_count,
            "skipped_existing_count": skipped_existing_count,
            "skipped_existing_bytes": skipped_existing_bytes,
            "similar_group_count": similar_group_count,
        }
        with connect(self.database_path) as connection:
            connection.execute(
                """
                UPDATE task_runs
                SET status = ?,
                    error = ?,
                    finished_at = ?,
                    scanned_count = COALESCE(?, scanned_count),
                    saved_count = COALESCE(?, saved_count),
                    skipped_existing_count = COALESCE(?, skipped_existing_count),
                    skipped_existing_bytes = COALESCE(?, skipped_existing_bytes),
                    similar_group_count = COALESCE(?, similar_group_count),
                    updated_at = CURRENT_TIMESTAMP
                WHERE task_id = ?
                """,
                (
                    str(task.get("status", "")),
                    task.get("error"),
                    task.get("finished_at"),
                    updates["scanned_count"],
                    updates["saved_count"],
                    updates["skipped_existing_count"],
                    updates["skipped_existing_bytes"],
                    updates["similar_group_count"],
                    str(task["task_id"]),
                ),
            )
            connection.commit()

    def record_skipped_existing(
        self,
        *,
        task_id: str,
        source_path: str,
        existing_path: str,
        strict_hash: str,
        size: int,
        file_name: str = "",
        source_fingerprint: str = "",
    ) -> None:
        file_name = file_name or Path(source_path).name
        source_fingerprint = source_fingerprint or build_source_fingerprint(file_name, size, strict_hash)

        with connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO task_skipped_existing
                    (task_id, source_path, existing_path, strict_hash, file_name, size)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (task_id, source_path, existing_path, strict_hash, file_name, size),
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
                    source_path,
                    existing_path,
                    file_name,
                    size,
                    task_id,
                    task_id,
                ),
            )
            connection.commit()

    def load_task(self, task_id: str) -> dict[str, Any] | None:
        with connect(self.database_path) as connection:
            row = connection.execute("SELECT * FROM task_runs WHERE task_id = ?", (task_id,)).fetchone()
        return dict(row) if row is not None else None

    def list_skipped_existing(self, task_id: str) -> list[dict[str, Any]]:
        with connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT task_id, source_path, existing_path, strict_hash, file_name, size, recorded_at
                FROM task_skipped_existing
                WHERE task_id = ?
                ORDER BY id
                """,
                (task_id,),
            ).fetchall()
        return [dict(row) for row in rows]
