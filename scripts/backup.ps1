param(
    [string]$Destination = (Join-Path (Get-Location) "backups")
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$target = Join-Path $Destination "signal-atlas-$timestamp"
New-Item -ItemType Directory -Force -Path $target | Out-Null

$database = Join-Path $root "backend\data\cni.db"
if (Test-Path $database) {
    Copy-Item $database (Join-Path $target "cni.db")
}
$uploads = Join-Path $root "backend\storage\uploads"
if (Test-Path $uploads) {
    Copy-Item $uploads (Join-Path $target "uploads") -Recurse
}
@"
Signal Atlas local backup
Created: $(Get-Date -Format o)
Source: $root
Contains: SQLite database (if present) and uploaded evidence (if present)
Secrets are intentionally not included.
"@ | Set-Content (Join-Path $target "MANIFEST.txt")
Write-Host "Backup written to $target" -ForegroundColor Green
