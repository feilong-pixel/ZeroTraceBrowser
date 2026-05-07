# SPDX-License-Identifier: MIT

from __future__ import annotations

import os
from pathlib import Path

from fastapi import HTTPException


LOCAL_CORS_ORIGINS = [
    "http://localhost",
    "http://127.0.0.1",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
LOCAL_TRUSTED_HOSTS = ["localhost", "127.0.0.1", "::1"]


def cors_origins_from_env() -> list[str]:
    configured = os.getenv("ZTB_CORS_ORIGINS", "").strip()
    if not configured:
        return LOCAL_CORS_ORIGINS
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


def trusted_hosts_from_env() -> list[str]:
    configured = os.getenv("ZTB_TRUSTED_HOSTS", "").strip()
    if not configured:
        return LOCAL_TRUSTED_HOSTS
    return [host.strip() for host in configured.split(",") if host.strip()]


def is_arbitrary_open_path_allowed() -> bool:
    return os.getenv("ZTB_ALLOW_ARBITRARY_OPEN_PATH", "").strip().lower() in {"1", "true", "yes", "on"}


def resolve_path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def is_within_or_equal(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def require_existing_directory(path: Path, label: str) -> Path:
    if not path.exists() or not path.is_dir():
        raise HTTPException(status_code=400, detail=f"{label} must be an existing directory")
    return path


def require_not_same_or_child(child: Path, parent: Path, detail: str) -> None:
    if is_within_or_equal(child, parent):
        raise HTTPException(status_code=400, detail=detail)


def require_open_path_allowed(target: Path, allowed_roots: list[Path]) -> None:
    if is_arbitrary_open_path_allowed():
        return

    if any(is_within_or_equal(target, root) for root in allowed_roots):
        return

    raise HTTPException(status_code=403, detail="Path is outside configured safe locations")
