# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.storage.database import connect, init_root_database


def utc_now_text() -> str:
    return datetime.now(timezone.utc).isoformat()


def token_hash(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


class PhoneSyncRepository:
    def __init__(self, database_path: str | Path):
        self.database_path = init_root_database(database_path)

    def pair_device(
        self,
        *,
        server_id: str,
        root_id: str,
        destination_root: str,
        sync_token: str,
        token_expires_at: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        now = utc_now_text()
        device_type = self._device_type(payload.get("device_type"))
        device_id = str(payload.get("device_id", "")).strip()
        capabilities = payload.get("capabilities") if isinstance(payload.get("capabilities"), dict) else {}
        raw_json = self._raw_json(payload)
        with connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO mobile_pairings (
                    server_id, root_id, device_type, device_id, device_name,
                    device_model, platform, app_id, app_version, owner_label,
                    destination_root, pairing_status, sync_token_hash,
                    token_expires_at, paired_at, last_seen_at, capabilities_json, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'paired', ?, ?, ?, ?, ?, ?)
                ON CONFLICT(server_id, root_id, device_type, device_id) DO UPDATE SET
                    device_name = excluded.device_name,
                    device_model = excluded.device_model,
                    platform = excluded.platform,
                    app_id = excluded.app_id,
                    app_version = excluded.app_version,
                    owner_label = excluded.owner_label,
                    destination_root = excluded.destination_root,
                    pairing_status = 'paired',
                    sync_token_hash = excluded.sync_token_hash,
                    token_expires_at = excluded.token_expires_at,
                    last_seen_at = excluded.last_seen_at,
                    capabilities_json = excluded.capabilities_json,
                    raw_json = excluded.raw_json
                """,
                (
                    server_id,
                    root_id,
                    device_type,
                    device_id,
                    str(payload.get("device_name", "")).strip(),
                    str(payload.get("device_model", "")).strip(),
                    str(payload.get("platform", "")).strip(),
                    str(payload.get("app_id", "")).strip(),
                    str(payload.get("app_version", "")).strip(),
                    str(payload.get("owner_label", "")).strip(),
                    destination_root,
                    token_hash(sync_token),
                    token_expires_at,
                    now,
                    now,
                    self._raw_json(capabilities),
                    raw_json,
                ),
            )
            connection.commit()
        return self.get_pairing(
            server_id=server_id,
            root_id=root_id,
            device_type=device_type,
            device_id=device_id,
        ) or {}

    def get_pairing(
        self,
        *,
        server_id: str,
        root_id: str,
        device_type: str,
        device_id: str,
    ) -> dict[str, Any] | None:
        with connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT server_id, root_id, device_type, device_id, device_name,
                       device_model, platform, app_id, app_version, owner_label,
                       destination_root, pairing_status, token_expires_at,
                       paired_at, last_seen_at, capabilities_json, raw_json
                FROM mobile_pairings
                WHERE server_id = ? AND root_id = ? AND device_type = ? AND device_id = ?
                """,
                (server_id, root_id, self._device_type(device_type), device_id),
            ).fetchone()
        return dict(row) if row is not None else None

    def start_session(
        self,
        *,
        session_id: str,
        server_id: str,
        root_id: str,
        destination_root: str,
        sync_token: str,
        token_expires_at: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        now = utc_now_text()
        device_type = self._device_type(payload.get("device_type"))
        device_id = str(payload.get("device_id", "")).strip()
        server_cursor = f"{session_id}:{now}"
        with connect(self.database_path) as connection:
            pairing = connection.execute(
                """
                SELECT id FROM mobile_pairings
                WHERE server_id = ?
                  AND root_id = ?
                  AND device_type = ?
                  AND device_id = ?
                  AND sync_token_hash = ?
                  AND pairing_status = 'paired'
                """,
                (server_id, root_id, device_type, device_id, token_hash(sync_token)),
            ).fetchone()
            if pairing is None:
                raise ValueError("Invalid sync token")
            connection.execute(
                """
                INSERT INTO mobile_sync_sessions (
                    session_id, server_id, root_id, device_type, device_id,
                    destination_root, status, sync_token_hash, token_expires_at,
                    client_cursor, server_cursor, battery_state, network_type,
                    started_at, last_seen_at, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, 'ready', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    status = 'ready',
                    last_seen_at = excluded.last_seen_at,
                    client_cursor = excluded.client_cursor,
                    server_cursor = excluded.server_cursor,
                    battery_state = excluded.battery_state,
                    network_type = excluded.network_type,
                    raw_json = excluded.raw_json
                """,
                (
                    session_id,
                    server_id,
                    root_id,
                    device_type,
                    device_id,
                    destination_root,
                    token_hash(sync_token),
                    token_expires_at,
                    str(payload.get("last_client_cursor", "")).strip(),
                    server_cursor,
                    str(payload.get("battery_state", "")).strip(),
                    str(payload.get("network_type", "")).strip(),
                    now,
                    now,
                    self._raw_json(payload),
                ),
            )
            connection.commit()
        return self.get_session(session_id) or {}

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT session_id, server_id, root_id, device_type, device_id,
                       destination_root, status, token_expires_at, client_cursor,
                       server_cursor, battery_state, network_type, started_at,
                       last_seen_at, finished_at, raw_json
                FROM mobile_sync_sessions
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def get_manifest_item(self, *, session_id: str, item_id: str) -> dict[str, Any] | None:
        with connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT id, run_id, session_id, upload_batch_id, source_ref,
                       server_id, root_id, device_type, device_id, item_id,
                       original_filename, media_type, mime_type, size,
                       created_at, modified_at, timezone, album, width, height,
                       duration_ms, strict_hash, phash, status, local_path,
                       existing_local_path, error, manifest_seen_at, imported_at,
                       raw_json
                FROM import_items
                WHERE session_id = ? AND item_id = ?
                """,
                (session_id, item_id),
            ).fetchone()
        return dict(row) if row is not None else None

    def mark_uploaded_item(
        self,
        *,
        session_id: str,
        item_id: str,
        status: str,
        strict_hash: str,
        phash: str = "",
        local_path: str = "",
        existing_local_path: str = "",
        error: str = "",
        imported_at: str = "",
    ) -> None:
        now = imported_at or utc_now_text()
        with connect(self.database_path) as connection:
            connection.execute(
                """
                UPDATE import_items
                SET strict_hash = ?,
                    phash = ?,
                    status = ?,
                    local_path = ?,
                    existing_local_path = ?,
                    error = ?,
                    imported_at = ?,
                    manifest_seen_at = manifest_seen_at
                WHERE session_id = ? AND item_id = ?
                """,
                (
                    strict_hash,
                    phash,
                    status,
                    local_path,
                    existing_local_path,
                    error,
                    now,
                    session_id,
                    item_id,
                ),
            )
            connection.execute(
                "UPDATE mobile_sync_sessions SET status = 'syncing', last_seen_at = ? WHERE session_id = ?",
                (now, session_id),
            )
            connection.commit()

    def save_manifest(
        self,
        *,
        upload_batch_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        session = self.get_session(str(payload.get("session_id", "")).strip())
        if session is None:
            raise ValueError("Unknown sync session")

        now = utc_now_text()
        items = payload.get("items") if isinstance(payload.get("items"), list) else []
        upload: list[dict[str, str]] = []
        skip: list[dict[str, str]] = []
        with connect(self.database_path) as connection:
            for item in items:
                if not isinstance(item, dict):
                    continue
                item_id = str(item.get("item_id", "")).strip()
                if not item_id:
                    continue
                existing = connection.execute(
                    """
                    SELECT status, local_path, existing_local_path
                    FROM import_items
                    WHERE server_id = ? AND root_id = ? AND device_type = ? AND device_id = ? AND item_id = ?
                    """,
                    (
                        session["server_id"],
                        session["root_id"],
                        session["device_type"],
                        session["device_id"],
                        item_id,
                    ),
                ).fetchone()
                if existing is not None and str(existing["status"]) in {
                    "imported",
                    "already_imported",
                    "skipped_duplicate",
                    "skipped_deleted_locally",
                }:
                    skip.append(
                        {
                            "item_id": item_id,
                            "status": str(existing["status"]),
                            "local_path": str(existing["local_path"] or existing["existing_local_path"] or ""),
                        }
                    )
                    continue
                connection.execute(
                    """
                    INSERT INTO import_items (
                        run_id, session_id, upload_batch_id, source_ref,
                        server_id, root_id, device_type, device_id, item_id,
                        original_filename, media_type, mime_type, size,
                        created_at, modified_at, timezone, album, width, height,
                        duration_ms, strict_hash, status, manifest_seen_at, raw_json
                    ) VALUES ('', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'manifested', ?, ?)
                    ON CONFLICT(server_id, root_id, device_type, device_id, item_id) DO UPDATE SET
                        session_id = excluded.session_id,
                        upload_batch_id = excluded.upload_batch_id,
                        source_ref = excluded.source_ref,
                        original_filename = excluded.original_filename,
                        media_type = excluded.media_type,
                        mime_type = excluded.mime_type,
                        size = excluded.size,
                        created_at = excluded.created_at,
                        modified_at = excluded.modified_at,
                        timezone = excluded.timezone,
                        album = excluded.album,
                        width = excluded.width,
                        height = excluded.height,
                        duration_ms = excluded.duration_ms,
                        strict_hash = excluded.strict_hash,
                        status = 'manifested',
                        manifest_seen_at = excluded.manifest_seen_at,
                        raw_json = excluded.raw_json
                    """,
                    (
                        session["session_id"],
                        upload_batch_id,
                        self._mobile_ref(session["device_type"], session["device_id"], item_id),
                        session["server_id"],
                        session["root_id"],
                        session["device_type"],
                        session["device_id"],
                        item_id,
                        str(item.get("filename", "")).strip(),
                        str(item.get("media_type", "")).strip(),
                        str(item.get("mime_type", "")).strip(),
                        int(item.get("size") or 0),
                        str(item.get("created_at", "")).strip(),
                        str(item.get("modified_at", "")).strip(),
                        str(item.get("timezone", "")).strip(),
                        str(item.get("album", "")).strip(),
                        int(item.get("width") or 0),
                        int(item.get("height") or 0),
                        int(item.get("duration_ms") or 0),
                        str(item.get("sha256", "")).strip(),
                        now,
                        self._raw_json(item),
                    ),
                )
                upload.append(
                    {
                        "item_id": item_id,
                        "upload_url": "/api/mobile/sync/upload",
                        "status": "upload_required",
                    }
                )
            connection.execute(
                "UPDATE mobile_sync_sessions SET status = 'syncing', last_seen_at = ? WHERE session_id = ?",
                (now, session["session_id"]),
            )
            connection.commit()
        return {
            "status": "accepted",
            "session_id": session["session_id"],
            "upload_batch_id": upload_batch_id,
            "upload": upload,
            "skip": skip,
            "batch_size": 10,
        }

    def status(self, *, destination_root: str = "") -> dict[str, Any]:
        with connect(self.database_path) as connection:
            paired_devices = connection.execute(
                "SELECT COUNT(*) AS count FROM mobile_pairings WHERE pairing_status = 'paired'"
            ).fetchone()["count"]
            sessions = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT device_type, device_id, status, last_seen_at
                    FROM mobile_sync_sessions
                    ORDER BY last_seen_at DESC
                    LIMIT 20
                    """
                ).fetchall()
            ]
            summary = dict(
                connection.execute(
                    """
                    SELECT
                        COUNT(*) AS processed,
                        SUM(CASE WHEN status = 'imported' THEN 1 ELSE 0 END) AS imported,
                        SUM(CASE WHEN status = 'skipped_duplicate' THEN 1 ELSE 0 END) AS skipped_duplicate,
                        SUM(CASE WHEN status = 'skipped_deleted_locally' THEN 1 ELSE 0 END) AS skipped_deleted_locally,
                        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed
                    FROM import_items
                    WHERE status IN ('imported', 'already_imported', 'skipped_duplicate', 'skipped_deleted_locally', 'failed')
                    """
                ).fetchone()
            )
        normalized_summary = {
            "processed": int(summary.get("processed") or 0),
            "imported": int(summary.get("imported") or 0),
            "skipped_duplicate": int(summary.get("skipped_duplicate") or 0),
            "skipped_deleted_locally": int(summary.get("skipped_deleted_locally") or 0),
            "failed": int(summary.get("failed") or 0),
        }
        return {
            "status": "syncing" if any(item.get("status") == "syncing" for item in sessions) else "idle",
            "destination_root": destination_root,
            "paired_devices": int(paired_devices or 0),
            "connected_devices": sessions,
            "summary": normalized_summary,
            "recent_events": [],
        }

    @staticmethod
    def _device_type(device_type: Any) -> str:
        return str(device_type or "iphone").strip().lower() or "iphone"

    @staticmethod
    def _mobile_ref(device_type: str, device_id: str, item_id: str) -> str:
        return f"mobile://{device_type}/{device_id}/{item_id}"

    @staticmethod
    def _raw_json(item: dict[str, Any]) -> str:
        return json.dumps(item, ensure_ascii=False)
