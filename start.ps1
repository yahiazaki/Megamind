# Starts Megamind locally: makes sure Ollama is running, builds the frontend if needed, then serves on :8000.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:Path = "C:\Program Files\nodejs;$env:LOCALAPPDATA\Programs\Ollama;" + $env:Path

try { Invoke-RestMethod http://127.0.0.1:11434/api/version -TimeoutSec 2 | Out-Null }
catch {
    Write-Host "Starting Ollama..."
    Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep 3
}

if (-not (Test-Path "$root\frontend\dist\index.html")) {
    Write-Host "Building the frontend..."
    Push-Location "$root\frontend"; npm install; npm run build; Pop-Location
}

Write-Host "Megamind running at http://localhost:8000  (admin: http://localhost:8000/admin)"
Push-Location "$root\backend"
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
Pop-Location
