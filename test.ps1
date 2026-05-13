Set-Location -Path $PSScriptRoot

$python = Join-Path $HOME ".virtualenvs\venv\Scripts\python.exe"
& $python -m pytest -q
exit $LASTEXITCODE
