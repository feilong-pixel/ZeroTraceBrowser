Set-Location -Path $PSScriptRoot

.\venv\Scripts\python.exe -m pytest -q
exit $LASTEXITCODE
