param(
    [switch]$SkipFrontend
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "Running backend verification..." -ForegroundColor Cyan
& .\.venv\Scripts\python.exe -m pytest backend\tests

if (-not $SkipFrontend) {
    Write-Host "Running frontend typecheck..." -ForegroundColor Cyan
    Push-Location frontend
    try {
        npm run typecheck
        npm run build
    }
    finally {
        Pop-Location
    }
}

Write-Host "Verification passed." -ForegroundColor Green
