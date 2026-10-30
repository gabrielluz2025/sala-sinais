# Modo web: API + engine em background + cloudflared opcional (financasmais.com).
# Uso: powershell -ExecutionPolicy Bypass -File scripts\start-sala-sinais-web.ps1
# Doc: docs/CLOUDFLARE_TUNNEL_PASSO_A_PASSO.md

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$EnvFile = Join-Path $Root ".env"

if (-not (Test-Path -LiteralPath $Python)) {
    Write-Host "[ERRO] .venv nao encontrado. Rode Sala-Sinais.bat opcao 1 uma vez." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path -LiteralPath $EnvFile)) {
    Copy-Item (Join-Path $Root ".env.example") $EnvFile
    Write-Host "[INFO] .env criado a partir de .env.example — ajuste CORS e WEBHOOK_SECRET."
}

function Get-EnvValue {
    param([string]$Name, [string]$Default = "")
    if (-not (Test-Path -LiteralPath $EnvFile)) {
        return $Default
    }
    foreach ($line in Get-Content -LiteralPath $EnvFile -Encoding UTF8) {
        if ($line -match "^\s*$([regex]::Escape($Name))\s*=\s*(.*)\s*$") {
            return $Matches[1].Trim().Trim('"').Trim("'")
        }
    }
    return $Default
}

$engineMode = Get-EnvValue -Name "ENGINE_MODE" -Default "simulation"
$agentStudy = Get-EnvValue -Name "AGENT_AUTO_STUDY_LIBRARY" -Default "true"
$agentStudyCmd = ""
if ($agentStudy -ne "false") {
    $agentStudyCmd = "set AGENT_AUTO_STUDY_LIBRARY=true&& "
}

Write-Host "Encerrando API antiga na porta 8000 (se houver)..."
& (Join-Path $Root "scripts\stop-api.ps1") | Out-Null

$env:PYTHONPATH = $Root

Write-Host "Iniciando API..."
Start-Process -FilePath "cmd.exe" -ArgumentList @(
    "/k", "cd /d `"$Root`" && set PYTHONPATH=$Root && ${agentStudyCmd}.venv\Scripts\python.exe -m api.main"
) -WindowStyle Normal -WorkingDirectory $Root

Write-Host "Aguardando http://127.0.0.1:8000/health ..."
$ready = $false
for ($i = 0; $i -lt 45; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200) {
            $ready = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 1
    }
}
if (-not $ready) {
    Write-Host "[AVISO] API nao respondeu em 45s — confira a janela da API." -ForegroundColor Yellow
} else {
    Write-Host "API pronta."
}

$engineTitle = "Sala de Sinais - Engine (web)"
$engineCmd = "set PYTHONPATH=$Root&& set ENGINE_MODE=simulation&& .venv\Scripts\python.exe -m engine.main"

if ($engineMode -eq "paper_mt5") {
    $engineTitle = "Sala de Sinais - Engine MT5 (paper)"
    $engineCmd = "set PYTHONPATH=$Root&& echo Modo PAPER_MT5 — MT5 aberto e logado.&& .venv\Scripts\python.exe -m engine.main"
    Write-Host "[MT5] ENGINE_MODE=paper_mt5 — abra o MetaTrader antes de operar."
} elseif ($engineMode -eq "live_mt5") {
    $engineTitle = "Sala de Sinais - Engine MT5 (LIVE)"
    $engineCmd = "set PYTHONPATH=$Root&& echo *** LIVE_MT5 ***&& .venv\Scripts\python.exe -m engine.main"
}

Write-Host "Iniciando engine ($engineMode)..."
Start-Process -FilePath "cmd.exe" -ArgumentList @(
    "/k", "cd /d `"$Root`" && $engineCmd"
) -WindowStyle Normal -WorkingDirectory $Root

$configCandidates = @(
    (Join-Path $env:USERPROFILE ".cloudflared\config.yml")
    (Join-Path $Root "scripts\cloudflare-tunnel.yml")
    (Join-Path $Root "cloudflare-tunnel.yml")
)
$tunnelConfig = $null
foreach ($p in $configCandidates) {
    if (Test-Path -LiteralPath $p) {
        $tunnelConfig = $p
        break
    }
}

if ($tunnelConfig) {
    Write-Host "Config cloudflared encontrado — iniciando túnel em nova janela..."
    Start-Process -FilePath "powershell.exe" -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
        (Join-Path $Root "scripts\start-cloudflare-tunnel.ps1")
    ) -WindowStyle Normal -WorkingDirectory $Root
} else {
    Write-Host ""
    Write-Host "[INFO] Túnel nao iniciado (sem config.yml)." -ForegroundColor Yellow
    Write-Host "       Siga docs\CLOUDFLARE_TUNNEL_PASSO_A_PASSO.md e copie cloudflare-tunnel.yml.example."
    Write-Host "       Local: http://127.0.0.1:8000/"
}

Write-Host ""
Write-Host "============================================================"
Write-Host " Modo web — mantenha API, engine e cloudflared abertos"
Write-Host " Publico (apos DNS): https://financasmais.com"
Write-Host "============================================================"
