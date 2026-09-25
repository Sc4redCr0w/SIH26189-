param(
    [string]$Revision = "head"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $root "backend")

if (-not (Test-Path ..\.venv\Scripts\alembic.exe)) {
    throw "Alembic is not installed. Run .\scripts\setup.ps1 first."
}

& ..\.venv\Scripts\alembic.exe upgrade $Revision
