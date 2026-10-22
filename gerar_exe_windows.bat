@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  set "PYTHON=py -3"
) else (
  set "PYTHON=python"
)
%PYTHON% -m pip install --upgrade pip
if errorlevel 1 goto erro
%PYTHON% -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto erro
%PYTHON% -m PyInstaller --noconfirm --clean --windowed --onefile --name LumenPDF --icon lumen.ico --collect-all pymupdf --collect-all fitz leitor_lumen.py
if errorlevel 1 goto erro
echo.
echo Executavel gerado em "%CD%\dist\LumenPDF.exe"
explorer "%CD%\dist"
pause
exit /b 0
:erro
echo.
echo Nao foi possivel gerar o executavel. Verifique a conexao com a internet e se o Python foi instalado corretamente.
pause
exit /b 1
