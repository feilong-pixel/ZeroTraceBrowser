# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import platform
import subprocess
from typing import Any


IPHONE_DEVICE_PROBE_TIMEOUT_SECONDS = 20


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
