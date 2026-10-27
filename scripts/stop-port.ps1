# Освобождает указанный TCP-порт: убивает процессы, которые его слушают.
# Использование: powershell -NoProfile -ExecutionPolicy Bypass -File stop-port.ps1 -Port 8000
param(
    [Parameter(Mandatory = $true)]
    [int]$Port
)

$connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if (-not $connections) {
    Write-Host "[store] Port $Port is free"
    exit 0
}

foreach ($connection in $connections) {
    $pidToKill = $connection.OwningProcess
    try {
        Stop-Process -Id $pidToKill -Force -ErrorAction Stop
        Write-Host "[store] Port $Port freed (PID $pidToKill)"
    } catch {
        Write-Host "[store] Failed to stop PID $pidToKill on port $Port : $($_.Exception.Message)"
    }
}
