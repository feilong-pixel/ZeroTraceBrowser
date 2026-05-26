from .base import *
from .settings_context import load_settings, save_settings
from .root_workspace import root_data_id, root_database_path
from .iphone_context import (
    _apply_portable_file_times,
    _find_existing_strict_duplicate,
    _invalidate_gallery_index,
    _import_staged_iphone_media,
    _local_time_text,
    _parse_iphone_shortcut_time,
    _safe_upload_filename,
    _sha256_file,
)

import secrets
import socket
import tempfile
import uuid
import io
import json
from datetime import datetime, timedelta, timezone

from MediaArchiveOrganizer.core.duplicate_detector import compute_phash
from core.storage.duplicates_repository import DuplicateResultRepository
from core.storage.hash_db_repository import HashDbRepository
from core.storage.mobile_repository import MobileRepository
from core.storage.phone_sync_repository import PhoneSyncRepository


PHONE_SYNC_BATCH_SIZE = 10
PHONE_SYNC_TOKEN_MINUTES = 30


def get_mobile_sync_pairing_code(request_url: str = "") -> dict[str, Any]:
    _, active_root, root_id, server_id, _ = _phone_sync_context()
    base_url = _local_network_base_url(request_url)
    pairing_token = _new_token("pair")
    expires_at = _token_expires_at()
    payload = {
        "protocol": "zerotrace-phone-sync",
        "version": 1,
        "server_id": server_id,
        "root_id": root_id,
        "base_url": base_url,
        "pairing_token": pairing_token,
        "pair_url": f"{base_url}/api/mobile/pair",
        "sync_start_url": f"{base_url}/api/mobile/sync/start",
        "manifest_url": f"{base_url}/api/mobile/sync/manifest",
        "upload_url": f"{base_url}/api/mobile/sync/upload",
        "status_url": f"{base_url}/api/mobile/sync/status",
        "expires_at": expires_at,
    }
    return {
        "status": "ready",
        "server_id": server_id,
        "root_id": root_id,
        "destination_root": str(active_root),
        "base_url": base_url,
        "pairing_token": pairing_token,
        "pairing_token_expires_at": expires_at,
        "payload": payload,
        "payload_text": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        "qr_svg": _optional_qr_svg(json.dumps(payload, ensure_ascii=False, separators=(",", ":"))),
    }


def get_phone_sync_server_id() -> str:
    settings = load_settings()
    phone_sync = settings.get("phone_sync", {})
    if not isinstance(phone_sync, dict):
        phone_sync = {}
    server_id = str(phone_sync.get("server_id", "")).strip()
    if server_id:
        return server_id
    server_id = f"ztb-{uuid.uuid4().hex}"
    phone_sync["server_id"] = server_id
    settings["phone_sync"] = phone_sync
    save_settings(settings)
    return server_id


def _phone_sync_context() -> tuple[dict[str, Any], Path, str, str, PhoneSyncRepository]:
    settings = load_settings()
    active_root = Path(settings["active_root"]).expanduser().resolve()
    root_id = root_data_id(active_root)
    server_id = get_phone_sync_server_id()
    return settings, active_root, root_id, server_id, PhoneSyncRepository(root_database_path(active_root))


def _new_token(prefix: str) -> str:
    return f"{prefix}-{secrets.token_urlsafe(24)}"


def _token_expires_at() -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=PHONE_SYNC_TOKEN_MINUTES)).isoformat()


