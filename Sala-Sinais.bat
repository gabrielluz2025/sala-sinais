@echo off
chcp 65001 >nul
setlocal EnableExtensions
title Sala de Sinais
cd /d "%~dp0"
set "ROOT=%~dp0"

if not "%~1"=="" goto :dispatch
set "FROM_MENU=1"

:menu
cls
echo.
echo  ============================================================
echo   SALA DE SINAIS — launcher unico
echo  ============================================================
echo.
echo   [1] Abrir tudo  ^(API + engine + painel; MT5 prep se paper^)  ^(padrao^)
echo   [2] So API + painel  ^(sem engine^)
echo   [3] So engine  ^(MT5 conforme .env^)
echo   [4] Simulacao  ^(so engine, sem MT5^)
echo   [5] Preparar MT5  ^(prepare_mt5_trading^)
echo   [6] Corretora demo / modo real  ^(preflight^)
echo   [7] Aprendizado 24h  ^(API + engine, ate pregão B3^)
echo   [0] Sair
echo.
set "MENU_CHOICE="
set /p MENU_CHOICE="Escolha [1]: "
if "%MENU_CHOICE%"=="" set "MENU_CHOICE=1"
if "%MENU_CHOICE%"=="0" exit /b 0
if "%MENU_CHOICE%"=="1" goto :do_all
if "%MENU_CHOICE%"=="2" goto :do_sistema
if "%MENU_CHOICE%"=="3" goto :do_engine
if "%MENU_CHOICE%"=="4" goto :do_simulacao
if "%MENU_CHOICE%"=="5" goto :do_mt5
if "%MENU_CHOICE%"=="6" goto :menu_mt5_live
if "%MENU_CHOICE%"=="7" goto :do_overnight
echo Opcao invalida.
timeout /t 2 /nobreak >nul
goto :menu

:menu_mt5_live
cls
echo.
echo   [6] Corretora / modo real
echo.
echo   [a] Conectar corretora  ^(paper_mt5, demo^)
echo   [b] Ativar modo REAL  ^(preflight conta real^)
echo   [0] Voltar
echo.
set "SUB_CHOICE="
set /p SUB_CHOICE="Escolha: "
if /i "%SUB_CHOICE%"=="a" goto :do_corretora
if /i "%SUB_CHOICE%"=="b" goto :do_real
if "%SUB_CHOICE%"=="0" goto :menu
goto :menu_mt5_live

:dispatch
set "FROM_MENU="
if /i "%~1"=="all" goto :do_all
if /i "%~1"=="sistema" goto :do_sistema
if /i "%~1"=="engine" goto :do_engine
if /i "%~1"=="simulacao" goto :do_simulacao
if /i "%~1"=="simulation" goto :do_simulacao
if /i "%~1"=="overnight" goto :do_overnight
if /i "%~1"=="aprendizado" goto :do_overnight
if /i "%~1"=="mt5" goto :do_mt5
if /i "%~1"=="prepare_mt5" goto :do_mt5
if /i "%~1"=="corretora" goto :do_corretora
if /i "%~1"=="real" goto :do_real
if /i "%~1"=="live" goto :do_real
echo [ERRO] Argumento desconhecido: %~1
echo Uso: Sala-Sinais.bat [all^|sistema^|engine^|simulacao^|mt5^|corretora^|real]
exit /b 1

