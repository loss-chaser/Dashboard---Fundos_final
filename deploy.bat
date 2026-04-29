@echo off
REM ============================================================
REM deploy.bat - Script automatico de deploy completo
REM
REM O que ele faz:
REM   1. Apaga parquets antigos
REM   2. Roda build_data.py (gera CSVs)
REM   3. Reseta o repositorio Git
REM   4. Faz push pro GitHub
REM   5. Faz push pro Hugging Face
REM
REM Voce so precisa:
REM   - Estar na pasta awr_dashboard
REM   - Ter substituido build_data.py e data_loader.py pelos novos
REM   - Ter o token do Hugging Face (hf_...) na mao
REM ============================================================

echo.
echo ============================================================
echo   DEPLOY AUTOMATICO - Dashboard Fundos AWR
echo ============================================================
echo.

REM Verifica se esta na pasta certa
if not exist "app.py" (
    echo [ERRO] Voce nao esta na pasta awr_dashboard!
    echo Rode primeiro:
    echo   cd /d "C:\Users\HP\AWR Capital\NuvemAwr - Codigos\VD_codigos\awr_dashboard"
    pause
    exit /b 1
)

REM Verifica se conda env esta ativo
where python >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado. Ative o conda env:
    echo   conda activate fundos
    pause
    exit /b 1
)

echo [1/6] Apagando parquets antigos...
if exist "data\cotas.parquet" del /q "data\cotas.parquet"
if exist "data\ibov.parquet" del /q "data\ibov.parquet"
if exist "data\cdi.parquet" del /q "data\cdi.parquet"
if exist "data\pl.parquet" del /q "data\pl.parquet"
echo   OK

echo.
echo [2/6] Rodando build_data.py (5-10 minutos)...
echo.
python build_data.py
if errorlevel 1 (
    echo.
    echo [ERRO] build_data.py falhou. Veja a mensagem acima.
    pause
    exit /b 1
)

echo.
echo [3/6] Resetando historico Git...
if exist ".git" rmdir /s /q .git
git init
git add .
git commit -m "Initial commit - dados em CSV.gz" -q
git branch -M main
echo   OK

echo.
echo [4/6] Configurando remotes...
git remote add origin https://github.com/loss-chaser/Dashboard---Fundos_final.git 2>nul
git remote add hf https://huggingface.co/spaces/loss-chaser/dashboard-fundos 2>nul
echo   OK

echo.
echo [5/6] Fazendo push pro GitHub...
echo (Se pedir login, usa suas credenciais do GitHub)
echo.
git push -u origin main --force
if errorlevel 1 (
    echo.
    echo [ERRO] Push pro GitHub falhou.
    pause
    exit /b 1
)

echo.
echo [6/6] Fazendo push pro Hugging Face...
echo.
echo IMPORTANTE: Quando pedir credenciais:
echo   Username: loss-chaser
echo   Password: cole seu token hf_xxxxx (NAO a senha da conta!)
echo   (o token nao aparece na tela quando voce cola, e normal)
echo.
git push hf main --force
if errorlevel 1 (
    echo.
    echo [ERRO] Push pro Hugging Face falhou.
    echo Verifique se o token tem permissao Write.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   SUCESSO!
echo ============================================================
echo.
echo Acompanhe o build em:
echo   https://huggingface.co/spaces/loss-chaser/dashboard-fundos
echo.
echo O Space vai aparecer como "Building" por 3-5 minutos
echo e depois "Running". Pronto!
echo.
pause
