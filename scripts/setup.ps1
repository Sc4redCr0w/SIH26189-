param(
    [switch]$SkipFrontend
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "Signal Atlas Windows setup" -ForegroundColor Cyan
Write-Host "Repository: $root"

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    throw "Python 3.12+ was not found. Install it with: winget install --id Python.Python.3.12 --exact --scope user"
}

python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt

if (-not $SkipFrontend) {
    $node = Get-Command node -ErrorAction SilentlyContinue
    $npm = Get-Command npm -ErrorAction SilentlyContinue
    if (-not $node -or -not $npm) {
        throw "Node.js 20+ and npm were not found. Install Node.js from https://nodejs.org/ and reopen PowerShell."
    }
    Push-Location frontend
    try {
        npm install
    }
    finally {
        Pop-Location
    }
}

if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Host "Created .env from .env.example. Change the seed passwords before sharing the app." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Start the API:  .\scripts\start-backend.ps1"
Write-Host "Start the UI:   .\scripts\start-frontend.ps1"
Write-Host "Verify:         .\scripts\verify.ps1"
