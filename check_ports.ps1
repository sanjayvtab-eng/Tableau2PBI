Write-Host "Checking TABLEAU2PBI ports..."
8000,5173,5174,5175 | ForEach-Object {
    $conn = Get-NetTCPConnection -LocalPort $_ -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($conn) {
        $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
        Write-Host "Port $_ is running: PID $($conn.OwningProcess) $($proc.ProcessName)"
    } else {
        Write-Host "Port $_ is not running"
    }
}