:do_all
call :ensure_venv strict
if errorlevel 1 goto :fail_exit
call :ensure_env
call :build_cockpit strict
if errorlevel 1 goto :fail_exit
set "PYTHONPATH=%ROOT%"
call :read_engine_mode
call :read_agent_auto_study
if /i "%ENGINE_MODE%"=="paper_mt5" (
    echo [MT5] paper_mt5 — preparando terminal ^(fechar + ini + abrir Clear^) antes da API...
    call "%ROOT%scripts\prepare_mt5_trading.bat"
    if errorlevel 1 (
        echo [AVISO] prepare_mt5_trading falhou — confira MT5_PATH no .env e feche o MT5 manualmente.
    )
    echo Aguardando login MT5 e carga do terminal ^(20s^)...
    timeout /t 20 /nobreak >nul
    echo Confirme o botao verde AlgoTrading na barra do MT5 se ainda estiver vermelho/cinza.
)
call :stop_api
start "Sala de Sinais - API" /D "%ROOT%" cmd /k "set PYTHONPATH=%ROOT%%AGENT_AUTO_STUDY_CMD%&& .venv\Scripts\python.exe -m api.main"
call :wait_for_api
call :open_cockpit
if /i "%ENGINE_MODE%"=="paper_mt5" (
    start "Sala de Sinais - Engine MT5 (paper)" /D "%ROOT%" cmd /k "set PYTHONPATH=%ROOT%&& echo Modo PAPER_MT5 — MetaTrader 5 deve estar aberto e logado.&& echo ENGINE_MODE vem do .env&& echo.&& .venv\Scripts\python.exe -m engine.main"
) else if /i "%ENGINE_MODE%"=="live_mt5" (
    start "Sala de Sinais - Engine MT5 (LIVE)" /D "%ROOT%" cmd /k "set PYTHONPATH=%ROOT%&& echo *** MODO LIVE_MT5 — DINHEIRO REAL ***&& echo MetaTrader 5 aberto e LIVE_TRADING conforme .env&& echo.&& .venv\Scripts\python.exe -m engine.main"
) else (
    start "Sala de Sinais - Simulação (sem MT5)" /D "%ROOT%" cmd /k "set PYTHONPATH=%ROOT%&& set ENGINE_MODE=simulation&& echo Modo SIMULAÇÃO — não precisa do MetaTrader 5.&& echo.&& .venv\Scripts\python.exe -m engine.main"
    set "ENGINE_MODE=simulation"
)
echo.
echo ============================================================
echo  API/Engine iniciados em janelas separadas
echo ============================================================
echo.
echo  Painel: http://127.0.0.1:8000/
echo  Engine: %ENGINE_MODE%  ^(ajuste ENGINE_MODE no .env^)
echo.
echo  Mantenha abertas as janelas "Sala de Sinais - API" e a do engine.
echo.
if defined FROM_MENU goto :menu_after_action
pause
exit /b 0

:menu_after_action
echo Pressione uma tecla para voltar ao menu...
pause >nul
goto :menu

:do_sistema
call :ensure_venv strict
if errorlevel 1 goto :fail_exit
call :ensure_env
call :build_cockpit lax
set "PYTHONPATH=%ROOT%"
call :read_agent_auto_study
call :stop_api
start "Sala de Sinais - API" /D "%ROOT%" cmd /k "set PYTHONPATH=%ROOT%%AGENT_AUTO_STUDY_CMD%&& .venv\Scripts\python.exe -m api.main"
call :wait_for_api
call :open_cockpit
echo.
echo API iniciada em janela separada — painel: http://127.0.0.1:8000/  ^(legado: /classic^).
echo Mantenha a janela "Sala de Sinais - API" aberta enquanto usar o sistema.
echo Engine: Sala-Sinais.bat ^(menu^) opcoes 3 ou 4.
echo.
if defined FROM_MENU goto :menu_after_action
pause
exit /b 0

:do_engine
call :ensure_venv installed
if errorlevel 1 exit /b 1
set "PYTHONPATH=%ROOT%"
echo MetaTrader 5 deve estar aberto e logado na conta demo.
echo.
".venv\Scripts\python.exe" -m engine.main
if defined FROM_MENU goto :menu_after_action
pause
exit /b 0

:do_simulacao
call :ensure_venv installed
if errorlevel 1 exit /b 1
call :ensure_env
set "PYTHONPATH=%ROOT%"
set "ENGINE_MODE=simulation"
echo Modo SIMULAÇÃO — não precisa do MetaTrader 5.
echo.
".venv\Scripts\python.exe" -m engine.main
if defined FROM_MENU goto :menu_after_action
pause
exit /b 0

