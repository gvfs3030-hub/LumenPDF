# Gerar o LumenPDF.exe

## Opção A — no Windows (mais simples)
1. Instale Python 3.12 ou mais recente pelo site oficial e marque **Add Python to PATH**.
2. Extraia a pasta do projeto.
3. Dê duplo clique em `gerar_exe_windows.bat`.
4. O executável aparecerá em `dist\LumenPDF.exe`.

## Opção B — compilar em um runner Windows do GitHub Actions
O arquivo `.github/workflows/build-windows.yml` já contém a rotina de compilação para Windows.
1. Crie um repositório no GitHub e envie o **conteúdo** desta pasta para a raiz do repositório, incluindo a pasta oculta `.github` (não envie a pasta `LumenPDF` como uma subpasta).
2. Abra a aba **Actions** e escolha **Build Lumen PDF for Windows**.
3. Clique em **Run workflow** (ou deixe o workflow compilar ao enviar para `main`/`master`).
4. Abra a execução concluída e baixe o artefato `LumenPDF-Windows-x64`, que contém `LumenPDF.exe`.

A compilação deve ocorrer em Windows. PyInstaller não transforma, de forma suportada, um build Linux em um executável Windows.
