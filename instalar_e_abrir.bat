@echo off
setlocal
cd /d "%~dp0"
title Lumen PDF - instalador e leitor
where py >nul 2>nul
if %errorlevel%==0 (
  set PYTHON=py -3
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python 3 nao foi encontrado.
    echo Instale o Python 3 em https://www.python.org/downloads/windows/
    echo Durante a instalacao, marque a opcao para adicionar Python ao PATH.
    pause
    exit /b 1
  )
  set PYTHON=python
)
echo.
echo Lumen PDF - verificando dependencias...
%PYTHON% -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Nao foi possivel instalar as dependencias. Verifique sua conexao e o Python.
  pause
  exit /b 1
)
echo.
echo Abrindo Lumen PDF...
%PYTHON% leitor_lumen.py
if errorlevel 1 (
  echo.
  echo O Lumen PDF terminou com um erro. Veja a mensagem acima.
  pause
)
endlocal
