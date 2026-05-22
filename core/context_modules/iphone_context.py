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
from .root_workspace import root_database_path, root_image_index_dir
from core.config.app_config import SKIP_SCAN_DIR_NAMES, SUPPORTED_EXTENSIONS
from core.services.image_index_service import (
    digest_for_cache_key,
    image_index_cache_path,
    image_index_summary_path,
    image_scan_cache_key,
    timeline_index_cache_path,
)
from core.services.image_scan_service import clear_image_list_cache
from core.storage.hash_db_repository import HashDbRepository
from core.storage.image_index_repository import ImageIndexRepository
from core.storage.mobile_repository import MobileRepository
from MediaArchiveOrganizer.core.date_classifier import build_date_path, get_target_date
from MediaArchiveOrganizer.core.duplicate_detector import compute_phash
from MediaArchiveOrganizer.core.file_transfer import apply_windows_file_times, read_windows_file_times
from MediaArchiveOrganizer.services.organizer import get_unique_path, transfer_file


IPHONE_DEVICE_PROBE_TIMEOUT_SECONDS = 20
IPHONE_INDEX_TIMEOUT_SECONDS = 600
IPHONE_DELETE_TIMEOUT_SECONDS = 60
IPHONE_INDEX_DEFAULT_LIMIT = 1
IPHONE_INDEX_MAX_LIMIT = 10000
SUPPORTED_MOBILE_DEVICE_TYPES = {"iphone"}


def _normalize_mobile_device_type(device_type: str = "iphone") -> str:
    normalized = str(device_type or "iphone").strip().lower()
    if normalized not in SUPPORTED_MOBILE_DEVICE_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported mobile device type: {device_type}")
    return normalized


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


def probe_iphone_item_properties(device_id: str) -> dict[str, Any]:
    if platform.system().lower() != "windows":
        return {
            "supported": False,
            "device_id": str(device_id or "").strip(),
            "properties": {},
            "details": [],
            "message": "iPhone MTP property probing is only supported on Windows.",
        }

    normalized_device_id = str(device_id or "").strip()
    if not normalized_device_id:
        raise HTTPException(status_code=400, detail="Device id is required")

    script = r"""
param([Parameter(Mandatory = $true)] [string] $DeviceId)
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$OutputEncoding = [Text.UTF8Encoding]::new($false)
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
$albumName = ""
$media = $null
$mediaFolder = $null
:albumLoop foreach ($album in Get-ShellFolderItems -Folder $dcim) {
    if (-not $album.IsFolder) { continue }
    $folder = $album.GetFolder
    foreach ($item in Get-ShellFolderItems -Folder $folder) {
        if ($item.IsFolder) { continue }
        $albumName = $album.Name
        $mediaFolder = $folder
        $media = $item
        break albumLoop
    }
}
if ($null -eq $media) { throw "No media item found under DCIM." }
$propertyNames = @(
    "System.ItemNameDisplay",
    "System.FileName",
    "System.ItemPathDisplay",
    "System.ItemFolderPathDisplay",
    "System.ParsingPath",
    "System.ItemUrl",
    "System.ItemTypeText",
    "System.Kind",
    "System.DateModified",
    "System.ItemDate",
    "System.DateCreated",
    "System.Size",
    "System.Photo.DateTaken",
    "System.Image.HorizontalSize",
    "System.Image.VerticalSize",
    "System.Media.UniqueFileIdentifier",
    "System.Identity",
    "System.StorageProviderFileIdentifier"
)
$properties = [ordered]@{}
foreach ($propertyName in $propertyNames) {
    try {
        $value = $media.ExtendedProperty($propertyName)
        if ($null -ne $value) { $properties[$propertyName] = [string]$value }
    } catch {
        $properties[$propertyName] = "__ERROR__: $($_.Exception.Message)"
    }
}
$details = @()
for ($i = 0; $i -lt 320; $i++) {
    try {
        $label = $mediaFolder.GetDetailsOf($null, $i)
        $value = $mediaFolder.GetDetailsOf($media, $i)
        if ($label -or $value) {
            $details += [ordered]@{ index = $i; label = [string]$label; value = [string]$value }
        }
    } catch {}
}
[ordered]@{
    supported = $true
    device_id = $target.Name
    album = $albumName
    filename = $media.Name
    properties = $properties
    details = $details
} | ConvertTo-Json -Depth 5 -Compress
"""
    with tempfile.TemporaryDirectory(prefix="ztb_iphone_probe_") as temp_name:
        script_path = Path(temp_name) / "iphone_probe_properties.ps1"
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
                normalized_device_id,
            ],
            capture_output=True,
            check=False,
            timeout=IPHONE_DEVICE_PROBE_TIMEOUT_SECONDS,
        )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        stdout = completed.stdout.decode("utf-8", errors="replace").strip()
        raise HTTPException(status_code=400, detail=stderr or stdout or "iPhone property probe failed")
    output = completed.stdout.decode("utf-8-sig", errors="replace").strip()
    return json.loads(output) if output else {"supported": True, "device_id": normalized_device_id, "properties": {}, "details": []}


