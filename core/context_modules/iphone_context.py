# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import platform
import hashlib
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from .settings_context import load_settings
from .root_workspace import root_database_path
from core.storage.iphone_repository import IphoneRepository
from MediaArchiveOrganizer.core.duplicate_detector import compute_phash


IPHONE_DEVICE_PROBE_TIMEOUT_SECONDS = 20
IPHONE_INDEX_TIMEOUT_SECONDS = 600


def _run_iphone_device_probe() -> list[dict[str, Any]]:
    script = r"""
$ErrorActionPreference = "Stop"
function Get-ShellFolderItems {
    param([Parameter(Mandatory = $true)] $Folder)
    $items = @()
    foreach ($item in $Folder.Items()) { $items += $item }
    return $items
}
function Find-ChildFolder {
    param(
        [Parameter(Mandatory = $true)] $Folder,
        [Parameter(Mandatory = $true)] [string] $Name
    )
    foreach ($item in Get-ShellFolderItems -Folder $Folder) {
        if ($item.IsFolder -and $item.Name -ieq $Name) { return $item.GetFolder }
    }
    return $null
}
function Find-DcimFolder {
    param([Parameter(Mandatory = $true)] $Device)
    $deviceFolder = $Device.GetFolder
    $internal = Find-ChildFolder -Folder $deviceFolder -Name "Internal Storage"
    if ($null -ne $internal) {
        $dcim = Find-ChildFolder -Folder $internal -Name "DCIM"
        if ($null -ne $dcim) { return $dcim }
    }
    return Find-ChildFolder -Folder $deviceFolder -Name "DCIM"
}
$shell = New-Object -ComObject Shell.Application
$thisPc = $shell.Namespace(17)
if ($null -eq $thisPc) { throw "Cannot open Shell namespace for This PC." }
$devices = @()
foreach ($item in Get-ShellFolderItems -Folder $thisPc) {
    if (-not $item.IsFolder -or $item.Name -notmatch "iPhone|Apple|iPad") { continue }
    $dcim = Find-DcimFolder -Device $item
    $albumCount = 0
    $sampleCount = 0
    if ($null -ne $dcim) {
        foreach ($album in Get-ShellFolderItems -Folder $dcim) {
            if (-not $album.IsFolder) { continue }
            $albumCount += 1
            foreach ($media in Get-ShellFolderItems -Folder $album.GetFolder) {
                if (-not $media.IsFolder) { $sampleCount += 1 }
                if ($sampleCount -ge 5) { break }
            }
            if ($sampleCount -ge 5) { break }
        }
    }
    $devices += [ordered]@{
        name = $item.Name
        device_id = $item.Name
        kind = "mtp"
        dcim_available = ($null -ne $dcim)
        album_count_sample = $albumCount
        media_count_sample = $sampleCount
    }
}
$devices | ConvertTo-Json -Depth 4 -Compress
"""
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="replace",
        timeout=IPHONE_DEVICE_PROBE_TIMEOUT_SECONDS,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "iPhone device probe failed")

    output = completed.stdout.strip()
    if not output:
        return []
    parsed = json.loads(output)
    if isinstance(parsed, dict):
        return [parsed]
    return parsed if isinstance(parsed, list) else []


def detect_iphone_devices() -> dict[str, Any]:
    if platform.system().lower() != "windows":
        return {
            "supported": False,
            "devices": [],
            "message": "iPhone MTP detection is only supported on Windows.",
        }

    try:
        devices = _run_iphone_device_probe()
    except Exception as exc:
        return {
            "supported": True,
            "devices": [],
            "message": str(exc),
        }

    return {
        "supported": True,
        "devices": devices,
        "message": "ok" if devices else "No iPhone device found.",
    }


