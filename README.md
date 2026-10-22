# Lumen PDF

Leitor de PDF para Windows com interface em português, foco em baixo consumo de memória e processamento local.

## Recursos

- Renderiza a página atual, em vez de manter todas as páginas em alta resolução na memória.
- Miniaturas carregadas conforme você navega no painel lateral.
- Busca de texto no documento, navegação por resultados, zoom e ajuste à largura.
- Seleção e cópia de texto.
- Realce colorido, sublinhado, tachado, desenho à mão livre e comentários tipo nota adesiva.
- Marcadores salvos no sumário interno do PDF.
- Painel de marcações para navegar e remover anotações.
- Desfazer a última marcação criada na sessão.
- Exportação do texto e de um relatório das anotações para `.txt`.
- PDFs protegidos por senha são aceitos quando a senha é conhecida.
- Arquivos processados localmente; o programa não envia PDFs para servidores.

## Instalação e execução

1. Instale [Python 3 para Windows](https://www.python.org/downloads/windows/) se necessário. Mantenha o Tcl/Tk habilitado e marque **Add Python to PATH** quando essa opção aparecer.
2. Extraia a pasta e execute `instalar_e_abrir.bat`. Ele instala as dependências e abre o leitor.
3. Nas execuções seguintes, use `abrir.bat`.

Dependências Python: `PyMuPDF` e `Pillow`; `tkinter` acompanha a instalação padrão de Python para Windows. É necessária conexão com a internet para a primeira instalação das dependências.

## Gerar um `.exe`

Em um Windows com Python instalado, execute `gerar_exe_windows.bat`. O script tenta empacotar o app em `dist\LumenPDF.exe` usando PyInstaller. A etapa de empacotamento está incluída como conveniência, mas não foi testada em Windows nesta entrega.

## Como marcar

- **Realçar / Sublinhar / Tachar:** selecione a ferramenta e arraste uma caixa sobre a área desejada.
- **Caneta:** arraste para desenhar livremente.
- **Comentário:** clique no local onde a nota deve ficar e escreva o comentário.
- **Cursor / texto:** arraste sobre palavras; o texto detectado é copiado automaticamente.
- **＋ Marcador:** cria uma entrada no sumário do PDF na página atual.

As alterações permanecem em memória até você clicar em **Salvar anotado** (`Ctrl+S`). Na primeira vez, escolha o nome e local de saída; o arquivo original não é sobrescrito silenciosamente.

## Atalhos

| Atalho | Ação |
|---|---|
| `Ctrl+O` | Abrir PDF |
| `Ctrl+S` | Salvar PDF anotado |
| `Ctrl+F` | Focar a busca |
| `Ctrl+Z` | Desfazer a última marcação criada |
| `←` / `→` | Página anterior / próxima |
| `Page Up` / `Page Down` | Navegar páginas |
| `Ctrl` + `+` / `-` | Zoom |
| `Ctrl` + roda do mouse | Zoom |

## Limitações conhecidas

- PDFs escaneados como imagem só são pesquisáveis se já tiverem uma camada de OCR. O aplicativo não faz OCR.
- As marcações por arrasto são áreas livres: o leitor não tenta detectar automaticamente a linha exata do texto.
- Regravar um PDF pode invalidar assinaturas digitais existentes. Mantenha o original de documentos assinados.
- Esta entrega contém o código-fonte e scripts de execução; não contém um executável Windows pré-compilado.