def _copy_iphone_media_for_index(
    device_id: str,
    temp_dir: Path,
    cutoff_modified_at: str = "",
    skip_refs: list[str] | None = None,
    limit: int = IPHONE_INDEX_DEFAULT_LIMIT,
) -> list[dict[str, Any]]:
    script = r"""
param(
    [Parameter(Mandatory = $true)] [string] $DeviceId,
    [Parameter(Mandatory = $true)] [string] $TempDir,
    [Parameter(Mandatory = $true)] [int] $Limit,
    [string] $CutoffModifiedAt = "",
    [string] $SkipRefsPath = ""
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
function Get-MtpItemModifiedAt {
    param([Parameter(Mandatory = $true)] $Item)
    $propertyNames = @("System.DateModified", "System.ItemDate")
    foreach ($propertyName in $propertyNames) {
        try {
            $value = $Item.ExtendedProperty($propertyName)
            if ($null -ne $value) { return [datetime]$value }
        } catch {}
    }
    try {
        if ($null -ne $Item.ModifyDate) { return [datetime]$Item.ModifyDate }
    } catch {}
    return $null
}
function Get-MtpItemLocalTimeText {
    param(
        [Parameter(Mandatory = $true)] $Item,
        [Parameter(Mandatory = $true)] [string[]] $PropertyNames
    )
    foreach ($propertyName in $PropertyNames) {
        try {
            $value = $Item.ExtendedProperty($propertyName)
            if ($null -ne $value) {
                return ([datetime]$value).ToLocalTime().ToString("yyyy-MM-dd HH:mm:ss")
            }
        } catch {}
    }
    return ""
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
$cutoff = $null
if ($CutoffModifiedAt.Trim()) {
    $cutoff = [datetime]::Parse($CutoffModifiedAt, [Globalization.CultureInfo]::InvariantCulture)
}
$skipRefs = @{}
if ($SkipRefsPath.Trim() -and (Test-Path -LiteralPath $SkipRefsPath)) {
    $rawSkipRefs = Get-Content -LiteralPath $SkipRefsPath -Raw | ConvertFrom-Json
    foreach ($skipRef in $rawSkipRefs) { $skipRefs[[string]$skipRef] = $true }
}
$records = @()
:albumLoop foreach ($album in Get-ShellFolderItems -Folder $dcim) {
    if (-not $album.IsFolder) { continue }
    foreach ($media in Get-ShellFolderItems -Folder $album.GetFolder) {
        if ($media.IsFolder) { continue }
        $mediaRef = "$($album.Name)/$($media.Name)"
        if ($skipRefs.ContainsKey($mediaRef)) { continue }
        $mediaModifiedAt = Get-MtpItemModifiedAt -Item $media
        if ($null -ne $cutoff -and $null -ne $mediaModifiedAt -and $mediaModifiedAt -ge $cutoff) { continue }
        $copied = Copy-MtpItem -Shell $shell -Item $media -Album $album.Name -TempDir $TempDir
        if ($null -eq $copied) { continue }
        if ($null -ne $cutoff -and $copied.LastWriteTime -ge $cutoff) { continue }
        $createdAt = Get-MtpItemLocalTimeText -Item $media -PropertyNames @("System.DateCreated", "System.Photo.DateTaken", "System.ItemDate")
        $modifiedAt = Get-MtpItemLocalTimeText -Item $media -PropertyNames @("System.DateModified", "System.ItemDate", "System.Photo.DateTaken")
        $records += [ordered]@{
            device_id = $target.Name
            device_name = $target.Name
            album = $album.Name
            filename = $media.Name
            temp_path = $copied.FullName
            size = $copied.Length
            created_at = $createdAt
            modified_at = if ($modifiedAt) { $modifiedAt } else { $copied.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss") }
        }
        if ($Limit -gt 0 -and $records.Count -ge $Limit) { break albumLoop }
    }
}
$records | ConvertTo-Json -Depth 4 -Compress
"""
    script_path = temp_dir / "iphone_index_copy.ps1"
    skip_refs_path = temp_dir / "iphone_skip_refs.json"
    script_path.write_text(script, encoding="utf-8")
    skip_refs_path.write_text(json.dumps(skip_refs or [], ensure_ascii=False), encoding="utf-8")
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
            "-Limit",
            str(limit),
            "-CutoffModifiedAt",
            cutoff_modified_at,
            "-SkipRefsPath",
            str(skip_refs_path),
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


