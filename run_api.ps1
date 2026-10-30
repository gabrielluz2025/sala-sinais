$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$env:PYTHONPATH = $Root
& "$Root\.venv\Scripts\python.exe" -m api.main
