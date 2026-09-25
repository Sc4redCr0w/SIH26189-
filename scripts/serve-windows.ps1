param(
    [string]$Host = "127.0.0.1",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
if (-not (Test-Path frontend\dist\index.html)) {
    throw "Frontend release is missing. Run .\scripts\build-release.ps1 first."
}
if (-not (Test-Path .venv\Scripts\python.exe)) {
    throw "Python environment is missing. Run .\scripts\setup.ps1 first."
}
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host $Host --port $Port
