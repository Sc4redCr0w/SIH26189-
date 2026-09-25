$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root\frontend

if (-not (Test-Path node_modules)) {
    throw "Frontend dependencies are not installed. Run .\scripts\setup.ps1 first."
}

$listener = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($listener) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)" -ErrorAction SilentlyContinue
    $commandLine = [string]$process.CommandLine
    if ($commandLine -like "*SIH26189-*vite*") {
        Write-Host "Signal Atlas frontend is already running at http://127.0.0.1:5173" -ForegroundColor Green
        Write-Host "Existing PID: $($listener.OwningProcess)" -ForegroundColor DarkGray
        exit 0
    }
    throw "Port 5173 is already used by PID $($listener.OwningProcess). Stop that process or run: npm run dev -- --port 5174"
}

npm run dev
