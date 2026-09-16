@echo off
setlocal
REM ============================================================
REM deploy.bat - publica o dashboard no GitHub e no Hugging Face
REM
REM O QUE ELE FAZ (e o que NAO faz)
REM   - Commita o que estiver pendente na pasta.
REM   - Busca o que os remotes tem (a GitHub Action commita dados
REM     sozinha) e REBASEIA o seu commit por cima.
REM   - Faz push normal, SEM --force.
REM
REM   NAO apaga o .git, NAO recria historico, NAO usa --force.
REM   A versao antiga fazia as tres coisas: rmdir /s /q .git + git init
REM   + push --force. Isso apagava, no seu PC e nos dois remotes, os
REM   commits "chore: atualizacao automatica de dados" da Action.
REM
REM USO
REM   deploy.bat                  publica o codigo (rapido)
REM   deploy.bat --dados          regera os parquets antes (5-10 min)
REM ============================================================

echo.
echo ============================================================
echo   DEPLOY - Dashboard Fundos AWR
echo ============================================================
echo.

if not exist "app.py" (
    echo [ERRO] Rode este script de dentro da pasta awr_dashboard.
    pause
    exit /b 1
)
where git >nul 2>&1 || (echo [ERRO] git nao encontrado no PATH. & pause & exit /b 1)

REM ---------- opcional: regerar os dados ----------
if /i "%~1"=="--dados" (
    where python >nul 2>&1 || (echo [ERRO] python nao encontrado. Ative: conda activate fundos & pause & exit /b 1)
    echo [dados] Regerando parquets ^(5-10 min^)...
    if exist "data\cotas.parquet" del /q "data\cotas.parquet"
    if exist "data\ibov.parquet"  del /q "data\ibov.parquet"
    if exist "data\cdi.parquet"   del /q "data\cdi.parquet"
    if exist "data\pl.parquet"    del /q "data\pl.parquet"
    python build_data.py || (echo [ERRO] build_data.py falhou. & pause & exit /b 1)
    echo.
)

REM ---------- 1. commitar o que estiver pendente ----------
echo [1/4] Commitando alteracoes pendentes...
git add -A
git diff --cached --quiet
if errorlevel 1 (
    set /p MSG=" Mensagem do commit (Enter = 'atualiza dashboard'): "
    if "%MSG%"=="" set "MSG=atualiza dashboard"
    git commit -q -m "%MSG%" || (echo [ERRO] commit falhou. & pause & exit /b 1)
    echo   commit criado.
) else (
    echo   nada pendente, seguindo com o que ja esta commitado.
)

REM ---------- 2. trazer o que os remotes tem ----------
echo.
echo [2/4] Buscando novidades dos remotes...
git fetch origin main || (echo [ERRO] fetch do GitHub falhou. & pause & exit /b 1)
git fetch hf     main >nul 2>&1

echo   rebaseando seu commit por cima do GitHub...
git rebase origin/main
if errorlevel 1 (
    echo.
    echo [PARE] O rebase deu conflito. NADA foi publicado.
    echo   Resolva os arquivos em conflito e rode:  git rebase --continue
    echo   Para desistir e voltar ao estado anterior: git rebase --abort
    pause
    exit /b 1
)
echo   OK

REM ---------- 3. GitHub ----------
echo.
echo [3/4] Publicando no GitHub...
git push origin main
if errorlevel 1 (
    echo.
    echo [ERRO] Push pro GitHub falhou. NAO use --force para contornar:
    echo   isso apagaria os commits de dados da Action. Rode de novo o
    echo   fetch + rebase e tente outra vez.
    pause
    exit /b 1
)
echo   OK

REM ---------- 4. Hugging Face ----------
echo.
echo [4/4] Publicando no Hugging Face...
echo.
echo   Se pedir credenciais:
echo     Username: loss-chaser
echo     Password: COLE O TOKEN hf_xxxxx ^(nao a senha da conta^)
echo     O token nao aparece na tela ao colar - e normal.
echo.
git push hf main
if errorlevel 1 (
    echo.
    echo [ERRO] Push pro Hugging Face falhou.
    echo   Causa comum: token vencido/sem permissao Write, ou o Windows
    echo   guardou a senha antiga. Para limpar a credencial salva:
    echo     cmdkey /list ^| findstr huggingface
    echo     cmdkey /delete:git:https://huggingface.co
    echo   Gere um token novo em huggingface.co ^> Settings ^> Access Tokens
    echo   ^(permissao Write^) e rode o deploy de novo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   PUBLICADO
echo ============================================================
echo.
echo   O Space fica "Building" por 3-5 min e volta a "Running":
echo     https://huggingface.co/spaces/loss-chaser/dashboard-fundos
echo.
pause
