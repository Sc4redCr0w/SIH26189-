<#
.SYNOPSIS
Registers the three prototype demo camera sources against a running backend.

.DESCRIPTION
Creates a demonstration camera set that runs without physical CCTV hardware:

  1. Demo Camera 01 - WEBCAM (laptop webcam index 0)      - Main Gate
  2. Demo Camera 02 - VIDEO_FILE (generated synthetic clip) - Parking Area
  3. Demo Camera 03 - VIDEO_FILE (generated synthetic clip) - Building Entrance

The two video sources are synthetic footage. Real face detection requires a
real face (webcam or an MP4 that contains a person). The generated clips are
used with DEMO SIMULATION MODE, which produces clearly labeled simulated
events. Simulated events are not biometric identification and a human reviewer
must approve any association.

.EXAMPLE
.\scripts\setup-camera-demo.ps1
.\scripts\setup-camera-demo.ps1 -Start -DemoMode
#>
[CmdletBinding()]
param(
    [string]$ApiBase = "http://127.0.0.1:8000/api/v1",
    [string]$Username = "admin",
    [string]$Password = "ChangeMe-Admin-2026!",
    [switch]$Start,
    [switch]$DemoMode,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"

function Write-Step { param([string]$Message) Write-Host "==> $Message" -ForegroundColor Cyan }
function Write-Ok { param([string]$Message) Write-Host "    $Message" -ForegroundColor Green }

if (-not (Test-Path $python)) {
    throw "Virtual environment not found. Run .\scripts\setup.ps1 first."
}

Write-Step "Checking backend availability"
try {
    $health = Invoke-RestMethod -Uri "$ApiBase/health" -Method Get -TimeoutSec 5
    Write-Ok "Backend responded: $($health.status)"
} catch {
    throw "Backend is not reachable at $ApiBase. Start it with .\scripts\start-backend.ps1"
}

Write-Step "Ensuring synthetic demo media exists"
& $python (Join-Path $PSScriptRoot "generate_camera_demo_media.py")
if ($LASTEXITCODE -ne 0) { throw "Demo media generation failed." }

Write-Step "Authenticating as $Username"
$loginBody = @{ username = $Username; password = $Password } | ConvertTo-Json
$login = Invoke-RestMethod -Uri "$ApiBase/auth/login" -Method Post -ContentType "application/json" -Body $loginBody
$headers = @{ Authorization = "Bearer $($login.access_token)" }
Write-Ok "Authenticated."

$existing = Invoke-RestMethod -Uri "$ApiBase/cameras" -Method Get -Headers $headers
if ($existing.Count -gt 0 -and -not $Force) {
    Write-Host "    $($existing.Count) camera(s) already exist. Use -Force to register the demo set again." -ForegroundColor Yellow
    $existing | ForEach-Object { Write-Host "    - $($_.id)  $($_.camera_name)  [$($_.source_type)]" }
    return
}

$demoEvent = {
    param([double]$Seconds, [string]$Label, [string]$PersonId)
    [pscustomobject]@{
        timestamp_seconds   = $Seconds
        bbox                = [pscustomobject]@{ x = 360; y = 180; width = 120; height = 180 }
        confidence          = 0.97
        label               = $Label
        suggested_person_id = $PersonId
    }
}

$cameras = @(
    @{
        camera_name = "Demo Camera 01 - Main Gate"
        source_type = "WEBCAM"
        source_uri = "0"
        location_name = "Main Gate"
        timezone = "Asia/Kolkata"
        description = "Laptop webcam used as the primary live detection source."
        metadata = @{}
    },
    @{
        camera_name = "Demo Camera 02 - Parking"
        source_type = "VIDEO_FILE"
        source_uri = "datasets/camera_demo/demo-parking.mp4"
        location_name = "Parking Area"
        timezone = "Asia/Kolkata"
        description = "Synthetic looping clip used to demonstrate independent multi-source capture."
        metadata = @{ demo_events = @(& $demoEvent 4.0 "Potential match event - SIMULATED" "ENT-DEMO-P1001") }
    },
    @{
        camera_name = "Demo Camera 03 - Entrance"
        source_type = "VIDEO_FILE"
        source_uri = "datasets/camera_demo/demo-entrance.mp4"
        location_name = "Building Entrance"
        timezone = "Asia/Kolkata"
        description = "Synthetic looping clip used to demonstrate independent multi-source capture."
        metadata = @{ demo_events = @(& $demoEvent 6.0 "Potential match event - SIMULATED" "ENT-DEMO-P2004") }
    }
)

$created = @()
foreach ($camera in $cameras) {
    Write-Step "Registering $($camera.camera_name)"
    $body = $camera | ConvertTo-Json -Depth 8
    $response = Invoke-RestMethod -Uri "$ApiBase/cameras" -Method Post -Headers $headers -ContentType "application/json" -Body $body
    $created += $response
    Write-Ok "$($response.id)  $($response.source_type)  $($response.source_uri_masked)"
}

if ($DemoMode) {
    Write-Step "DEMO SIMULATION MODE requested"
    Write-Host "    Set CNI_CAMERA_DEMO_MODE=true in .env and restart the backend before starting streams." -ForegroundColor Yellow
}

if ($Start) {
    foreach ($camera in $created) {
        Write-Step "Starting $($camera.camera_name)"
        try {
            $status = Invoke-RestMethod -Uri "$ApiBase/cameras/$($camera.id)/start" -Method Post -Headers $headers
            Write-Ok "status=$($status.status)"
        } catch {
            Write-Host "    Start failed: $($_.Exception.Message)" -ForegroundColor Yellow
        }
    }
}

Write-Step "Camera demo set ready"
Write-Host "    Open http://127.0.0.1:5173/monitoring for the live grid."
Write-Host "    Open http://127.0.0.1:5173/monitoring/review for the human review queue."
Write-Host "    Face detection is detection only. Identity association always requires a human reviewer."