def _copy_iphone_media_for_index(device_id: str, temp_dir: Path) -> list[dict[str, Any]]:
    script = r"""
param(
    [Parameter(Mandatory = $true)] [string] $DeviceId,
    [Parameter(Mandatory = $true)] [string] $TempDir
)
$ErrorActionPreference = "Stop"
function Get-ShellFolderItems {
    param([Parameter(Mandatory = $true)] $Folder)
    $items = @()
    foreach ($item in $Folder.Items()) { $items += $item }
    return $items
}
function Find-ChildFolder {
    param(
        [Parameter(Mandatory = $true)] $Folder,
        [Parameter(Mandatory = $true)] [string] $Name
    )
    foreach ($item in Get-ShellFolderItems -Folder $Folder) {
        if ($item.IsFolder -and $item.Name -ieq $Name) { return $item.GetFolder }
    }
    return $null
}
function Find-DcimFolder {
    param([Parameter(Mandatory = $true)] $Device)
    $deviceFolder = $Device.GetFolder
    $internal = Find-ChildFolder -Folder $deviceFolder -Name "Internal Storage"
    if ($null -ne $internal) {
        $dcim = Find-ChildFolder -Folder $internal -Name "DCIM"
        if ($null -ne $dcim) { return $dcim }
    }
    return Find-ChildFolder -Folder $deviceFolder -Name "DCIM"
}
function Copy-MtpItem {
    param(
        [Parameter(Mandatory = $true)] $Shell,
        [Parameter(Mandatory = $true)] $Item,
        [Parameter(Mandatory = $true)] [string] $Album,
        [Parameter(Mandatory = $true)] [string] $TempDir
    )
    $albumDir = Join-Path $TempDir $Album
    New-Item -ItemType Directory -Path $albumDir -Force | Out-Null
    $destination = $Shell.Namespace($albumDir)
    $before = @{}
    Get-ChildItem -LiteralPath $albumDir -File -Force | ForEach-Object { $before[$_.FullName] = $true }
    $destination.CopyHere($Item, 16)
    $copied = $null
    $deadline = (Get-Date).AddSeconds(60)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 250
        $copied = Get-ChildItem -LiteralPath $albumDir -File -Force |
            Where-Object { -not $before.ContainsKey($_.FullName) } |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1
        if ($null -ne $copied -and $copied.Length -gt 0) { break }
    }
    if ($null -eq $copied) { return $null }
    return $copied
}
$shell = New-Object -ComObject Shell.Application
$thisPc = $shell.Namespace(17)
if ($null -eq $thisPc) { throw "Cannot open Shell namespace for This PC." }
$target = $null
foreach ($item in Get-ShellFolderItems -Folder $thisPc) {
    if ($item.IsFolder -and ($item.Name -eq $DeviceId -or $item.Name -match "iPhone|Apple|iPad")) {
        $target = $item
        if ($item.Name -eq $DeviceId) { break }
    }
}
if ($null -eq $target) { throw "iPhone device not found: $DeviceId" }
$dcim = Find-DcimFolder -Device $target
if ($null -eq $dcim) { throw "DCIM folder not found." }
$records = @()
foreach ($album in Get-ShellFolderItems -Folder $dcim) {
    if (-not $album.IsFolder) { continue }
    foreach ($media in Get-ShellFolderItems -Folder $album.GetFolder) {
        if ($media.IsFolder) { continue }
        $copied = Copy-MtpItem -Shell $shell -Item $media -Album $album.Name -TempDir $TempDir
        if ($null -eq $copied) { continue }
        $records += [ordered]@{
            device_id = $target.Name
            device_name = $target.Name
            album = $album.Name
            filename = $media.Name
            temp_path = $copied.FullName
            size = $copied.Length
            modified_at = $copied.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss")
        }
    }
}
$records | ConvertTo-Json -Depth 4 -Compress
"""
    script_path = temp_dir / "iphone_index_copy.ps1"
    script_path.write_text(script, encoding="utf-8")
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
            "-DeviceId",
            device_id,
            "-TempDir",
            str(temp_dir),
        ],
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="replace",
        timeout=IPHONE_INDEX_TIMEOUT_SECONDS,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "iPhone index copy failed")
    output = completed.stdout.strip()
    if not output:
        return []
    parsed = json.loads(output)
    if isinstance(parsed, dict):
        return [parsed]
    return parsed if isinstance(parsed, list) else []


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_iphone_photo_index(device_id: str) -> dict[str, Any]:
    if platform.system().lower() != "windows":
        return {"status": "unsupported", "indexed": 0, "message": "iPhone MTP indexing is only supported on Windows."}

    normalized_device_id = str(device_id or "").strip()
    if not normalized_device_id:
        raise HTTPException(status_code=400, detail="Device id is required")

    settings = load_settings()
    active_root = Path(settings["active_root"]).expanduser().resolve()
    database_path = root_database_path(active_root)

    indexed_at = datetime.now(timezone.utc).isoformat()
    with tempfile.TemporaryDirectory(prefix="ztb_iphone_index_") as temp_name:
        copied_records = _copy_iphone_media_for_index(normalized_device_id, Path(temp_name))
        indexed_records: list[dict[str, Any]] = []
        for record in copied_records:
            temp_path = Path(str(record.get("temp_path", "")))
            if not temp_path.exists() or not temp_path.is_file():
                continue
            strict_hash = _sha256_file(temp_path)
            phash = compute_phash(str(temp_path)) or ""
            indexed_records.append(
                {
                    **record,
                    "strict_hash": strict_hash,
                    "phash": phash,
                    "indexed_at": indexed_at,
                }
            )

    device_name = indexed_records[0].get("device_name", normalized_device_id) if indexed_records else normalized_device_id
    albums = {str(item.get("album", "")) for item in indexed_records if str(item.get("album", "")).strip()}
    IphoneRepository(database_path).save_index(
        device_id=normalized_device_id,
        device_name=str(device_name),
        indexed_at=indexed_at,
        records=indexed_records,
    )

    return {
        "status": "indexed",
        "device_id": normalized_device_id,
        "device_name": str(device_name),
        "album_count": len(albums),
        "indexed": len(indexed_records),
        "indexed_at": indexed_at,
        "database_path": str(database_path),
    }