def _parse_iphone_target(target: str) -> tuple[str, str]:
    normalized = str(target or "").replace("\\", "/").strip().strip("/")
    if not normalized:
        raise HTTPException(status_code=400, detail="iPhone photo target is required")
    parts = [part.strip() for part in normalized.split("/") if part.strip()]
    if len(parts) == 1:
        return "", parts[0]
    if len(parts) == 2:
        return parts[0], parts[1]
    raise HTTPException(status_code=400, detail="Use filename or album/filename")


def _delete_iphone_media(device_id: str, album: str, filename: str) -> dict[str, Any]:
    script = r"""
param(
    [Parameter(Mandatory = $true)] [string] $DeviceId,
    [string] $Album = "",
    [Parameter(Mandatory = $true)] [string] $Filename
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
$shell = New-Object -ComObject Shell.Application
$thisPc = $shell.Namespace(17)
if ($null -eq $thisPc) { throw "Cannot open Shell namespace for This PC." }
$targetDevice = $null
foreach ($item in Get-ShellFolderItems -Folder $thisPc) {
    if ($item.IsFolder -and ($item.Name -eq $DeviceId -or $item.Name -match "iPhone|Apple|iPad")) {
        $targetDevice = $item
        if ($item.Name -eq $DeviceId) { break }
    }
}
if ($null -eq $targetDevice) { throw "iPhone device not found: $DeviceId" }
$dcim = Find-DcimFolder -Device $targetDevice
if ($null -eq $dcim) { throw "DCIM folder not found." }
$matched = @()
foreach ($albumItem in Get-ShellFolderItems -Folder $dcim) {
    if (-not $albumItem.IsFolder) { continue }
    if ($Album.Trim() -and $albumItem.Name -ine $Album) { continue }
    foreach ($media in Get-ShellFolderItems -Folder $albumItem.GetFolder) {
        if ($media.IsFolder) { continue }
        if ($media.Name -ieq $Filename) {
            $matched += [ordered]@{ album = $albumItem.Name; filename = $media.Name; item = $media }
        }
    }
}
if ($matched.Count -lt 1) { throw "iPhone photo not found: $Filename" }
if ($matched.Count -gt 1) { throw "Multiple iPhone photos matched. Use album/filename." }
$target = $matched[0]
$target.item.InvokeVerb("delete")
Start-Sleep -Milliseconds 500
[ordered]@{
    device_id = $targetDevice.Name
    album = $target.album
    filename = $target.filename
    deleted = $true
} | ConvertTo-Json -Depth 3 -Compress
"""
    with tempfile.TemporaryDirectory(prefix="ztb_iphone_delete_") as temp_name:
        script_path = Path(temp_name) / "iphone_delete.ps1"
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
                "-Album",
                album,
                "-Filename",
                filename,
            ],
            capture_output=True,
            check=False,
            encoding="utf-8",
            errors="replace",
            timeout=IPHONE_DELETE_TIMEOUT_SECONDS,
        )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "iPhone delete failed")
    output = completed.stdout.strip()
    return json.loads(output) if output else {}


def _find_existing_strict_duplicate(hash_db: dict[str, dict[str, list[str]]], strict_hash: str, gallery_root: Path) -> str:
    gallery_root = gallery_root.resolve()
    for candidate in hash_db.get("strict", {}).get(strict_hash, []):
        try:
            candidate_path = Path(candidate).expanduser().resolve()
            candidate_path.relative_to(gallery_root)
        except (OSError, ValueError):
            continue
        if candidate_path.is_file():
            return str(candidate_path)
    return ""


def _import_staged_iphone_media(
    staged_path: Path,
    filename: str,
    gallery_root: Path,
    created_at: str = "",
    modified_at: str = "",
) -> Path:
    target_date = get_target_date(str(staged_path))
    target_dir = Path(build_date_path(str(gallery_root), target_date))
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = Path(get_unique_path(str(target_dir), filename))
    transfer_file(staged_path, target_path, "copy")
    _apply_iphone_file_times(target_path, created_at, modified_at)
    return target_path


