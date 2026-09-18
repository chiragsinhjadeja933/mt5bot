#!/usr/bin/env pwsh
# Run all unit tests
Set-Location "$PSScriptRoot\..\backend"
python -m pytest tests/unit/ -v --tb=short --cov=app --cov-report=term-missing
