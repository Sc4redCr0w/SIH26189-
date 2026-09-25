param(
    [string]$ApiUrl = "http://127.0.0.1:8000/api/v1",
    [string]$Username = "admin",
    [string]$Password = "ChangeMe-Admin-2026!",
    [string]$CsvPath = "datasets\cdr.csv"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$login = Invoke-RestMethod -Uri "$ApiUrl/auth/login" -Method Post -ContentType "application/json" -Body (@{ username = $Username; password = $Password } | ConvertTo-Json)
$headers = @{ Authorization = "Bearer $($login.access_token)" }
$file = (Resolve-Path $CsvPath).Path
$response = curl.exe -sS -X POST "$ApiUrl/imports/csv" -H "Authorization: Bearer $($login.access_token)" -F "file=@$file;type=text/csv" -F "title=Synthetic CDR import" -F "category=CDR"
$response