:do_overnight
call :ensure_venv strict
if errorlevel 1 goto :fail_exit
call :ensure_env
call :build_cockpit lax
set "PYTHONPATH=%ROOT%"
call :stop_api
echo.
echo ============================================================
echo   APRENDIZADO 24h — sinais simulados + estudo ate abrir o pregao B3
echo   Sem ordens MT5. OVERNIGHT_LEARNING=true ^(nao precisa do MetaTrader^)
echo ============================================================
echo.
start "Sala de Sinais - API (aprendizado)" /D "%ROOT%" cmd /k "set PYTHONPATH=%ROOT%&& set OVERNIGHT_LEARNING=true&& set AGENT_AUTO_STUDY_LIBRARY=true&& set ENGINE_MODE=simulation&& set SIGNAL_MODE=paper&& set AUTO_EXECUTE_ORDERS=false&& set B3_IGNORE_SESSION_HOURS=true&& set SIM_RESPECT_RISK_HOURS=false&& .venv\Scripts\python.exe -m api.main"
call :wait_for_api
call :open_cockpit
start "Sala de Sinais - Engine (aprendizado 24h)" /D "%ROOT%" cmd /k "set PYTHONPATH=%ROOT%&& set OVERNIGHT_LEARNING=true&& set AGENT_AUTO_STUDY_LIBRARY=true&& set ENGINE_MODE=simulation&& set SIGNAL_MODE=paper&& set AUTO_EXECUTE_ORDERS=false&& set B3_IGNORE_SESSION_HOURS=true&& set SIM_RESPECT_RISK_HOURS=false&& echo Modo APRENDIZADO 24h — estudo e sinais simulados ate o pregao.&& echo Sem ordens MT5 ^(use paper_mt5 separado se quiser demo^).&& echo.&& .venv\Scripts\python.exe -m engine.main"
set "ENGINE_MODE=simulation"
echo.
echo ============================================================
echo  Aprendizado 24h iniciado ^(API + engine^)
echo ============================================================
echo.
echo  Painel: http://127.0.0.1:8000/
echo  Badge no painel: overnight_learning
echo.
if defined FROM_MENU goto :menu_after_action
pause
exit /b 0

:do_mt5
call :ensure_venv installed
if errorlevel 1 exit /b 1
call "%ROOT%scripts\prepare_mt5_trading.bat"
exit /b %ERRORLEVEL%

:do_corretora
call :ensure_venv installed
if errorlevel 1 exit /b 1
set "PYTHONPATH=%ROOT%"
echo.
echo ============================================================
echo   CONECTAR CORRETORA — MetaTrader 5 obrigatorio
echo   Avenue e apps sem MT5 NAO enviam ordens por este sistema.
echo   Use conta DEMO na corretora antes de dinheiro real.
echo ============================================================
echo.
".venv\Scripts\python.exe" -m engine.scripts.preflight_live
set PREFLIGHT_EXIT=%ERRORLEVEL%
echo.
if exist "docs\EXECUCAO_AUTOMATICA.md" (
    start "" "docs\EXECUCAO_AUTOMATICA.md"
) else (
    echo Guia: docs\EXECUCAO_AUTOMATICA.md
)
if "%PREFLIGHT_EXIT%"=="1" (
    echo [BLOQUEADO] Corrija MT5/API antes de paper_mt5.
    pause
    exit /b 1
)
echo.
echo Se o preflight OK e MT5 esta logado na DEMO:
echo   1. Edite .env com ENGINE_MODE=paper_mt5
echo   2. SIGNAL_MODE=live, LIVE_TRADING=false
echo   3. AUTO_EXECUTE_ORDERS=true e EXECUTE_ON_DEMO=true
echo   4. Sala-Sinais.bat opcao 2  ^(API^)
echo   5. Sala-Sinais.bat opcao 3  ^(engine + MT5^)
echo.
choice /M "Abrir .env agora para colar as linhas do guia"
if not errorlevel 2 start notepad ".env"
echo.
choice /M "Abrir engine agora (MT5 deve estar aberto)"
if not errorlevel 2 start "" "%~dp0Sala-Sinais.bat" engine
pause
exit /b 0

:do_real
call :ensure_venv installed
if errorlevel 1 exit /b 1
set "PYTHONPATH=%ROOT%"
echo.
echo ============================================================
echo   PREFLIGHT — verificacao antes de dinheiro real
echo   MetaTrader 5 deve estar ABERTO e logado na conta desejada.
echo ============================================================
echo.
".venv\Scripts\python.exe" -m engine.scripts.preflight_live
set PREFLIGHT_EXIT=%ERRORLEVEL%
echo.
if "%PREFLIGHT_EXIT%"=="1" (
    echo [BLOQUEADO] Corrija os problemas acima antes de ativar LIVE_TRADING.
    echo Nao alteramos seu .env automaticamente.
    pause
    exit /b 1
)
if "%PREFLIGHT_EXIT%"=="2" (
    echo [PRONTO COM AVISOS] Conta REAL detectada e checks principais OK.
    echo.
    echo Proximos passos MANUAIS:
    echo   1. Abra o arquivo .env.live.example nesta pasta
    echo   2. Copie SIGNAL_MODE, LIVE_TRADING e taxas para seu .env
    echo   3. Confirme MT5_SYMBOL e margem para WIN na corretora
    echo   4. Salve o .env
    echo   5. Sala-Sinais.bat opcao 2  ^(API + painel^)
    echo   6. Sala-Sinais.bat opcao 3  ^(com MT5 aberto^)
    echo.
    choice /M "Abrir .env.live.example e .env agora para editar"
    if not errorlevel 2 start notepad ".env.live.example"
    if not errorlevel 2 start notepad ".env"
    pause
    exit /b 0
)
echo [PAPER / DEMO OK] Exit %PREFLIGHT_EXIT% — LIVE_TRADING ainda nao esta ativo ou conta demo.
echo Para modo real: faca login na conta REAL no MT5 e rode este script de novo.
echo Referencia: docs\MODO_REAL.md
echo.
pause
exit /b 0

