$procs = Get-Process -Name terminal64 -ErrorAction SilentlyContinue
if ($procs) {
    Write-Host 'Encerrando MetaTrader 5 (terminal64.exe)...'
    foreach ($p in $procs) {
        $null = $p.CloseMainWindow()
    }
    Start-Sleep -Seconds 3
    $left = Get-Process -Name terminal64 -ErrorAction SilentlyContinue
    if ($left) {
        Write-Host 'AVISO: processo ainda ativo — taskkill /F'
        $left | Stop-Process -Force
    } else {
        Write-Host 'MT5 encerrado.'
    }
} else {
    Write-Host 'Nenhum terminal64.exe em execucao.'
}
