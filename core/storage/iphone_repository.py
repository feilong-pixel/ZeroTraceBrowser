# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.storage.database import connect, init_root_database


class IphoneRepository:
    def __init__(self, database_path: str | Path):
        self.database_path = init_root_database(database_path)

    def save_index(
        self,
        *,
        device_id: str,
        device_name: str,
        indexed_at: str,
        records: list[dict[str, Any]],
    ) -> None:
        albums = {str(item.get("album", "")) for item in records if str(item.get("album", "")).strip()}
        with connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO iphone_devices (
                    device_id, name, kind, dcim_available, album_count, media_count, indexed_at
                ) VALUES (?, ?, 'mtp', 1, ?, ?, ?)
                ON CONFLICT(device_id) DO UPDATE SET
                    name = excluded.name,
                    dcim_available = excluded.dcim_available,
                    album_count = excluded.album_count,
                    media_count = excluded.media_count,
                    indexed_at = excluded.indexed_at,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (device_id, device_name, len(albums), len(records), indexed_at),
            )
            connection.execute("DELETE FROM iphone_photo_index WHERE device_id = ?", (device_id,))
            connection.executemany(
                """
                INSERT OR REPLACE INTO iphone_photo_index (
                    device_id, album, filename, size, modified_at, strict_hash, phash, indexed_at, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        device_id,
                        str(item.get("album", "")),
                        str(item.get("filename", "")),
                        int(item.get("size") or 0),
                        str(item.get("modified_at", "")),
                        str(item.get("strict_hash", "")),
                        str(item.get("phash", "")),
                        indexed_at,
                        self._raw_json(item),
                    )
                    for item in records
                ],
            )
            connection.executemany(
                """
                INSERT INTO iphone_import_records (
                    device_id, device_name, album, filename, iphone_ref,
                    size, modified_at, strict_hash, phash,
                    save_state, import_status, indexed_at, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'iphone_only', 'indexed', ?, ?)
                ON CONFLICT(device_id, album, filename) DO UPDATE SET
                    device_name = excluded.device_name,
                    iphone_ref = excluded.iphone_ref,
                    size = excluded.size,
                    modified_at = excluded.modified_at,
                    strict_hash = excluded.strict_hash,
                    phash = excluded.phash,
                    save_state = CASE
                        WHEN iphone_import_records.local_path != ''
                          OR iphone_import_records.existing_local_path != ''
                        THEN iphone_import_records.save_state
                        ELSE 'iphone_only'
                    END,
                    import_status = CASE
                        WHEN iphone_import_records.import_status IN ('imported', 'skipped_duplicate')
                        THEN iphone_import_records.import_status
                        ELSE 'indexed'
                    END,
                    indexed_at = excluded.indexed_at,
                    updated_at = CURRENT_TIMESTAMP,
                    raw_json = excluded.raw_json
                """,
                [
                    (
                        device_id,
                        str(item.get("device_name", device_name)),
                        str(item.get("album", "")),
                        str(item.get("filename", "")),
                        self._iphone_ref(device_id, item),
                        int(item.get("size") or 0),
                        str(item.get("modified_at", "")),
                        str(item.get("strict_hash", "")),
                        str(item.get("phash", "")),
                        indexed_at,
                        self._raw_json(item),
                    )
                    for item in records
                ],
            )
            connection.commit()

    def list_import_records(self, device_id: str = "") -> list[dict[str, Any]]:
        query = """
            SELECT device_id, device_name, album, filename, iphone_ref, size, modified_at,
                   strict_hash, phash, save_state, import_status, local_path,
                   existing_local_path, deleted_from_iphone_at, indexed_at, imported_at
            FROM iphone_import_records
        """
        params: tuple[str, ...] = ()
        if device_id:
            query += " WHERE device_id = ?"
            params = (device_id,)
        query += " ORDER BY device_id, album, filename"
        with connect(self.database_path) as connection:
            return [dict(row) for row in connection.execute(query, params).fetchall()]

    def mark_imported(
        self,
        *,
        device_id: str,
        album: str,
        filename: str,
        local_path: str | Path,
        imported_at: str,
    ) -> None:
        with connect(self.database_path) as connection:
            connection.execute(
                """
                UPDATE iphone_import_records
                SET save_state = 'both',
                    import_status = 'imported',
                    local_path = ?,
                    existing_local_path = '',
                    imported_at = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE device_id = ? AND album = ? AND filename = ?
                """,
                (str(local_path), imported_at, device_id, album, filename),
            )
            connection.commit()

    def mark_skipped_duplicate(
        self,
        *,
        device_id: str,
        album: str,
        filename: str,
        existing_local_path: str | Path,
        imported_at: str,
    ) -> None:
        with connect(self.database_path) as connection:
            connection.execute(
                """
                UPDATE iphone_import_records
                SET save_state = 'iphone_only',
                    import_status = 'skipped_duplicate',
                    local_path = '',
                    existing_local_path = ?,
                    imported_at = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE device_id = ? AND album = ? AND filename = ?
                """,
                (str(existing_local_path), imported_at, device_id, album, filename),
            )
            connection.commit()

    def mark_deleted_from_iphone(
        self,
        *,
        device_id: str,
        album: str,
        filename: str,
        deleted_at: str,
    ) -> None:
        with connect(self.database_path) as connection:
            connection.execute(
                """
                UPDATE iphone_import_records
                SET deleted_from_iphone_at = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE device_id = ? AND album = ? AND filename = ?
                """,
                (deleted_at, device_id, album, filename),
            )
            connection.commit()

    @staticmethod
    def _iphone_ref(device_id: str, item: dict[str, Any]) -> str:
        return f"mtp://{device_id}/DCIM/{item.get('album', '')}/{item.get('filename', '')}"

    @staticmethod
    def _raw_json(item: dict[str, Any]) -> str:
        return json.dumps({k: v for k, v in item.items() if k != "temp_path"}, ensure_ascii=False)