REM ---------- helpers ----------

:ensure_venv
if exist ".venv\Scripts\python.exe" exit /b 0
if /i "%~1"=="installed" (
    echo Rode primeiro Sala-Sinais.bat ^(opcao 1 ou 2^) para instalar o ambiente.
    pause
    exit /b 1
)
echo Criando ambiente Python...
python -m venv .venv
if errorlevel 1 (
    echo Instale Python 3.11+ de python.org e tente de novo.
    pause
    exit /b 1
)
".venv\Scripts\pip.exe" install -r requirements.txt -q
exit /b 0

:ensure_env
if not exist ".env" (
    copy /Y ".env.example" ".env" >nul
    echo Arquivo .env criado. Ajuste MT5_SYMBOL se precisar.
)
exit /b 0

:build_cockpit
if exist "cockpit\dist\index.html" exit /b 0
if not exist "cockpit\package.json" exit /b 0
if /i "%~1"=="strict" (
    where npm >nul 2>&1
    if errorlevel 1 (
        echo [AVISO] Node.js/npm nao encontrado — cockpit nao sera compilado.
        echo         Instale Node.js LTS ou abra /classic no painel.
        exit /b 0
    )
)
echo Construindo Pulse Deck ^(cockpit^)...
pushd "%ROOT%cockpit"
call npm install
if errorlevel 1 (
    echo Falha no npm install do cockpit.
    popd
    if /i "%~1"=="strict" (
        pause
        exit /b 1
    )
    exit /b 0
)
call npm run build
popd
if not exist "cockpit\dist\index.html" (
    echo Build do cockpit falhou. Painel abrira em /classic se necessario.
)
exit /b 0

:read_engine_mode
set "ENGINE_MODE=simulation"
for /f "usebackq tokens=2 delims==" %%a in (`findstr /b /i "ENGINE_MODE=" ".env" 2^>nul`) do set "ENGINE_MODE=%%a"
for /f "tokens=* delims= " %%a in ("%ENGINE_MODE%") do set "ENGINE_MODE=%%a"
exit /b 0

:read_agent_auto_study
set "AGENT_AUTO_STUDY_CMD=&& set AGENT_AUTO_STUDY_LIBRARY=true"
findstr /b /i "AGENT_AUTO_STUDY_LIBRARY=false" ".env" >nul 2>&1
if not errorlevel 1 set "AGENT_AUTO_STUDY_CMD="
exit /b 0

:stop_api
echo Encerrando API antiga na porta 8000 (se houver)...
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\stop-api.ps1" >nul 2>&1
exit /b 0

:wait_for_api
set "API_WAIT=0"
echo Aguardando a API em http://127.0.0.1:8000/health ...
:wait_for_api_loop
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r=Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 goto :wait_for_api_ok
set /a API_WAIT+=1
if %API_WAIT% GEQ 45 (
    echo [AVISO] API nao respondeu em 45s — tente abrir o painel manualmente.
    exit /b 1
)
timeout /t 1 /nobreak >nul
goto :wait_for_api_loop
:wait_for_api_ok
echo API pronta.
exit /b 0

:open_cockpit
set "PAINEL_URL=http://127.0.0.1:8000/"
echo Abrindo Pulse Deck no navegador: %PAINEL_URL%
timeout /t 1 /nobreak >nul
start "" "%PAINEL_URL%"
if errorlevel 1 rundll32 url.dll,FileProtocolHandler "%PAINEL_URL%"
exit /b 0

:fail_exit
if defined FROM_MENU goto :menu
exit /b 1
