$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root\frontend

if (-not (Test-Path node_modules)) {
    throw "Frontend dependencies are not installed. Run .\scripts\setup.ps1 first."
}

npm run dev
