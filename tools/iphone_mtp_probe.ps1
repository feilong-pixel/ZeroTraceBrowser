param(
    [switch] $HashFirstSample
)

$ErrorActionPreference = "Stop"

function Get-ShellFolderItems {
    param(
        [Parameter(Mandatory = $true)]
        $Folder
    )

    $items = @()
    foreach ($item in $Folder.Items()) {
        $items += $item
    }
    return $items
}

function Get-ShellItemDetails {
    param(
        [Parameter(Mandatory = $true)]
        $Folder,
        [Parameter(Mandatory = $true)]
        $Item,
        [int[]] $Columns = @(0, 1, 2, 3, 4, 10, 11, 12, 13, 14, 15, 21, 27, 28, 30, 31, 164)
    )

    $details = [ordered]@{}
    foreach ($column in $Columns) {
        $name = $Folder.GetDetailsOf($null, $column)
        $value = $Folder.GetDetailsOf($Item, $column)
        if ([string]::IsNullOrWhiteSpace($name) -or [string]::IsNullOrWhiteSpace($value)) {
            continue
        }
        $details[$name] = $value
    }
    return $details
}

function Find-ChildFolder {
    param(
        [Parameter(Mandatory = $true)]
        $Folder,
        [Parameter(Mandatory = $true)]
        [string] $Name
    )

    foreach ($item in Get-ShellFolderItems -Folder $Folder) {
        if (-not $item.IsFolder) {
            continue
        }
        if ($item.Name -ieq $Name) {
            return $item.GetFolder
        }
    }
    return $null
}

function Find-FirstFolderPath {
    param(
        [Parameter(Mandatory = $true)]
        $Folder,
        [Parameter(Mandatory = $true)]
        [string[]] $Names
    )

    $current = $Folder
    foreach ($name in $Names) {
        $current = Find-ChildFolder -Folder $current -Name $name
        if ($null -eq $current) {
            return $null
        }
    }
    return $current
}

function Write-DeviceSummary {
    param(
        [Parameter(Mandatory = $true)]
        $ThisPc,
        [Parameter(Mandatory = $true)]
        $Device
    )

    Write-Host ""
    Write-Host "Device: $($Device.Name)"
    $details = Get-ShellItemDetails -Folder $ThisPc -Item $Device
    foreach ($key in $details.Keys) {
        Write-Host "  ${key}: $($details[$key])"
    }
}

function Write-DcimSummary {
    param(
        [Parameter(Mandatory = $true)]
        $Device,
        [switch] $HashFirstSample
    )

    $deviceFolder = $Device.GetFolder
    $dcim = Find-FirstFolderPath -Folder $deviceFolder -Names @("Internal Storage", "DCIM")
    if ($null -eq $dcim) {
        $dcim = Find-ChildFolder -Folder $deviceFolder -Name "DCIM"
    }

    if ($null -eq $dcim) {
        Write-Host "  DCIM: not found"
        return
    }

    Write-Host "  DCIM: found"
    $albumCount = 0
    $sampleCount = 0
    foreach ($album in Get-ShellFolderItems -Folder $dcim) {
        if (-not $album.IsFolder) {
            continue
        }
        $albumCount += 1
        Write-Host "  Album: $($album.Name)"
        foreach ($media in Get-ShellFolderItems -Folder $album.GetFolder) {
            if ($media.IsFolder) {
                continue
            }
            $sampleCount += 1
            Write-Host "    Sample: $($media.Name)"
            $details = Get-ShellItemDetails -Folder $album.GetFolder -Item $media
            foreach ($key in $details.Keys) {
                Write-Host "      ${key}: $($details[$key])"
            }
            if ($HashFirstSample -and $sampleCount -eq 1) {
                Test-MediaReadHash -Item $media
            }
            if ($sampleCount -ge 5) {
                break
            }
        }
        if ($sampleCount -ge 5) {
            break
        }
    }
    Write-Host "  Albums scanned: $albumCount"
    Write-Host "  Media samples: $sampleCount"
}

function Test-MediaReadHash {
    param(
        [Parameter(Mandatory = $true)]
        $Item
    )

    $probeDir = Join-Path ([System.IO.Path]::GetTempPath()) ("ztb_iphone_probe_" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $probeDir | Out-Null
    try {
        $destination = (New-Object -ComObject Shell.Application).Namespace($probeDir)
        $before = @{}
        Get-ChildItem -LiteralPath $probeDir -Force | ForEach-Object { $before[$_.FullName] = $true }
        $destination.CopyHere($Item, 16)

        $copied = $null
        $deadline = (Get-Date).AddSeconds(30)
        while ((Get-Date) -lt $deadline) {
            Start-Sleep -Milliseconds 300
            $copied = Get-ChildItem -LiteralPath $probeDir -File -Force |
                Where-Object { -not $before.ContainsKey($_.FullName) } |
                Sort-Object LastWriteTime -Descending |
                Select-Object -First 1
            if ($null -ne $copied -and $copied.Length -gt 0) {
                break
            }
        }

        if ($null -eq $copied) {
            Write-Host "      Hash probe: copy timeout"
            return
        }

        $hash = Get-FileHash -Algorithm SHA256 -LiteralPath $copied.FullName
        Write-Host "      Hash probe copied bytes: $($copied.Length)"
        Write-Host "      Hash probe SHA256: $($hash.Hash.ToLowerInvariant())"
    }
    finally {
        Remove-Item -LiteralPath $probeDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

$shell = New-Object -ComObject Shell.Application
$thisPc = $shell.Namespace(17)
if ($null -eq $thisPc) {
    throw "Cannot open Shell namespace for This PC."
}

$devices = @()
foreach ($item in Get-ShellFolderItems -Folder $thisPc) {
    if ($item.IsFolder -and $item.Name -match "iPhone|Apple|iPad") {
        $devices += $item
    }
}

Write-Host "iPhone-like devices found: $($devices.Count)"
foreach ($device in $devices) {
    Write-DeviceSummary -ThisPc $thisPc -Device $device
    Write-DcimSummary -Device $device -HashFirstSample:$HashFirstSample
}
