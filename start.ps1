# HealthSense - start the demo
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

Write-Host "[HealthSense] starting backend on http://127.0.0.1:5000" -ForegroundColor Cyan

$python = Join-Path $root ".venv312\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "Virtual env not found at $python - falling back to system python" -ForegroundColor Yellow
    $python = "python"
}

# Free port 5000 if anything is squatting on it (e.g. an earlier backend)
$inUse = Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue
if ($inUse) {
    Write-Host "[HealthSense] port 5000 is in use - stopping that process" -ForegroundColor Yellow
    $inUse | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 1
}

# Launch backend in foreground (Flask serves the frontend from / on the same port)
$server = Join-Path $root "backend\server.py"
& $python $server
