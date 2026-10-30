# Inicia cloudflared se existir config.yml (login/túnel feitos manualmente antes).
# Uso: powershell -ExecutionPolicy Bypass -File scripts\start-cloudflare-tunnel.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent

function Get-CloudflareConfigPath {
    $candidates = @(
        (Join-Path $env:USERPROFILE ".cloudflared\config.yml")
        (Join-Path $Root "scripts\cloudflare-tunnel.yml")
        (Join-Path $Root "cloudflare-tunnel.yml")
    )
    foreach ($path in $candidates) {
        if (Test-Path -LiteralPath $path) {
            return $path
        }
    }
    return $null
}

function Get-TunnelNameFromConfig {
    param([string]$ConfigPath)
    $defaultName = "sala-sinais"
    if (-not (Test-Path -LiteralPath $ConfigPath)) {
        return $defaultName
    }
    foreach ($line in Get-Content -LiteralPath $ConfigPath -Encoding UTF8) {
        if ($line -match '^\s*tunnel:\s*(\S+)\s*$') {
            $id = $Matches[1].Trim()
            if ($id -and $id -ne "TUNNEL_ID") {
                # UUID no yml: cloudflared run aceita o nome do túnel criado (sala-sinais)
                return $defaultName
            }
        }
    }
    return $defaultName
}

function Find-CloudflaredExe {
    $cmd = Get-Command cloudflared -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }
    $local = Join-Path $env:ProgramFiles "cloudflared\cloudflared.exe"
    if (Test-Path -LiteralPath $local) {
        return $local
    }
    return $null
}

$config = Get-CloudflareConfigPath
if (-not $config) {
    Write-Host "[AVISO] Nenhum config cloudflared encontrado." -ForegroundColor Yellow
    Write-Host "        Copie scripts\cloudflare-tunnel.yml.example para:"
    Write-Host "          $env:USERPROFILE\.cloudflared\config.yml"
    Write-Host "        ou scripts\cloudflare-tunnel.yml"
    Write-Host "        Guia: docs\CLOUDFLARE_TUNNEL_PASSO_A_PASSO.md"
    exit 1
}

$exe = Find-CloudflaredExe
if (-not $exe) {
    Write-Host "[ERRO] cloudflared nao encontrado no PATH." -ForegroundColor Red
    Write-Host "       Instale: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
    exit 1
}

$tunnelName = Get-TunnelNameFromConfig -ConfigPath $config
Write-Host "Iniciando cloudflared (config: $config, tunnel: $tunnelName)..."

& $exe tunnel --config $config run $tunnelName
