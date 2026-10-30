@echo off
chcp 65001 >nul
title Sala de Sinais - Preparar MT5 (Clear)
cd /d "%~dp0\.."

if not exist ".venv\Scripts\python.exe" (
    echo Rode Sala-Sinais.bat ^(opcoes 1 ou 2^) primeiro para criar o .venv.
    pause
    exit /b 1
)

set "PYTHONPATH=%~dp0\.."
set "MT5_EXE=C:\Program Files\Clear Investimentos MT5 Terminal\terminal64.exe"
for /f "usebackq tokens=2 delims==" %%a in (`findstr /b /i "MT5_PATH=" ".env" 2^>nul`) do set "MT5_EXE=%%a"
for /f "tokens=* delims= " %%a in ("%MT5_EXE%") do set "MT5_EXE=%%a"

echo.
echo ============================================================
echo   PREPARAR MT5 — corrige common.ini e abre o terminal Clear
echo   Feche ordens pendentes antes de continuar.
echo ============================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop-mt5-terminal.ps1"

echo.
echo Aplicando fix em config\common.ini [Experts] (MT5 fechado)...
".venv\Scripts\python.exe" scripts\fix_mt5_experts_ini.py
if errorlevel 1 (
    echo [ERRO] fix_mt5_experts_ini falhou.
    pause
    exit /b 1
)

echo.
echo Valores atuais em common.ini [Experts]:
".venv\Scripts\python.exe" -c "import os; from engine.mt5_experts_ini import find_terminal_data_folder, read_experts_flags_for_data_dir; f=find_terminal_data_folder(mt5_path=os.environ.get('MT5_PATH') or r'%MT5_EXE%'); print(read_experts_flags_for_data_dir(str(f.data_dir)) if f else 'pasta nao encontrada')"

if not exist "%MT5_EXE%" (
    echo [ERRO] MT5_PATH nao encontrado: %MT5_EXE%
    echo Ajuste MT5_PATH no .env
    pause
    exit /b 1
)

echo.
echo Abrindo Clear MT5...
start "" "%MT5_EXE%"
echo Aguarde login na demo e confirme o botao verde AlgoTrading na barra.
echo Valide: .venv\Scripts\python.exe scripts\check_mt5_trading.py
echo.
exit /b 0
