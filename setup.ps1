$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
python -m venv .venv
if ($LASTEXITCODE) { throw 'Virtual environment creation failed' }
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
if ($LASTEXITCODE) { throw 'Dependency installation failed' }
Write-Host 'Ready. Run .\run.ps1 or .\.venv\Scripts\python.exe demo.py'
