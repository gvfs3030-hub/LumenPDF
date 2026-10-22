@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 leitor_lumen.py %*
) else (
  python leitor_lumen.py %*
)
endlocal
