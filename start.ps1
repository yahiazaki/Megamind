# Starts Megamind locally: makes sure Ollama is running, builds the frontend if needed, then serves on :8000.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:Path = "C:\Program Files\nodejs;$env:LOCALAPPDATA\Programs\Ollama;" + $env:Path

try {
    Invoke-RestMethod http://127.0.0.1:8000/api/health -TimeoutSec 2 | Out-Null
    Write-Host "Megamind is already running - opening it in your browser."
    Start-Process "http://localhost:8000/admin"
    exit 0
} catch {}

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
Write-Host "Keep this window open while you use Megamind. Close it to stop."
# open the browser once the server answers (runs in the background so it doesn't block the server)
Start-Job {
    for ($i = 0; $i -lt 30; $i++) {
        try { Invoke-RestMethod http://127.0.0.1:8000/api/health -TimeoutSec 1 | Out-Null; Start-Process "http://localhost:8000/admin"; break }
        catch { Start-Sleep 1 }
    }
} | Out-Null
Push-Location "$root\backend"
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
Pop-Location
