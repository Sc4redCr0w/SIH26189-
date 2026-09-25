param(
    [switch]$SkipFrontend
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "Signal Atlas evaluation" -ForegroundColor Cyan
Write-Host "1/3 Backend tests"
& .\.venv\Scripts\python.exe -m pytest backend\tests

if (-not $SkipFrontend) {
    Write-Host "2/3 Frontend typecheck"
    Push-Location frontend
    try {
        npm run typecheck
    }
    finally {
        Pop-Location
    }
    Write-Host "3/3 Frontend production build"
    Push-Location frontend
    try {
        npm run build
    }
    finally {
        Pop-Location
    }
}
else {
    Write-Host "2/3 Frontend checks skipped"
    Write-Host "3/3 Frontend checks skipped"
}

Write-Host "Evaluation commands completed. See docs/evaluation-report.md for scope and limitations." -ForegroundColor Green
