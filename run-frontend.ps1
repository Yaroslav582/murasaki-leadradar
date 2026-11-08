$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath (Join-Path $root "frontend")

if (-not (Test-Path "node_modules")) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Cyan
    npm install
}

if (-not $env:BACKEND_API_URL) {
    $env:BACKEND_API_URL = "http://127.0.0.1:8000"
}

Write-Host "UI: http://localhost:3000 (Backend: $env:BACKEND_API_URL)" -ForegroundColor Green
npm run dev
