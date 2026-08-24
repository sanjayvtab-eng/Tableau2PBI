Write-Host "Stopping TABLEAU2PBI backend/frontend ports..." -ForegroundColor Cyan
8000,5173,5174,5175 | ForEach-Object {
    $conns = Get-NetTCPConnection -LocalPort $_ -State Listen -ErrorAction SilentlyContinue
    foreach ($conn in $conns) {
        try {
            Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
            Write-Host "Stopped PID $($conn.OwningProcess) on port $_" -ForegroundColor Yellow
        } catch {}
    }
}
Write-Host "Done." -ForegroundColor Green
