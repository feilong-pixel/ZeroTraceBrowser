Set-Location -Path $PSScriptRoot

$localHosts = @("localhost", "127.0.0.1", "::1")
$lanHosts = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -and $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } |
    Select-Object -ExpandProperty IPAddress
$env:ZTB_TRUSTED_HOSTS = ($localHosts + $lanHosts | Select-Object -Unique) -join ","

Write-Host "ZeroTraceBrowser trusted hosts: $env:ZTB_TRUSTED_HOSTS"
Write-Host "LAN access: http://<one-of-the-above-ip>:8000/"
~\.virtualenvs\venv\Scripts\python.exe -m uvicorn app:app --host 0.0.0.0 --port 8000
exit $LASTEXITCODE
