$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$frontend = Join-Path $root "frontend"

Write-Host "Running TABLEAU2PBI UI/UX Automated Test Suite..." -ForegroundColor Cyan

Set-Location $frontend
if (!(Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm was not found. Please ensure Node.js LTS is installed."
}

if (!(Test-Path "node_modules")) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Yellow
    npm install --no-audit --no-fund
}

Write-Host "Building frontend assets..." -ForegroundColor Cyan
npm run build

Write-Host "Executing UI/UX regression tests..." -ForegroundColor Green
npm test

if ($LASTEXITCODE -eq 0) {
    Write-Host "`nALL UI/UX TESTS PASSED SUCCESSFULLY!" -ForegroundColor Green
} else {
    Write-Host "`nUI/UX TESTS FAILED!" -ForegroundColor Red
    exit 1
}
