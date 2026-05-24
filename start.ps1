$ErrorActionPreference = "Stop"

Set-Location -Path (Split-Path -Parent $MyInvocation.MyCommand.Path)

$python = Join-Path $HOME ".virtualenvs\venv\Scripts\python.exe"
$port = 8000

if (-not (Test-Path $python)) {
    Write-Host "ERROR: venv python not found: $python"
    exit 1
}

if (-not (Test-Path ".\app.py")) {
    Write-Host "ERROR: app.py not found in current directory:"
    Get-Location
    exit 1
}

$localHosts = @("localhost", "127.0.0.1", "::1")
$lanHosts = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -and $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } |
    Select-Object -ExpandProperty IPAddress
$env:ZTB_TRUSTED_HOSTS = ($localHosts + $lanHosts | Select-Object -Unique) -join ","

Write-Host "ZeroTraceBrowser trusted hosts: $env:ZTB_TRUSTED_HOSTS"
Write-Host "Local access: http://127.0.0.1:$port/"
Write-Host "LAN access: http://<one-of-the-above-ip>:$port/"

& $python -m uvicorn app:app --host 0.0.0.0 --port $port

exit $LASTEXITCODE