def _parse_iphone_local_time(value: str) -> datetime | None:
    value = str(value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _datetime_to_windows_filetime_parts(value: datetime) -> tuple[int, int]:
    filetime = int((value.timestamp() + 11644473600) * 10_000_000)
    return filetime & 0xFFFFFFFF, filetime >> 32


def _apply_iphone_file_times(path: Path, created_at: str = "", modified_at: str = "") -> None:
    if platform.system().lower() != "windows":
        return
    times = read_windows_file_times(path)
    if not times:
        return
    existing_created, accessed, existing_written = times
    created_dt = _parse_iphone_local_time(created_at)
    modified_dt = _parse_iphone_local_time(modified_at)
    created = _datetime_to_windows_filetime_parts(created_dt) if created_dt else existing_created
    written = _datetime_to_windows_filetime_parts(modified_dt) if modified_dt else existing_written
    apply_windows_file_times(path, (created, accessed, written))


def _invalidate_gallery_index(root: Path) -> None:
    clear_image_list_cache(root)
    index_dir = root_image_index_dir(root)
    cache_key = image_scan_cache_key(root, SUPPORTED_EXTENSIONS, SKIP_SCAN_DIR_NAMES)
    cache_digest = digest_for_cache_key(cache_key)
    ImageIndexRepository(root_database_path(root)).delete_index(cache_digest)
    for cache_path in (
        image_index_cache_path(index_dir, cache_key),
        image_index_summary_path(index_dir, cache_key),
        timeline_index_cache_path(index_dir, cache_key),
    ):
        try:
            cache_path.unlink()
        except OSError:
            pass


def _existing_local_path_for_record(records: list[dict[str, Any]], album: str, filename: str) -> str:
    for record in records:
        if str(record.get("album", "")) != album or str(record.get("filename", "")) != filename:
            continue
        local_path = str(record.get("local_path") or record.get("existing_local_path") or "").strip()
        if local_path and Path(local_path).expanduser().is_file():
            return local_path
    return ""


def _existing_iphone_refs(records: list[dict[str, Any]]) -> list[str]:
    refs: list[str] = []
    for record in records:
        album = str(record.get("album", "")).strip()
        filename = str(record.get("filename", "")).strip()
        local_path = str(record.get("local_path") or record.get("existing_local_path") or "").strip()
        if album and filename and local_path and Path(local_path).expanduser().is_file():
            refs.append(f"{album}/{filename}")
    return refs


def build_iphone_photo_index(
    device_id: str,
    limit: int = IPHONE_INDEX_DEFAULT_LIMIT,
    copy_all: bool = False,
) -> dict[str, Any]:
    if platform.system().lower() != "windows":
        return {"status": "unsupported", "indexed": 0, "message": "iPhone MTP indexing is only supported on Windows."}

    normalized_device_id = str(device_id or "").strip()
    if not normalized_device_id:
        raise HTTPException(status_code=400, detail="Device id is required")
    requested_limit = max(1, min(int(limit or IPHONE_INDEX_DEFAULT_LIMIT), IPHONE_INDEX_MAX_LIMIT))
    copy_limit = 0 if copy_all else requested_limit

    settings = load_settings()
    active_root = Path(settings["active_root"]).expanduser().resolve()
    database_path = root_database_path(active_root)
    hash_repository = HashDbRepository(database_path)
    mobile_repository = MobileRepository(database_path)
    import_records_before = mobile_repository.list_import_records("iphone", normalized_device_id)
    skip_refs = _existing_iphone_refs(import_records_before)

    indexed_at = datetime.now(timezone.utc).isoformat()
    indexed_records: list[dict[str, Any]] = []
    import_status = "indexed"
    imported_path = ""
    existing_local_path = ""
    imported_at = ""
    imported_count = 0
    skipped_duplicate_count = 0
    already_imported_count = 0
    imported_any = False
    with tempfile.TemporaryDirectory(prefix="ztb_iphone_index_") as temp_name:
        staging_dir = Path(temp_name) / "staging"
        staging_dir.mkdir(parents=True, exist_ok=True)
        copied_records = _copy_iphone_media_for_index(
            normalized_device_id,
            staging_dir,
            "",
            skip_refs,
            copy_limit,
        )
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
        mobile_repository.save_index(
            device_type="iphone",
            device_id=normalized_device_id,
            device_name=str(device_name),
            indexed_at=indexed_at,
            records=indexed_records,
        )

        for record in indexed_records:
            imported_at = datetime.now(timezone.utc).isoformat()
            strict_hash = str(record.get("strict_hash", ""))
            album = str(record.get("album", ""))
            filename = str(record.get("filename", ""))
            already_local_path = _existing_local_path_for_record(import_records_before, album, filename)
            if already_local_path:
                imported_path = already_local_path
                already_imported_count += 1
                continue

            existing_local_path = _find_existing_strict_duplicate(
                hash_repository.load_hash_db(),
                strict_hash,
                active_root,
            )
            if existing_local_path:
                skipped_duplicate_count += 1
                mobile_repository.mark_skipped_duplicate(
                    device_type="iphone",
                    device_id=normalized_device_id,
                    album=album,
                    filename=filename,
                    existing_local_path=existing_local_path,
                    imported_at=imported_at,
                )
            else:
                staged_path = Path(str(record.get("temp_path", "")))
                imported = _import_staged_iphone_media(
                    staged_path,
                    filename,
                    active_root,
                    str(record.get("created_at", "")),
                    str(record.get("modified_at", "")),
                )
                imported_path = str(imported)
                hash_repository.add_hash_record("strict", strict_hash, imported_path)
                mobile_repository.mark_imported(
                    device_type="iphone",
                    device_id=normalized_device_id,
                    album=album,
                    filename=filename,
                    local_path=imported_path,
                    imported_at=imported_at,
                )
                imported_count += 1
                imported_any = True

        if imported_any:
            _invalidate_gallery_index(active_root)

        if imported_count:
            import_status = "imported"
        elif skipped_duplicate_count:
            import_status = "skipped_duplicate"
        elif already_imported_count:
            import_status = "already_imported"

    device_name = indexed_records[0].get("device_name", normalized_device_id) if indexed_records else normalized_device_id
    albums = {str(item.get("album", "")) for item in indexed_records if str(item.get("album", "")).strip()}
    return {
        "status": import_status,
        "device_id": normalized_device_id,
        "device_name": str(device_name),
        "album_count": len(albums),
        "indexed": len(indexed_records),
        "imported": imported_count,
        "skipped_duplicate": skipped_duplicate_count,
        "already_imported": already_imported_count,
        "local_path": imported_path,
        "existing_local_path": existing_local_path,
        "skipped_existing_refs": len(skip_refs),
        "limit": requested_limit,
        "copy_all": bool(copy_all),
        "indexed_at": indexed_at,
        "imported_at": imported_at,
        "database_path": str(database_path),
    }


def delete_iphone_photo(device_id: str, target: str) -> dict[str, Any]:
    if platform.system().lower() != "windows":
        return {"status": "unsupported", "deleted": False, "message": "iPhone MTP deletion is only supported on Windows."}

    normalized_device_id = str(device_id or "").strip()
    if not normalized_device_id:
        raise HTTPException(status_code=400, detail="Device id is required")

    album, filename = _parse_iphone_target(target)
    try:
        deleted = _delete_iphone_media(normalized_device_id, album, filename)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    deleted_at = datetime.now(timezone.utc).isoformat()
    settings = load_settings()
    active_root = Path(settings["active_root"]).expanduser().resolve()
    MobileRepository(root_database_path(active_root)).mark_deleted_from_device(
        device_type="iphone",
        device_id=normalized_device_id,
        album=str(deleted.get("album", album)),
        filename=str(deleted.get("filename", filename)),
        deleted_at=deleted_at,
    )
    return {
        "status": "deleted",
        "deleted": True,
        "device_id": str(deleted.get("device_id", normalized_device_id)),
        "album": str(deleted.get("album", album)),
        "filename": str(deleted.get("filename", filename)),
        "deleted_at": deleted_at,
    }


def detect_mobile_devices(device_type: str = "iphone") -> dict[str, Any]:
    normalized_type = _normalize_mobile_device_type(device_type)
    result = detect_iphone_devices()
    return {**result, "device_type": normalized_type}


def probe_mobile_item_properties(device_type: str, device_id: str) -> dict[str, Any]:
    normalized_type = _normalize_mobile_device_type(device_type)
    result = probe_iphone_item_properties(device_id)
    return {**result, "device_type": normalized_type}


def build_mobile_photo_index(
    device_type: str,
    device_id: str,
    limit: int = IPHONE_INDEX_DEFAULT_LIMIT,
    copy_all: bool = False,
) -> dict[str, Any]:
    normalized_type = _normalize_mobile_device_type(device_type)
    result = build_iphone_photo_index(device_id, limit=limit, copy_all=copy_all)
    return {**result, "device_type": normalized_type}


def delete_mobile_photo(device_type: str, device_id: str, target: str) -> dict[str, Any]:
    normalized_type = _normalize_mobile_device_type(device_type)
    result = delete_iphone_photo(device_id, target)
    return {**result, "device_type": normalized_type}
