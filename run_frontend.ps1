$ErrorActionPreference = "Stop"
$frontendPath = Join-Path $PSScriptRoot "frontend"
$packageJson = Join-Path $frontendPath "package.json"
$indexHtml = Join-Path $frontendPath "index.html"
$viteConfig = Join-Path $frontendPath "vite.config.ts"

Write-Host "Starting TABLEAU2PBI frontend" -ForegroundColor Cyan
Write-Host "Frontend root: $frontendPath" -ForegroundColor Cyan

if (!(Test-Path $packageJson)) { throw "Frontend package.json not found at $packageJson. Re-extract the application ZIP to a clean folder." }
if (!(Test-Path $indexHtml)) { throw "Frontend index.html not found at $indexHtml. Re-extract the application ZIP to a clean folder." }
if (!(Test-Path $viteConfig)) { throw "Frontend vite.config.ts not found at $viteConfig." }
if (!(Get-Command npm -ErrorAction SilentlyContinue)) { throw "npm was not found. Install Node.js LTS and restart PowerShell." }

$env:VITE_API_BASE_URL = "http://127.0.0.1:8000"
$env:npm_config_registry = "https://registry.npmjs.org/"

# IMPORTANT: npm install and npm run must execute with the frontend folder as
# the actual current working directory. Do not rely on npm --prefix here: on
# some Windows/npm combinations spawned from PowerShell it can still resolve
# package.json from the parent workbench folder.
Push-Location $frontendPath
try {
    $vite = Join-Path $frontendPath "node_modules\.bin\vite.cmd"

    if (!(Test-Path $vite)) {
        Write-Host "Frontend dependencies are not installed. Installing them once in $frontendPath ..." -ForegroundColor Yellow
        Write-Host "Using npm registry: $env:npm_config_registry" -ForegroundColor DarkGray
        npm install --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { throw "Frontend dependency installation failed with exit code $LASTEXITCODE." }
    }
    else {
        Write-Host "Frontend dependencies already installed - skipping npm install." -ForegroundColor Green
    }

    if (!(Test-Path $vite)) { throw "Vite executable was not created at $vite after npm install." }

    Write-Host "Starting Vite from frontend working directory..." -ForegroundColor Green
    Write-Host "Frontend URL: http://127.0.0.1:5173" -ForegroundColor Cyan
    npm run dev -- --strictPort
    if ($LASTEXITCODE -ne 0) { throw "Vite frontend stopped with exit code $LASTEXITCODE." }
}
finally {
    Pop-Location
}
