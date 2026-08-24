$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$backendScript = Join-Path $root "run_backend.ps1"
$frontendScript = Join-Path $root "run_frontend.ps1"
$frontendIndex = Join-Path $root "frontend\index.html"
$frontendPackage = Join-Path $root "frontend\package.json"

Write-Host "TABLEAU2PBI automated start" -ForegroundColor Cyan
Write-Host "Root: $root"

if (!(Test-Path $backendScript)) { throw "Missing run_backend.ps1 at $backendScript" }
if (!(Test-Path $frontendScript)) { throw "Missing run_frontend.ps1 at $frontendScript" }
if (!(Test-Path $frontendIndex)) { throw "Missing frontend/index.html. Re-extract the application ZIP into a clean folder." }
if (!(Test-Path $frontendPackage)) { throw "Missing frontend/package.json. Re-extract the application ZIP into a clean folder." }

# Stop only known TABLEAU2PBI listener ports so stale versions cannot be served.
8000,5173,5174,5175 | ForEach-Object {
    $port = $_
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($conn in $conns) {
        try {
            $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
            Write-Host ("Stopping stale process on port {0}: PID {1} {2}" -f $port, $conn.OwningProcess, $proc.ProcessName) -ForegroundColor Yellow
            Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
        } catch {}
    }
}
Start-Sleep -Seconds 1

$runtime = "C:\T2PBI_RUNTIME\workspace"
New-Item -ItemType Directory -Force -Path $runtime | Out-Null
Write-Host "Runtime workspace: $runtime" -ForegroundColor Cyan

Write-Host "Starting backend..." -ForegroundColor Green
Start-Process powershell.exe -WorkingDirectory $root -ArgumentList @(
    "-NoProfile", "-ExecutionPolicy", "Bypass", "-NoExit", "-File", $backendScript
)

# Do not start/open the UI until the API is actually reachable. First-run pip
# installation can take longer than a fixed 8-second sleep.
$backendReady = $false
for ($i = 0; $i -lt 180; $i++) {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 2 -ErrorAction Stop
        if ($health.status -eq "ok") { $backendReady = $true; break }
    } catch {}
    if (($i % 10) -eq 0) { Write-Host "Waiting for backend health..." -ForegroundColor DarkGray }
    Start-Sleep -Seconds 1
}
if (!$backendReady) {
    throw "Backend did not become healthy within 180 seconds. Review the backend PowerShell window for the exact error."
}
Write-Host "Backend healthy: http://127.0.0.1:8000/api/health" -ForegroundColor Green

Write-Host "Starting frontend..." -ForegroundColor Green
Start-Process powershell.exe -WorkingDirectory $root -ArgumentList @(
    "-NoProfile", "-ExecutionPolicy", "Bypass", "-NoExit", "-File", $frontendScript
)

$frontendReady = $false
for ($i = 0; $i -lt 90; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:5173/" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        if ($r.StatusCode -eq 200 -and $r.Content -match "TABLEAU2PBI") { $frontendReady = $true; break }
    } catch {}
    if (($i % 10) -eq 0) { Write-Host "Waiting for frontend..." -ForegroundColor DarkGray }
    Start-Sleep -Seconds 1
}
if (!$frontendReady) {
    throw "Frontend did not return index.html on port 5173 within 90 seconds. Review the frontend PowerShell window."
}

Write-Host "Frontend healthy: http://127.0.0.1:5173" -ForegroundColor Green
Write-Host "Opening TABLEAU2PBI..." -ForegroundColor Cyan
Start-Process "http://127.0.0.1:5173/"
Write-Host "Backend docs: http://127.0.0.1:8000/docs" -ForegroundColor Cyan