def pair_mobile_device(payload: Any) -> dict[str, Any]:
    _, active_root, root_id, server_id, repository = _phone_sync_context()
    sync_token = _new_token("sync")
    expires_at = _token_expires_at()
    payload_dict = payload.model_dump() if hasattr(payload, "model_dump") else dict(payload)
    pairing = repository.pair_device(
        server_id=server_id,
        root_id=root_id,
        destination_root=str(active_root),
        sync_token=sync_token,
        token_expires_at=expires_at,
        payload=payload_dict,
    )
    return {
        "status": "paired",
        "device_type": pairing.get("device_type", payload.device_type),
        "device_id": pairing.get("device_id", payload.device_id),
        "server_id": server_id,
        "root_id": root_id,
        "destination_root": str(active_root),
        "sync_token": sync_token,
        "sync_token_expires_at": expires_at,
        "batch_size": PHONE_SYNC_BATCH_SIZE,
        "accepted_types": sorted(SUPPORTED_EXTENSIONS),
        "duplicate_policy": "strict_skip",
        "deleted_marker_policy": "skip_deleted_locally",
    }


def start_mobile_sync(payload: Any) -> dict[str, Any]:
    _, active_root, root_id, server_id, repository = _phone_sync_context()
    session_id = f"phone-sync-{uuid.uuid4().hex}"
    expires_at = _token_expires_at()
    payload_dict = payload.model_dump() if hasattr(payload, "model_dump") else dict(payload)
    try:
        session = repository.start_session(
            session_id=session_id,
            server_id=server_id,
            root_id=root_id,
            destination_root=str(active_root),
            sync_token=payload.sync_token,
            token_expires_at=expires_at,
            payload=payload_dict,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    status = repository.status(destination_root=str(active_root))
    return {
        "status": "ready",
        "session_id": session["session_id"],
        "server_id": server_id,
        "root_id": root_id,
        "destination_root": str(active_root),
        "batch_size": PHONE_SYNC_BATCH_SIZE,
        "server_cursor": session.get("server_cursor", ""),
        "known_item_ids": [],
        "skip_hashes": [],
        "deleted_hashes": [],
        "summary": status["summary"],
    }


def save_mobile_sync_manifest(payload: Any) -> dict[str, Any]:
    _, active_root, _, _, repository = _phone_sync_context()
    payload_dict = payload.model_dump() if hasattr(payload, "model_dump") else dict(payload)
    upload_batch_id = f"batch-{uuid.uuid4().hex}"
    try:
        result = repository.save_manifest(upload_batch_id=upload_batch_id, payload=payload_dict)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {**result, "destination_root": str(active_root)}


def upload_mobile_sync_item(metadata: dict[str, Any], body: bytes) -> dict[str, Any]:
    if not body:
        raise HTTPException(status_code=400, detail="Upload body is empty")

    _, active_root, _, _, repository = _phone_sync_context()
    session_id = str(metadata.get("session_id", "")).strip()
    item_id = str(metadata.get("item_id", "")).strip()
    if not session_id or not item_id:
        raise HTTPException(status_code=400, detail="session_id and item_id are required")

    session = repository.get_session(session_id)
    item = repository.get_manifest_item(session_id=session_id, item_id=item_id)
    if session is None or item is None:
        raise HTTPException(status_code=400, detail="Unknown sync item")

    device_type = str(metadata.get("device_type") or item["device_type"]).strip().lower() or "iphone"
    device_id = str(metadata.get("device_id") or item["device_id"]).strip()
    if device_type != str(item["device_type"]) or device_id != str(item["device_id"]):
        raise HTTPException(status_code=400, detail="Upload device does not match manifest")

    filename = _safe_upload_filename(str(metadata.get("filename") or item["original_filename"] or "photo.jpg"))
    created_at = _parse_iphone_shortcut_time(str(metadata.get("created_at") or item["created_at"] or ""))
    modified_at = _parse_iphone_shortcut_time(str(metadata.get("modified_at") or item["modified_at"] or ""))
    database_path = root_database_path(active_root)
    imported_at = datetime.now(timezone.utc).isoformat()

    with tempfile.TemporaryDirectory(prefix="ztb_phone_sync_upload_") as temp_name:
        staged_path = Path(temp_name) / filename
        staged_path.write_bytes(body)
        _apply_portable_file_times(staged_path, created_at, modified_at)

        strict_hash = _sha256_file(staged_path)
        phash = _compute_optional_phash(staged_path)
        size = staged_path.stat().st_size

        mobile_repository = MobileRepository(database_path)
        deleted_marker = mobile_repository.find_deleted_local_marker(strict_hash)
        if deleted_marker:
            repository.mark_uploaded_item(
                session_id=session_id,
                item_id=item_id,
                status="skipped_deleted_locally",
                strict_hash=strict_hash,
                phash=phash,
                error="deleted_locally",
                imported_at=imported_at,
            )
            return {
                "status": "skipped_deleted_locally",
                "imported": False,
                "item_id": item_id,
                "file": filename,
                "sha256": strict_hash,
                "size": size,
                "deleted_at": str(deleted_marker.get("deleted_at", "")),
                "deleted_relative_path": str(deleted_marker.get("relative_path", "")),
                "delete_source": str(deleted_marker.get("delete_source", "")),
            }

        hash_repository = HashDbRepository(database_path)
        existing_local_path = _find_existing_strict_duplicate(hash_repository.load_hash_db(), strict_hash, active_root)
        if existing_local_path:
            repository.mark_uploaded_item(
                session_id=session_id,
                item_id=item_id,
                status="skipped_duplicate",
                strict_hash=strict_hash,
                phash=phash,
                existing_local_path=existing_local_path,
                imported_at=imported_at,
            )
            return {
                "status": "skipped_duplicate",
                "imported": False,
                "item_id": item_id,
                "file": filename,
                "sha256": strict_hash,
                "existing_local_path": existing_local_path,
                "size": size,
            }

        imported = _import_staged_iphone_media(
            staged_path,
            filename,
            active_root,
            _local_time_text(created_at),
            _local_time_text(modified_at),
        )
        hash_repository.add_hash_record("strict", strict_hash, str(imported))
        if phash:
            hash_repository.add_hash_record("phash", phash, str(imported))
        DuplicateResultRepository(database_path).mark_dirty(active_root, "phone_sync_upload")
        repository.mark_uploaded_item(
            session_id=session_id,
            item_id=item_id,
            status="imported",
            strict_hash=strict_hash,
            phash=phash,
            local_path=str(imported),
            imported_at=imported_at,
        )
        _invalidate_gallery_index(active_root)

    return {
        "status": "success",
        "imported": True,
        "item_id": item_id,
        "file": filename,
        "local_path": str(imported),
        "sha256": strict_hash,
        "phash": phash,
        "size": size,
        "destination_root": str(active_root),
    }


def get_mobile_sync_status() -> dict[str, Any]:
    _, active_root, _, _, repository = _phone_sync_context()
    return repository.status(destination_root=str(active_root))


def _compute_optional_phash(path: Path) -> str:
    try:
        return compute_phash(str(path)) or ""
    except Exception:
        return ""


def _local_network_base_url(request_url: str = "") -> str:
    port = "8000"
    try:
        from urllib.parse import urlparse

        parsed = urlparse(str(request_url or ""))
        if parsed.port:
            port = str(parsed.port)
    except ValueError:
        pass
    return f"http://{_local_lan_ip()}:{port}"


def _local_lan_ip() -> str:
    candidates: list[str] = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))
            candidates.append(str(probe.getsockname()[0]))
    except OSError:
        pass
    try:
        hostname = socket.gethostname()
        candidates.extend(socket.gethostbyname_ex(hostname)[2])
    except OSError:
        pass
    for candidate in candidates:
        if candidate and not candidate.startswith("127.") and ":" not in candidate:
            return candidate
    return "127.0.0.1"


def _optional_qr_svg(payload: str) -> str:
    try:
        import qrcode
        import qrcode.image.svg
    except Exception:
        return ""
    factory = qrcode.image.svg.SvgPathImage
    image = qrcode.make(payload, image_factory=factory, box_size=6, border=2)
    stream = io.BytesIO()
    image.save(stream)
    return stream.getvalue().decode("utf-8")
