param(
    [string]$OutputDirectory = "release"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
if (-not (Test-Path .venv\Scripts\python.exe)) { throw "Run .\scripts\setup.ps1 first." }
if (-not (Test-Path frontend\node_modules)) { throw "Frontend dependencies are missing. Run .\scripts\setup.ps1 first." }

& .\.venv\Scripts\python.exe -m pytest backend\tests
if ($LASTEXITCODE -ne 0) { throw "Backend tests failed; release was not packaged." }
Push-Location backend
try {
    & ..\.venv\Scripts\alembic.exe upgrade head
    if ($LASTEXITCODE -ne 0) { throw "Database migration failed; release was not packaged." }
}
finally { Pop-Location }
Push-Location frontend
try {
    npm run typecheck
    if ($LASTEXITCODE -ne 0) { throw "Frontend typecheck failed; release was not packaged." }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed; release was not packaged." }
}
finally { Pop-Location }

$releaseRoot = Join-Path $root $OutputDirectory
$release = Join-Path $releaseRoot "signal-atlas-$(Get-Date -Format yyyyMMdd-HHmmss)"
New-Item -ItemType Directory -Force -Path $release | Out-Null
Copy-Item frontend\dist (Join-Path $release "frontend") -Recurse
Copy-Item backend\app (Join-Path $release "backend-app") -Recurse
Copy-Item backend\migrations (Join-Path $release "migrations") -Recurse
Copy-Item backend\requirements.txt (Join-Path $release "requirements.txt")
Copy-Item backend\pyproject.toml (Join-Path $release "pyproject.toml")
Copy-Item scripts (Join-Path $release "scripts") -Recurse
Copy-Item docs (Join-Path $release "docs") -Recurse
Copy-Item .env.example (Join-Path $release ".env.example")
@"
Signal Atlas Windows release
Created: $(Get-Date -Format o)
The release is a native Windows bundle. Configure secrets and optional PostgreSQL/Neo4j services before use.
"@ | Set-Content (Join-Path $release "MANIFEST.txt")
Write-Host "Release written to $release" -ForegroundColor Green
