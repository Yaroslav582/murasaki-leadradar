$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-File", (Join-Path $root "run-backend.ps1")
) -WindowStyle Normal

Start-Sleep -Seconds 2

Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-File", (Join-Path $root "run-frontend.ps1")
) -WindowStyle Normal

Write-Host "Backend  -> http://127.0.0.1:8000/docs" -ForegroundColor Green
Write-Host "Frontend -> http://localhost:3000" -ForegroundColor Green
