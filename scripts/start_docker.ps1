param(
    [switch]$Build,
    [switch]$Open
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -Path (Join-Path $scriptDir "..")

if ($Build) {
    Write-Host "Building Docker images..."
    docker compose build
}

Write-Host "Starting Docker Compose stack..."
docker compose up -d

$localUrl = 'http://127.0.0.1:8000'
Write-Host "\nYour application is running at:"
Write-Host "  $localUrl" -ForegroundColor Cyan
Write-Host "\nIf you see the page not loaded yet, wait a few seconds and refresh the browser."

if ($Open) {
    Start-Process $localUrl
}
