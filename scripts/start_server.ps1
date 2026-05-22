# Start the FastAPI app using the project's virtual environment and Hypercorn.
# Usage: .\scripts\start_server.ps1 [-Open]
param(
    [switch]$Open
)

# Ensure we're in the repo root
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -Path (Join-Path $scriptDir "..")

# Activate venv if present
$activate = Join-Path -Path ".venv\Scripts" -ChildPath "Activate.ps1"
if (Test-Path $activate) {
    Write-Host "Activating virtual environment..."
    & $activate
} else {
    Write-Host "Virtual environment not found at .venv. Create one with: python -m venv .venv" -ForegroundColor Yellow
}

# Install pinned dependencies if missing
Write-Host "Installing dependencies from requirements.txt (if needed)..."
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt

# Ensure logs directory exists
if (-not (Test-Path "logs")) { New-Item -ItemType Directory -Path logs | Out-Null }

# Start Hypercorn (no autoreload by default on Windows)
Write-Host "Starting server with Hypercorn at http://127.0.0.1:8000"
& ".venv\Scripts\python.exe" -m hypercorn app.main:app --bind 127.0.0.1:8000 --workers 1 --log-level info --access-logfile logs/access.log --error-logfile logs/error.log

if ($Open) {
    Start-Process "http://127.0.0.1:8000"
}
