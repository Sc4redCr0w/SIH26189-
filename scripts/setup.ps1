param(
    [switch]$SkipFrontend,
    [switch]$Recreate,
    [string]$PythonPath = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "Signal Atlas Windows setup" -ForegroundColor Cyan
Write-Host "Repository: $root"

$pythonCommand = if ($PythonPath) {
    Get-Command $PythonPath -ErrorAction SilentlyContinue
}
else {
    Get-Command python -ErrorAction SilentlyContinue
}
if (-not $pythonCommand) {
    throw "Python 3.12+ was not found. Install it with: winget install --id Python.Python.3.12 --exact --scope user"
}
$pythonExe = $pythonCommand.Source
$versionText = & $pythonExe -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
$pythonVersion = [Version]$versionText
if ($pythonVersion.Major -lt 3 -or ($pythonVersion.Major -eq 3 -and $pythonVersion.Minor -lt 12)) {
    throw "Python 3.12+ is required. Found $pythonVersion at $pythonExe"
}

$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$needsRecreate = $Recreate
if (-not $needsRecreate -and (Test-Path ".venv\pyvenv.cfg")) {
    $existingVersion = (Get-Content ".venv\pyvenv.cfg" | Where-Object { $_ -like "version=*" } | Select-Object -First 1) -replace "^version=", ""
    if ($existingVersion -and [Version]$existingVersion -ne $pythonVersion) {
        Write-Host "Existing .venv uses Python $existingVersion; recreating it with $pythonVersion." -ForegroundColor Yellow
        $needsRecreate = $true
    }
}
if ($needsRecreate -and (Test-Path ".venv")) {
    Remove-Item .venv -Recurse -Force
}

& $pythonExe -m venv .venv
if ($LASTEXITCODE -ne 0) { throw "Python virtual environment creation failed." }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }
& .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Backend dependency installation failed." }

if (-not $SkipFrontend) {
    $node = Get-Command node -ErrorAction SilentlyContinue
    $npm = Get-Command npm -ErrorAction SilentlyContinue
    if (-not $node -or -not $npm) {
        throw "Node.js 20+ and npm were not found. Install Node.js from https://nodejs.org/ and reopen PowerShell."
    }
    Push-Location frontend
    try {
        npm install
        if ($LASTEXITCODE -ne 0) { throw "Frontend dependency installation failed." }
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
Write-Host "Setup complete. Python: $pythonVersion" -ForegroundColor Green
Write-Host "Start the API:  .\scripts\start-backend.ps1"
Write-Host "Start the UI:   .\scripts\start-frontend.ps1"
Write-Host "Verify:         .\scripts\verify.ps1"
