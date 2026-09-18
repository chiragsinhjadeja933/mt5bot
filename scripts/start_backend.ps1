#!/usr/bin/env pwsh
# Start backend (runs in this window)
Set-Location "$PSScriptRoot\..\backend"
if (!(Test-Path ".env") -and (Test-Path "..\.env")) {
    Copy-Item "..\.env" ".env"
} elseif (!(Test-Path ".env")) {
    Copy-Item "..\.env.example" ".env"
    Write-Host "Created .env. Please configure it before running."
}
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
