param(
    [switch]$SkipFrontend,
    [switch]$Camera
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "Running backend verification..." -ForegroundColor Cyan
& .\.venv\Scripts\python.exe -m pytest backend\tests

if ($Camera) {
    Write-Host "Running the live camera end-to-end walkthrough..." -ForegroundColor Cyan
    Write-Host "The backend must be running with CNI_CAMERA_DEMO_MODE=true for scripted events." -ForegroundColor Yellow
    & .\.venv\Scripts\python.exe scripts\verify-camera-e2e.py
}

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
