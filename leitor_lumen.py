# -*- coding: utf-8 -*-
"""Lumen PDF — leitor leve com anotações locais.

Dependências: PyMuPDF e Pillow. A interface usa tkinter, incluído no Python para Windows.
"""
from __future__ import annotations

import os
import sys
import math
import tempfile
import subprocess
import platform
from collections import OrderedDict
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

try:
    import fitz  # PyMuPDF
    from PIL import Image, ImageTk, ImageDraw
except ImportError as exc:
    raise SystemExit(
        "Dependências ausentes. Execute instalar_e_abrir.bat ou: "
        "python -m pip install -r requirements.txt\n\n" + str(exc)
    )

APP_NAME = "Lumen PDF"
APP_VERSION = "1.0.0"

# Paleta escura, com contraste alto e poucos elementos visuais.
COLORS = {
    "bg": "#111827",
    "panel": "#182233",
    "panel2": "#202d40",
    "panel3": "#29384d",
    "viewer": "#263244",
    "border": "#34445b",
    "text": "#f3f6fb",
    "muted": "#aab7ca",
    "accent": "#61c7f2",
    "accent_dark": "#173f56",
    "success": "#71d9b0",
    "warning": "#f2c879",
    "danger": "#f18b91",
    "white": "#ffffff",
}

HIGHLIGHT_COLORS = {
    "Amarelo": (1.0, 0.84, 0.20),
    "Verde": (0.38, 0.82, 0.55),
    "Azul": (0.30, 0.67, 0.98),
    "Rosa": (0.96, 0.48, 0.68),
    "Laranja": (1.0, 0.58, 0.27),
}

TOOL_LABELS = {
    "select": "Selecionar texto",
    "highlight": "Realçar",
    "underline": "Sublinhar",
    "strike": "Tachar",
    "draw": "Caneta livre",
    "comment": "Comentário",
}


class LumenPDFApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"{APP_NAME} · leitor leve de PDF")
        self.root.geometry("1260x820")
        self.root.minsize(980, 640)
        self.root.configure(bg=COLORS["bg"])
        icon_path = Path(__file__).resolve().parent / "lumen.ico"
        if icon_path.exists():
            try:
                self.root.iconbitmap(str(icon_path))
            except tk.TclError:
                pass

        self.doc: fitz.Document | None = None
        self.file_path: Path | None = None
        self.output_path: Path | None = None
        self.current_page = 0
        self.dirty = False
        self.zoom = 1.0
        self.fit_width = True
        self.render_scale = 1.0
        self.image_origin = (28, 24)
        self.page_photo = None
        self.page_image_cache: OrderedDict[tuple[int, float], Image.Image] = OrderedDict()
        self.page_cache_limit = 2
        self.thumb_photos: dict[int, ImageTk.PhotoImage] = {}
        self.thumb_items: dict[int, list[int]] = {}
        self.thumb_row_height = 164
        self.thumb_redraw_job = None
        self.resize_job = None
        self.current_tool = "select"
        self.tool_buttons: dict[str, ttk.Button] = {}
        self.active_color_name = tk.StringVar(value="Amarelo")
        self.drag_start: tuple[float, float] | None = None
        self.drag_points: list[fitz.Point] = []
        self.preview_items: list[int] = []
        self.search_results: list[tuple[int, fitz.Rect]] = []
        self.search_result_index = -1
        self.annotation_map: dict[str, tuple[int, int]] = {}
        self.undo_stack: list[tuple[int, int]] = []
        self.outline_map: dict[str, int] = {}
        self.dark_mode = True
        self.status_var = tk.StringVar(value="Pronto · abra um PDF para começar")
        self.page_var = tk.StringVar(value="1")
        self.zoom_var = tk.StringVar(value="Ajustar à largura")
        self.search_var = tk.StringVar()
        self.doc_label_var = tk.StringVar(value="Nenhum documento aberto")
        self.annotation_count_var = tk.StringVar(value="0 marcações")

        self._setup_style()
        self._build_menu()
        self._build_ui()
        self._bind_shortcuts()
        self.root.protocol("WM_DELETE_WINDOW", self.close_app)

        if len(sys.argv) > 1:
            candidate = Path(sys.argv[1].strip('"'))
            if candidate.is_file() and candidate.suffix.lower() == ".pdf":
                self.root.after(150, lambda p=candidate: self.open_pdf(p))

    # ------------------------------ Interface ------------------------------
    def _setup_style(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=COLORS["bg"])
        style.configure("Panel.TFrame", background=COLORS["panel"])
        style.configure("Panel2.TFrame", background=COLORS["panel2"])
        style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=("Segoe UI", 10))
        style.configure("Panel.TLabel", background=COLORS["panel"], foreground=COLORS["text"], font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=COLORS["bg"], foreground=COLORS["muted"], font=("Segoe UI", 9))
        style.configure("PanelMuted.TLabel", background=COLORS["panel"], foreground=COLORS["muted"], font=("Segoe UI", 9))
        style.configure("Brand.TLabel", background=COLORS["bg"], foreground=COLORS["accent"], font=("Segoe UI", 17, "bold"))
        style.configure("Title.TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=("Segoe UI", 10))
        style.configure("Toolbar.TButton", background=COLORS["panel2"], foreground=COLORS["text"], padding=(11, 7), borderwidth=0, font=("Segoe UI", 9))
        style.map("Toolbar.TButton", background=[("active", COLORS["panel3"]), ("pressed", COLORS["accent_dark"])], foreground=[("disabled", COLORS["muted"])])
        style.configure("Accent.TButton", background=COLORS["accent_dark"], foreground=COLORS["accent"], padding=(12, 7), borderwidth=0, font=("Segoe UI", 9, "bold"))
        style.map("Accent.TButton", background=[("active", "#21536d"), ("pressed", "#123244")])
        style.configure("ActiveTool.TButton", background=COLORS["accent"], foreground="#0c2330", padding=(10, 6), borderwidth=0, font=("Segoe UI", 9, "bold"))
        style.map("ActiveTool.TButton", background=[("active", "#7bd5fb")])
        style.configure("TEntry", fieldbackground=COLORS["panel2"], foreground=COLORS["text"], insertcolor=COLORS["text"], bordercolor=COLORS["border"], padding=6)
        style.configure("TCombobox", fieldbackground=COLORS["panel2"], background=COLORS["panel2"], foreground=COLORS["text"], arrowcolor=COLORS["text"], padding=5)
        style.map("TCombobox", fieldbackground=[("readonly", COLORS["panel2"])], foreground=[("readonly", COLORS["text"])])
        style.configure("TNotebook", background=COLORS["panel"], borderwidth=0)
        style.configure("TNotebook.Tab", background=COLORS["panel2"], foreground=COLORS["muted"], padding=(12, 8), font=("Segoe UI", 9))
        style.map("TNotebook.Tab", background=[("selected", COLORS["panel"])], foreground=[("selected", COLORS["accent"])])
        style.configure("Treeview", background=COLORS["panel"], fieldbackground=COLORS["panel"], foreground=COLORS["text"], rowheight=29, borderwidth=0, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", background=COLORS["panel2"], foreground=COLORS["muted"], font=("Segoe UI", 9, "bold"), relief="flat")
        style.map("Treeview", background=[("selected", COLORS["accent_dark"])], foreground=[("selected", COLORS["text"])])
        style.configure("Vertical.TScrollbar", background=COLORS["panel2"], troughcolor=COLORS["panel"], bordercolor=COLORS["panel"], arrowcolor=COLORS["muted"])
        style.configure("Horizontal.TScrollbar", background=COLORS["panel2"], troughcolor=COLORS["panel"], bordercolor=COLORS["panel"], arrowcolor=COLORS["muted"])

    def _build_menu(self):
        menu = tk.Menu(self.root, tearoff=False, bg=COLORS["panel"], fg=COLORS["text"], activebackground=COLORS["accent_dark"], activeforeground=COLORS["text"])
        file_menu = tk.Menu(menu, tearoff=False, bg=COLORS["panel"], fg=COLORS["text"], activebackground=COLORS["accent_dark"], activeforeground=COLORS["text"])
        file_menu.add_command(label="Abrir PDF…", accelerator="Ctrl+O", command=self.open_pdf)
        file_menu.add_command(label="Salvar PDF anotado…", accelerator="Ctrl+S", command=self.save_pdf)
        file_menu.add_separator()
        file_menu.add_command(label="Exportar texto para TXT…", command=self.export_text)
        file_menu.add_command(label="Exportar relatório de marcações…", command=self.export_annotation_report)
        file_menu.add_separator()
        file_menu.add_command(label="Sair", command=self.close_app)
        menu.add_cascade(label="Arquivo", menu=file_menu)
        edit_menu = tk.Menu(menu, tearoff=False, bg=COLORS["panel"], fg=COLORS["text"], activebackground=COLORS["accent_dark"], activeforeground=COLORS["text"])
        edit_menu.add_command(label="Desfazer última marcação", accelerator="Ctrl+Z", command=self.undo_last_annotation)
        edit_menu.add_command(label="Adicionar marcador à página", command=self.add_bookmark)
        edit_menu.add_command(label="Copiar texto da página atual", command=self.copy_page_text)
        menu.add_cascade(label="Editar", menu=edit_menu)
        view_menu = tk.Menu(menu, tearoff=False, bg=COLORS["panel"], fg=COLORS["text"], activebackground=COLORS["accent_dark"], activeforeground=COLORS["text"])
        view_menu.add_command(label="Página anterior", accelerator="←", command=lambda: self.change_page(-1))
        view_menu.add_command(label="Próxima página", accelerator="→", command=lambda: self.change_page(1))
        view_menu.add_command(label="Ajustar à largura", command=self.fit_to_width)
        view_menu.add_command(label="Aumentar zoom", accelerator="Ctrl++", command=lambda: self.change_zoom(1.15))
        view_menu.add_command(label="Diminuir zoom", accelerator="Ctrl+-", command=lambda: self.change_zoom(1 / 1.15))
        menu.add_cascade(label="Exibir", menu=view_menu)
        help_menu = tk.Menu(menu, tearoff=False, bg=COLORS["panel"], fg=COLORS["text"], activebackground=COLORS["accent_dark"], activeforeground=COLORS["text"])
        help_menu.add_command(label="Atalhos de teclado", command=self.show_shortcuts)
        help_menu.add_command(label="Sobre o Lumen PDF", command=self.show_about)
        menu.add_cascade(label="Ajuda", menu=help_menu)
        self.root.config(menu=menu)

    def _build_ui(self):
        # Cabeçalho
        header = ttk.Frame(self.root, padding=(18, 12, 18, 10))
        header.pack(fill="x")
        brand = ttk.Frame(header)
        brand.pack(side="left", fill="x", expand=True)
        ttk.Label(brand, text="LUMEN", style="Brand.TLabel").pack(side="left")
        ttk.Label(brand, text=" PDF", font=("Segoe UI", 17, "bold"), foreground=COLORS["text"]).pack(side="left")
        ttk.Label(brand, text="  ·  seu espaço de leitura", style="Muted.TLabel").pack(side="left", padx=(12, 0), pady=(4, 0))
        ttk.Label(header, textvariable=self.doc_label_var, style="Muted.TLabel", width=30, anchor="e").pack(side="left", padx=14)
        ttk.Button(header, text="Como usar", style="Toolbar.TButton", command=self.show_shortcuts).pack(side="right")

        # Barra de arquivo, páginas, zoom e busca
        toolbar = ttk.Frame(self.root, padding=(14, 8, 14, 8), style="Panel.TFrame")
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="＋  Abrir PDF", style="Accent.TButton", command=self.open_pdf).pack(side="left", padx=(0, 7))
        ttk.Button(toolbar, text="Salvar anotado", style="Toolbar.TButton", command=self.save_pdf).pack(side="left", padx=(0, 10))
        self._separator(toolbar)
        ttk.Button(toolbar, text="‹", width=3, style="Toolbar.TButton", command=lambda: self.change_page(-1)).pack(side="left", padx=(10, 4))
        self.page_entry = ttk.Entry(toolbar, textvariable=self.page_var, width=5, justify="center")
        self.page_entry.pack(side="left")
        self.page_entry.bind("<Return>", self._go_to_page_from_entry)
        self.page_total_label = ttk.Label(toolbar, text="/ —", style="PanelMuted.TLabel")
        self.page_total_label.pack(side="left", padx=(5, 4))
        ttk.Button(toolbar, text="›", width=3, style="Toolbar.TButton", command=lambda: self.change_page(1)).pack(side="left", padx=(4, 10))
        self._separator(toolbar)
        ttk.Button(toolbar, text="−", width=3, style="Toolbar.TButton", command=lambda: self.change_zoom(1 / 1.15)).pack(side="left", padx=(10, 4))
        ttk.Label(toolbar, textvariable=self.zoom_var, style="PanelMuted.TLabel", width=17, anchor="center").pack(side="left")
        ttk.Button(toolbar, text="＋", width=3, style="Toolbar.TButton", command=lambda: self.change_zoom(1.15)).pack(side="left", padx=(4, 4))
        ttk.Button(toolbar, text="Largura", style="Toolbar.TButton", command=self.fit_to_width).pack(side="left", padx=(0, 10))
        self._separator(toolbar)
        self.search_entry = ttk.Entry(toolbar, textvariable=self.search_var, width=18)
        self.search_entry.pack(side="left", padx=(10, 4))
        self.search_entry.insert(0, "")
        self.search_entry.bind("<Return>", lambda _e: self.search_document())
        ttk.Button(toolbar, text="Buscar", style="Toolbar.TButton", command=self.search_document).pack(side="left", padx=(0, 4))
        ttk.Button(toolbar, text="↑", width=3, style="Toolbar.TButton", command=lambda: self.move_search_result(-1)).pack(side="left", padx=(0, 3))
        ttk.Button(toolbar, text="↓", width=3, style="Toolbar.TButton", command=lambda: self.move_search_result(1)).pack(side="left")

        # Barra de ferramentas de anotação
        tools = ttk.Frame(self.root, padding=(14, 8, 14, 8))
        tools.pack(fill="x")
        ttk.Label(tools, text="FERRAMENTAS", style="Muted.TLabel").pack(side="left", padx=(0, 10))
        tool_defs = [
            ("select", "Cursor / texto"),
            ("highlight", "Realçar"),
            ("underline", "Sublinhar"),
            ("strike", "Tachar"),
            ("draw", "Caneta"),
            ("comment", "Comentário"),
        ]
        for tool, label in tool_defs:
            btn = ttk.Button(tools, text=label, style="Toolbar.TButton", command=lambda t=tool: self.set_tool(t))
            btn.pack(side="left", padx=(0, 5))
            self.tool_buttons[tool] = btn
        ttk.Label(tools, text="Cor", style="Muted.TLabel").pack(side="left", padx=(7, 5))
        color_box = ttk.Combobox(tools, textvariable=self.active_color_name, values=list(HIGHLIGHT_COLORS.keys()), state="readonly", width=10)
        color_box.pack(side="left", padx=(0, 10))
        ttk.Button(tools, text="↶ Desfazer", style="Toolbar.TButton", command=self.undo_last_annotation).pack(side="left", padx=(0, 5))
        ttk.Button(tools, text="＋ Marcador", style="Toolbar.TButton", command=self.add_bookmark).pack(side="left")
        self.set_tool("select")

        # Área de trabalho: navegação lateral + visualizador
        body = ttk.Frame(self.root, padding=(12, 0, 12, 8))
        body.pack(fill="both", expand=True)
        self.sidebar = ttk.Frame(body, style="Panel.TFrame", width=248)
        self.sidebar.pack(side="left", fill="y", padx=(0, 10))
        self.sidebar.pack_propagate(False)

        self.notebook = ttk.Notebook(self.sidebar)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)
        self.pages_tab = ttk.Frame(self.notebook, style="Panel.TFrame")
        self.annotations_tab = ttk.Frame(self.notebook, style="Panel.TFrame")
        self.outline_tab = ttk.Frame(self.notebook, style="Panel.TFrame")
        self.notebook.add(self.pages_tab, text="Páginas")
        self.notebook.add(self.annotations_tab, text="Marcações")
        self.notebook.add(self.outline_tab, text="Sumário")
        self._build_thumbnails()
        self._build_annotations_panel()
        self._build_outline_panel()

        viewer = ttk.Frame(body, style="Panel.TFrame")
        viewer.pack(side="left", fill="both", expand=True)
        viewer_top = ttk.Frame(viewer, padding=(13, 9), style="Panel.TFrame")
        viewer_top.pack(fill="x")
        ttk.Label(viewer_top, text="LEITOR", style="PanelMuted.TLabel").pack(side="left")
        ttk.Label(viewer_top, textvariable=self.annotation_count_var, style="PanelMuted.TLabel").pack(side="right")
        self.page_canvas = tk.Canvas(viewer, bg=COLORS["viewer"], highlightthickness=0, relief="flat", cursor="arrow")
        self.page_vscroll = ttk.Scrollbar(viewer, orient="vertical", command=self.page_canvas.yview)
        self.page_hscroll = ttk.Scrollbar(viewer, orient="horizontal", command=self.page_canvas.xview)
        self.page_canvas.configure(yscrollcommand=self.page_vscroll.set, xscrollcommand=self.page_hscroll.set)
        self.page_vscroll.pack(side="right", fill="y")
        self.page_hscroll.pack(side="bottom", fill="x")
        self.page_canvas.pack(side="left", fill="both", expand=True)
        self.page_canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self.page_canvas.bind("<B1-Motion>", self._on_mouse_move)
        self.page_canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.page_canvas.bind("<Configure>", self._on_view_resize)
        self.page_canvas.bind("<Control-MouseWheel>", self._on_ctrl_mousewheel)
        self.page_canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.page_canvas.bind("<Button-3>", self._show_canvas_context_menu)
        self._show_empty_state()

        # Rodapé/status
        status = tk.Frame(self.root, bg=COLORS["panel"], height=29)
        status.pack(fill="x", side="bottom")
        tk.Label(status, textvariable=self.status_var, bg=COLORS["panel"], fg=COLORS["muted"], font=("Segoe UI", 9), anchor="w", padx=14).pack(side="left", fill="x", expand=True)
        tk.Label(status, text=f"v{APP_VERSION}  ·  processamento local", bg=COLORS["panel"], fg=COLORS["muted"], font=("Segoe UI", 9), padx=14).pack(side="right")

    def _separator(self, parent):
        tk.Frame(parent, bg=COLORS["border"], width=1, height=26).pack(side="left", padx=1)

    def _build_thumbnails(self):
        frame = ttk.Frame(self.pages_tab, style="Panel.TFrame")
        frame.pack(fill="both", expand=True)
        self.thumb_canvas = tk.Canvas(frame, bg=COLORS["panel"], highlightthickness=0, width=225)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.thumb_canvas.yview)
        self.thumb_canvas.configure(yscrollcommand=self._on_thumb_yview)
        scrollbar.pack(side="right", fill="y")
        self.thumb_canvas.pack(side="left", fill="both", expand=True)
        self.thumb_scrollbar = scrollbar
        self.thumb_canvas.bind("<Configure>", lambda _e: self._schedule_thumb_redraw(force=True))
        self.thumb_canvas.bind("<MouseWheel>", self._on_thumb_mousewheel)
        self.thumb_canvas.bind("<Button-1>", self._on_thumb_click)

    def _build_annotations_panel(self):
        wrapper = ttk.Frame(self.annotations_tab, style="Panel.TFrame", padding=(6, 7))
        wrapper.pack(fill="both", expand=True)
        ttk.Label(wrapper, text="Marcações deste documento", style="Panel.TLabel").pack(anchor="w", pady=(2, 6))
        cols = ("page", "kind", "content")
        self.annotation_tree = ttk.Treeview(wrapper, columns=cols, show="headings", selectmode="browse")
        self.annotation_tree.heading("page", text="Pg.")
        self.annotation_tree.heading("kind", text="Tipo")
        self.annotation_tree.heading("content", text="Comentário / marcação")
        self.annotation_tree.column("page", width=34, minwidth=34, stretch=False, anchor="center")
        self.annotation_tree.column("kind", width=80, minwidth=72, stretch=False)
        self.annotation_tree.column("content", width=112, minwidth=80, stretch=True)
        ann_scroll = ttk.Scrollbar(wrapper, orient="vertical", command=self.annotation_tree.yview)
        self.annotation_tree.configure(yscrollcommand=ann_scroll.set)
        self.annotation_tree.pack(side="left", fill="both", expand=True)
        ann_scroll.pack(side="right", fill="y")
        self.annotation_tree.bind("<Double-1>", self._jump_to_annotation)
        self.annotation_tree.bind("<Button-3>", self._annotation_context_menu)
        controls = ttk.Frame(self.annotations_tab, style="Panel.TFrame", padding=7)
        controls.pack(fill="x")
        ttk.Button(controls, text="Ir até", style="Toolbar.TButton", command=self._jump_to_annotation).pack(side="left", padx=(0, 4))
        ttk.Button(controls, text="Excluir", style="Toolbar.TButton", command=self.delete_selected_annotation).pack(side="left")
        self.annotation_menu = tk.Menu(self.root, tearoff=False, bg=COLORS["panel"], fg=COLORS["text"], activebackground=COLORS["accent_dark"], activeforeground=COLORS["text"])
        self.annotation_menu.add_command(label="Ir até a marcação", command=self._jump_to_annotation)
        self.annotation_menu.add_command(label="Excluir marcação", command=self.delete_selected_annotation)

    def _build_outline_panel(self):
        wrapper = ttk.Frame(self.outline_tab, style="Panel.TFrame", padding=(6, 7))
        wrapper.pack(fill="both", expand=True)
        ttk.Label(wrapper, text="Sumário e marcadores", style="Panel.TLabel").pack(anchor="w", pady=(2, 7))
        self.outline_tree = ttk.Treeview(wrapper, columns=("page",), show="tree headings", selectmode="browse")
        self.outline_tree.heading("#0", text="Título")
        self.outline_tree.heading("page", text="Pg.")
        self.outline_tree.column("#0", width=160, minwidth=100, stretch=True)
        self.outline_tree.column("page", width=36, minwidth=36, stretch=False, anchor="center")
        outline_scroll = ttk.Scrollbar(wrapper, orient="vertical", command=self.outline_tree.yview)
        self.outline_tree.configure(yscrollcommand=outline_scroll.set)
        self.outline_tree.pack(side="left", fill="both", expand=True)
        outline_scroll.pack(side="right", fill="y")
        self.outline_tree.bind("<Double-1>", self._jump_to_outline)
        buttons = ttk.Frame(self.outline_tab, style="Panel.TFrame", padding=7)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="＋ Marcador nesta página", style="Toolbar.TButton", command=self.add_bookmark).pack(fill="x")

    def _bind_shortcuts(self):
        self.root.bind_all("<Control-o>", lambda _e: self.open_pdf())
        self.root.bind_all("<Control-s>", lambda _e: self.save_pdf())
        self.root.bind_all("<Control-f>", lambda _e: self._focus_search())
        self.root.bind_all("<Control-z>", lambda _e: self.undo_last_annotation())
        self.root.bind_all("<Control-plus>", lambda _e: self.change_zoom(1.15))
        self.root.bind_all("<Control-equal>", lambda _e: self.change_zoom(1.15))
        self.root.bind_all("<Control-minus>", lambda _e: self.change_zoom(1 / 1.15))
        self.root.bind_all("<Prior>", lambda _e: self.change_page(-1))
        self.root.bind_all("<Next>", lambda _e: self.change_page(1))
        self.root.bind_all("<Left>", self._left_key)
        self.root.bind_all("<Right>", self._right_key)
        self.root.bind_all("<Escape>", lambda _e: self.set_tool("select"))

    # ------------------------------ Arquivos -------------------------------
    def open_pdf(self, path: Path | str | None = None):
        if self.doc is not None and self.dirty:
            answer = messagebox.askyesnocancel("Alterações não salvas", "Há alterações neste PDF. Deseja salvá-las antes de abrir outro arquivo?", parent=self.root)
            if answer is None:
                return
            if answer and not self.save_pdf():
                return
        if path is None or isinstance(path, tk.Event):
            picked = filedialog.askopenfilename(title="Abrir documento PDF", filetypes=[("Arquivos PDF", "*.pdf"), ("Todos os arquivos", "*.*")])
            if not picked:
                return
            path = Path(picked)
        else:
            path = Path(path)
        try:
            new_doc = fitz.open(str(path))
            if new_doc.needs_pass:
                password = simpledialog.askstring("PDF protegido", "Este documento exige uma senha:", show="•", parent=self.root)
                if not password or not new_doc.authenticate(password):
                    new_doc.close()
                    messagebox.showerror("Não foi possível abrir", "A senha não foi informada ou está incorreta.", parent=self.root)
                    return
            if len(new_doc) == 0:
                new_doc.close()
                messagebox.showwarning("PDF vazio", "Este arquivo não possui páginas para exibir.", parent=self.root)
                return
        except Exception as exc:
            messagebox.showerror("Erro ao abrir PDF", f"Não foi possível abrir este documento.\n\n{exc}", parent=self.root)
            return

        if self.doc is not None:
            try:
                self.doc.close()
            except Exception:
                pass
        self.doc = new_doc
        self.file_path = path.resolve()
        self.output_path = None
        self.current_page = 0
        self.zoom = 1.0
        self.fit_width = True
        self.dirty = False
        self.undo_stack.clear()
        self.search_results.clear()
        self.search_result_index = -1
        self.page_image_cache.clear()
        self.thumb_photos.clear()
        self.thumb_items.clear()
        self.doc_label_var.set(path.name)
        self.root.title(f"{APP_NAME} · {path.name}")
        self.page_total_label.configure(text=f"/ {len(self.doc)}")
        self.page_var.set("1")
        self._set_status(f"Documento aberto · {len(self.doc)} página(s) · alterações ficam locais até salvar")
        self.refresh_annotations()
        self.refresh_outline()
        self.thumb_canvas.delete("all")
        self.thumb_canvas.configure(scrollregion=(0, 0, 225, len(self.doc) * self.thumb_row_height))
        self._schedule_thumb_redraw(force=True)
        self.render_current_page()

    def save_pdf(self) -> bool:
        if self.doc is None or self.file_path is None:
            messagebox.showinfo("Nada para salvar", "Abra um PDF antes de salvá-lo.", parent=self.root)
            return False
        target = self.output_path
        if target is None:
            base_name = f"{self.file_path.stem}_anotado.pdf"
            picked = filedialog.asksaveasfilename(
                title="Salvar PDF anotado",
                defaultextension=".pdf",
                initialdir=str(self.file_path.parent),
                initialfile=base_name,
                filetypes=[("Arquivo PDF", "*.pdf")],
            )
            if not picked:
                return False
            target = Path(picked).resolve()
            # Não sobrescreve silenciosamente o arquivo original aberto.
            if target == self.file_path:
                messagebox.showwarning("Preservando o original", "Para proteger o arquivo original, salve com outro nome.\nSugestão: acrescente '_anotado' ao nome.", parent=self.root)
                return False
            if target.exists() and not messagebox.askyesno("Substituir arquivo?", f"O arquivo já existe:\n{target.name}\n\nDeseja substituí-lo?", parent=self.root):
                return False
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            # Grava primeiro em um temporário no mesmo volume e só depois substitui o destino.
            fd, temp_name = tempfile.mkstemp(prefix=".lumen_", suffix=".pdf", dir=str(target.parent))
            os.close(fd)
            os.unlink(temp_name)
            try:
                self.doc.save(temp_name, garbage=4, deflate=True, clean=True)
                os.replace(temp_name, target)
            finally:
                if os.path.exists(temp_name):
                    try:
                        os.remove(temp_name)
                    except OSError:
                        pass
            self.output_path = target
            self.dirty = False
            self.doc_label_var.set(target.name)
            self.root.title(f"{APP_NAME} · {target.name}")
            self._set_status(f"Salvo com sucesso · {target}")
            messagebox.showinfo("PDF salvo", f"O PDF anotado foi salvo em:\n\n{target}", parent=self.root)
            return True
        except Exception as exc:
            messagebox.showerror("Erro ao salvar", f"Não foi possível salvar o PDF.\n\n{exc}\n\nSe o documento tiver assinatura digital, a regravação pode invalidá-la.", parent=self.root)
            return False

    def export_text(self):
        if self.doc is None:
            messagebox.showinfo("Exportar texto", "Abra um PDF primeiro.", parent=self.root)
            return
        initial = f"{self.file_path.stem if self.file_path else 'documento'}_texto.txt"
        target = filedialog.asksaveasfilename(title="Exportar texto do PDF", defaultextension=".txt", initialfile=initial, filetypes=[("Arquivo de texto", "*.txt")])
        if not target:
            return
        try:
            with open(target, "w", encoding="utf-8") as handle:
                for i in range(len(self.doc)):
                    page = self.doc.load_page(i)
                    handle.write(f"\n\n{'=' * 18} PÁGINA {i + 1} {'=' * 18}\n\n")
                    handle.write(page.get_text("text"))
            self._set_status(f"Texto exportado · {target}")
            messagebox.showinfo("Exportação concluída", f"O texto foi exportado para:\n{target}", parent=self.root)
        except Exception as exc:
            messagebox.showerror("Falha na exportação", str(exc), parent=self.root)

    def export_annotation_report(self):
        if self.doc is None:
            messagebox.showinfo("Relatório", "Abra um PDF primeiro.", parent=self.root)
            return
        initial = f"{self.file_path.stem if self.file_path else 'documento'}_marcacoes.txt"
        target = filedialog.asksaveasfilename(title="Exportar relatório de marcações", defaultextension=".txt", initialfile=initial, filetypes=[("Arquivo de texto", "*.txt")])
        if not target:
            return
        try:
            count = 0
            with open(target, "w", encoding="utf-8") as handle:
                handle.write(f"Relatório de marcações — {self.file_path.name if self.file_path else 'PDF'}\n")
                handle.write("=" * 60 + "\n\n")
                for page_index in range(len(self.doc)):
                    page = self.doc.load_page(page_index)
                    for annot in page.annots() or []:
                        count += 1
                        kind = annot.type[1] if annot.type else "Anotação"
                        info = annot.info or {}
                        content = (info.get("content") or "").strip()
                        title = (info.get("title") or "").strip()
                        handle.write(f"Página {page_index + 1} — {kind}\n")
                        if title:
                            handle.write(f"Autor/título: {title}\n")
                        handle.write(f"Comentário: {content if content else '(sem texto)'}\n")
                        handle.write(f"Área: {tuple(round(v, 1) for v in annot.rect)}\n\n")
            self._set_status(f"Relatório exportado · {count} marcação(ões)")
            messagebox.showinfo("Relatório concluído", f"Foram exportadas {count} marcação(ões) para:\n{target}", parent=self.root)
        except Exception as exc:
            messagebox.showerror("Falha no relatório", str(exc), parent=self.root)

    # ------------------------------- Render --------------------------------
    def _show_empty_state(self):
        self.page_canvas.delete("all")
        w = max(self.page_canvas.winfo_width(), 700)
        h = max(self.page_canvas.winfo_height(), 500)
        cx, cy = w // 2, h // 2
        self.page_canvas.create_oval(cx - 37, cy - 128, cx + 37, cy - 54, fill=COLORS["accent_dark"], outline="")
        self.page_canvas.create_text(cx, cy - 91, text="L", fill=COLORS["accent"], font=("Segoe UI", 31, "bold"))
        self.page_canvas.create_text(cx, cy - 18, text="Seu próximo PDF começa aqui", fill=COLORS["text"], font=("Segoe UI", 19, "bold"))
        self.page_canvas.create_text(cx, cy + 20, text="Abra um documento para ler, buscar, destacar e comentar.", fill=COLORS["muted"], font=("Segoe UI", 11))
        self.page_canvas.create_text(cx, cy + 59, text="Ctrl + O  ·  Abrir arquivo", fill=COLORS["accent"], font=("Segoe UI", 10, "bold"))
        self.page_canvas.configure(scrollregion=(0, 0, w, h))

    def _compute_render_scale(self, page: fitz.Page) -> float:
        if self.fit_width:
            available = max(380, self.page_canvas.winfo_width() - 78)
            scale = available / max(1.0, page.rect.width)
            scale = min(2.0, max(0.48, scale))
        else:
            scale = 1.25 * self.zoom
        # Proteção contra páginas gigantes e consumo acidental de muita memória.
        max_dim = max(page.rect.width, page.rect.height, 1.0)
        scale = min(scale, 5200 / max_dim)
        return max(0.2, scale)

    def _render_page_image(self, page_index: int, scale: float) -> Image.Image:
        key = (page_index, round(scale, 3))
        if key in self.page_image_cache:
            self.page_image_cache.move_to_end(key)
            return self.page_image_cache[key]
        page = self.doc.load_page(page_index)
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False, annots=True)
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        self.page_image_cache[key] = image
        self.page_image_cache.move_to_end(key)
        while len(self.page_image_cache) > self.page_cache_limit:
            self.page_image_cache.popitem(last=False)
        return image

    def render_current_page(self):
        if self.doc is None:
            self._show_empty_state()
            return
        if self.current_page < 0 or self.current_page >= len(self.doc):
            return
        try:
            page = self.doc.load_page(self.current_page)
            scale = self._compute_render_scale(page)
            self.render_scale = scale
            image = self._render_page_image(self.current_page, scale)
            self.page_canvas.delete("all")
            self.page_photo = ImageTk.PhotoImage(image)
            x0, y0 = 28, 24
            self.image_origin = (x0, y0)
            # Sombra sutil atrás da página.
            self.page_canvas.create_rectangle(x0 + 7, y0 + 8, x0 + image.width + 7, y0 + image.height + 8, fill="#141b27", outline="")
            self.page_canvas.create_image(x0, y0, image=self.page_photo, anchor="nw", tags=("page-image",))
            self.page_canvas.configure(scrollregion=(0, 0, image.width + x0 * 2 + 10, image.height + y0 * 2 + 10))
            self.page_canvas.xview_moveto(0)
            self.page_canvas.yview_moveto(0)
            self.page_var.set(str(self.current_page + 1))
            self.zoom_var.set("Ajustar à largura" if self.fit_width else f"{int(self.zoom * 100)}%")
            self._draw_search_overlays()
            self._set_status(f"Página {self.current_page + 1} de {len(self.doc)}  ·  {int(scale * 100)}% de escala  ·  ferramenta: {TOOL_LABELS.get(self.current_tool, self.current_tool)}")
            self._schedule_thumb_redraw(force=True)
        except Exception as exc:
            self._set_status(f"Erro ao renderizar a página: {exc}")

    def _draw_search_overlays(self):
        if self.doc is None or not self.search_results:
            return
        ox, oy = self.image_origin
        for idx, (page_index, rect) in enumerate(self.search_results):
            if page_index != self.current_page:
                continue
            current = idx == self.search_result_index
            color = "#ffb547" if current else "#f0d45b"
            self.page_canvas.create_rectangle(
                ox + rect.x0 * self.render_scale,
                oy + rect.y0 * self.render_scale,
                ox + rect.x1 * self.render_scale,
                oy + rect.y1 * self.render_scale,
                outline=color,
                width=3 if current else 2,
                fill="#f0d45b" if current else "",
                stipple="gray25" if current else "",
                tags=("search-mark",),
            )

    # --------------------------- Miniaturas / painel ------------------------
    def _on_thumb_yview(self, first, last):
        self.thumb_scrollbar.set(first, last)
        self._schedule_thumb_redraw()

    def _schedule_thumb_redraw(self, force=False):
        if not hasattr(self, "thumb_canvas") or self.doc is None:
            return
        if self.thumb_redraw_job is not None:
            try:
                self.root.after_cancel(self.thumb_redraw_job)
            except tk.TclError:
                pass
        self.thumb_redraw_job = self.root.after(65, lambda: self._update_visible_thumbs(force))

    def _update_visible_thumbs(self, force=False):
        self.thumb_redraw_job = None
        if self.doc is None:
            self.thumb_canvas.delete("all")
            self.thumb_items.clear()
            self.thumb_photos.clear()
            return
        top = max(0, self.thumb_canvas.canvasy(0))
        height = max(120, self.thumb_canvas.winfo_height())
        first = max(0, int(top // self.thumb_row_height) - 1)
        last = min(len(self.doc), int((top + height) // self.thumb_row_height) + 2)
        wanted = set(range(first, last))
        for idx in list(self.thumb_items):
            if idx not in wanted or force:
                for item in self.thumb_items.pop(idx, []):
                    self.thumb_canvas.delete(item)
                self.thumb_photos.pop(idx, None)
        for idx in range(first, last):
            if idx not in self.thumb_items:
                self._draw_thumbnail(idx)
        # Evita manter imagens de miniaturas fora da janela de visualização.
        for idx in list(self.thumb_photos):
            if idx not in wanted:
                self.thumb_photos.pop(idx, None)

    def _draw_thumbnail(self, page_index: int):
        if self.doc is None:
            return
        width = max(190, self.thumb_canvas.winfo_width())
        y = page_index * self.thumb_row_height
        items: list[int] = []
        selected = page_index == self.current_page
        fill = COLORS["accent_dark"] if selected else COLORS["panel"]
        outline = COLORS["accent"] if selected else COLORS["panel"]
        items.append(self.thumb_canvas.create_rectangle(10, y + 7, width - 10, y + self.thumb_row_height - 7, fill=fill, outline=outline, width=2 if selected else 1, tags=(f"thumb:{page_index}",)))
        try:
            page = self.doc.load_page(page_index)
            scale = min(105 / max(1.0, page.rect.width), 119 / max(1.0, page.rect.height))
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False, annots=False)
            pil = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            photo = ImageTk.PhotoImage(pil)
            self.thumb_photos[page_index] = photo
            center = width // 2
            items.append(self.thumb_canvas.create_image(center, y + 14, image=photo, anchor="n", tags=(f"thumb:{page_index}",)))
            items.append(self.thumb_canvas.create_text(center, y + 143, text=f"Página {page_index + 1}", fill=COLORS["accent"] if selected else COLORS["muted"], font=("Segoe UI", 9, "bold" if selected else "normal"), tags=(f"thumb:{page_index}",)))
        except Exception:
            items.append(self.thumb_canvas.create_text(width // 2, y + 75, text=f"Página {page_index + 1}", fill=COLORS["muted"], tags=(f"thumb:{page_index}",)))
        self.thumb_items[page_index] = items

    def _on_thumb_click(self, event):
        item = self.thumb_canvas.find_withtag("current")
        if not item:
            return
        tags = self.thumb_canvas.gettags(item[0])
        for tag in tags:
            if tag.startswith("thumb:"):
                try:
                    self.go_to_page(int(tag.split(":", 1)[1]))
                except ValueError:
                    pass
                return

    def _on_thumb_mousewheel(self, event):
        self.thumb_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"

    # ------------------------------ Navegação ------------------------------
    def go_to_page(self, page_index: int):
        if self.doc is None:
            return
        page_index = max(0, min(len(self.doc) - 1, int(page_index)))
        if page_index == self.current_page:
            self.render_current_page()
            return
        self.current_page = page_index
        self.render_current_page()
        self._schedule_thumb_redraw(force=True)

    def change_page(self, delta: int):
        if self.doc is None:
            return
        self.go_to_page(self.current_page + delta)

    def _go_to_page_from_entry(self, _event=None):
        if self.doc is None:
            return "break"
        try:
            page_num = int(self.page_var.get().strip())
            self.go_to_page(page_num - 1)
        except ValueError:
            self.page_var.set(str(self.current_page + 1))
        return "break"

    def fit_to_width(self):
        if self.doc is None:
            return
        self.fit_width = True
        self.render_current_page()

    def change_zoom(self, factor: float):
        if self.doc is None:
            return
        if self.fit_width:
            self.zoom = max(0.35, min(2.2, self.render_scale / 1.25))
        self.fit_width = False
        self.zoom = max(0.35, min(2.2, self.zoom * factor))
        self.render_current_page()

    def _on_view_resize(self, _event=None):
        if self.doc is None or not self.fit_width:
            if self.doc is None:
                self._show_empty_state()
            return
        if self.resize_job is not None:
            try:
                self.root.after_cancel(self.resize_job)
            except tk.TclError:
                pass
        self.resize_job = self.root.after(120, self._render_after_resize)

    def _render_after_resize(self):
        self.resize_job = None
        if self.doc is not None and self.fit_width:
            self.render_current_page()

    def _on_mousewheel(self, event):
        if self.doc is not None:
            self.page_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_ctrl_mousewheel(self, event):
        self.change_zoom(1.12 if event.delta > 0 else 1 / 1.12)
        return "break"

    def _left_key(self, _event=None):
        focused = self.root.focus_get()
        if focused in (self.page_entry, self.search_entry):
            return
        self.change_page(-1)

    def _right_key(self, _event=None):
        focused = self.root.focus_get()
        if focused in (self.page_entry, self.search_entry):
            return
        self.change_page(1)

    # ------------------------------ Ferramentas -----------------------------
    def set_tool(self, tool: str):
        self.current_tool = tool
        for key, button in self.tool_buttons.items():
            button.configure(style="ActiveTool.TButton" if key == tool else "Toolbar.TButton")
        cursors = {"select": "arrow", "highlight": "crosshair", "underline": "crosshair", "strike": "crosshair", "draw": "pencil", "comment": "hand2"}
        if hasattr(self, "page_canvas"):
            try:
                self.page_canvas.configure(cursor=cursors.get(tool, "arrow"))
            except tk.TclError:
                self.page_canvas.configure(cursor="crosshair" if tool != "select" else "arrow")
        self._set_status(f"Ferramenta ativa: {TOOL_LABELS.get(tool, tool)}")

    def _active_rgb(self):
        return HIGHLIGHT_COLORS.get(self.active_color_name.get(), HIGHLIGHT_COLORS["Amarelo"])

    def _canvas_to_page(self, canvas_x: float, canvas_y: float) -> fitz.Point | None:
        if self.doc is None:
            return None
        ox, oy = self.image_origin
        x = (canvas_x - ox) / self.render_scale
        y = (canvas_y - oy) / self.render_scale
        page = self.doc.load_page(self.current_page)
        if x < 0 or y < 0 or x > page.rect.width or y > page.rect.height:
            return None
        return fitz.Point(x + page.rect.x0, y + page.rect.y0)

    def _on_mouse_down(self, event):
        if self.doc is None:
            return
        cx, cy = self.page_canvas.canvasx(event.x), self.page_canvas.canvasy(event.y)
        point = self._canvas_to_page(cx, cy)
        if point is None:
            self.drag_start = None
            return
        self.drag_start = (cx, cy)
        self.drag_points = [point]
        self._clear_preview()
        if self.current_tool == "comment":
            self._add_comment(point)
            self.drag_start = None

    def _on_mouse_move(self, event):
        if self.doc is None or self.drag_start is None:
            return
        cx, cy = self.page_canvas.canvasx(event.x), self.page_canvas.canvasy(event.y)
        if self.current_tool == "draw":
            point = self._canvas_to_page(cx, cy)
            if point is not None:
                last = self.drag_points[-1] if self.drag_points else None
                if last is None or math.hypot(point.x - last.x, point.y - last.y) > 1.0:
                    self.drag_points.append(point)
                if last is not None:
                    ox, oy = self.image_origin
                    item = self.page_canvas.create_line(ox + last.x * self.render_scale, oy + last.y * self.render_scale, ox + point.x * self.render_scale, oy + point.y * self.render_scale, fill=self._tk_rgb(self._active_rgb()), width=2.5, capstyle="round", smooth=True, tags=("temp-annotation",))
                    self.preview_items.append(item)
        else:
            x0, y0 = self.drag_start
            self._clear_preview()
            color = self._tk_rgb(self._active_rgb()) if self.current_tool in ("highlight", "underline", "strike") else COLORS["accent"]
            if self.current_tool == "highlight":
                item = self.page_canvas.create_rectangle(x0, y0, cx, cy, outline=color, fill=color, stipple="gray50", width=1, tags=("temp-annotation",))
            elif self.current_tool in ("underline", "strike"):
                item = self.page_canvas.create_rectangle(x0, y0, cx, cy, outline=color, dash=(3, 3), width=1, tags=("temp-annotation",))
            else:
                item = self.page_canvas.create_rectangle(x0, y0, cx, cy, outline=COLORS["accent"], dash=(3, 3), width=1, tags=("temp-annotation",))
            self.preview_items.append(item)

    def _on_mouse_up(self, event):
        if self.doc is None or self.drag_start is None:
            self._clear_preview()
            return
        start = self.drag_start
        self.drag_start = None
        cx, cy = self.page_canvas.canvasx(event.x), self.page_canvas.canvasy(event.y)
        end_point = self._canvas_to_page(cx, cy)
        start_point = self._canvas_to_page(start[0], start[1])
        self._clear_preview()
        if start_point is None:
            return
        if self.current_tool == "select":
            if end_point is not None:
                selection_rect = fitz.Rect(start_point, end_point)
                selection_rect.normalize()
                self._copy_words_in_rect(selection_rect)
            return
        if self.current_tool == "draw":
            if end_point is not None:
                self.drag_points.append(end_point)
            self._commit_ink()
            return
        if end_point is None:
            return
        rect = fitz.Rect(start_point, end_point)
        rect.normalize()
        if rect.width < 2 and rect.height < 2:
            return
        if self.current_tool == "highlight":
            self._add_highlight(rect)
        elif self.current_tool == "underline":
            self._add_line_markup(rect, "underline")
        elif self.current_tool == "strike":
            self._add_line_markup(rect, "strike")

    def _clear_preview(self):
        for item in self.preview_items:
            try:
                self.page_canvas.delete(item)
            except tk.TclError:
                pass
        self.preview_items.clear()
        self.page_canvas.delete("temp-annotation")

    def _tk_rgb(self, rgb):
        return "#%02x%02x%02x" % tuple(max(0, min(255, int(c * 255))) for c in rgb)

    def _add_highlight(self, rect: fitz.Rect):
        page = self.doc.load_page(self.current_page)
        rgb = self._active_rgb()
        try:
            annot = page.add_rect_annot(rect)
            annot.set_colors(stroke=rgb, fill=rgb)
            annot.set_opacity(0.30)
            annot.set_border(width=0)
            annot.set_info(title="Lumen PDF", subject="Realce", content="")
            annot.update()
            self._annotation_added(annot, "Realce adicionado")
        except Exception as exc:
            messagebox.showerror("Não foi possível realçar", str(exc), parent=self.root)

    def _add_line_markup(self, rect: fitz.Rect, kind: str):
        page = self.doc.load_page(self.current_page)
        rgb = self._active_rgb()
        y = rect.y1 - max(1.0, rect.height * 0.08) if kind == "underline" else (rect.y0 + rect.y1) / 2
        try:
            annot = page.add_line_annot(fitz.Point(rect.x0, y), fitz.Point(rect.x1, y))
            annot.set_colors(stroke=rgb)
            annot.set_border(width=1.5)
            annot.set_info(title="Lumen PDF", subject="Sublinhado" if kind == "underline" else "Tachado", content="")
            annot.update()
            self._annotation_added(annot, "Sublinhado adicionado" if kind == "underline" else "Texto tachado")
        except Exception as exc:
            messagebox.showerror("Não foi possível marcar", str(exc), parent=self.root)

    def _commit_ink(self):
        if self.doc is None or not self.drag_points:
            return
        if len(self.drag_points) < 2:
            self.drag_points.clear()
            return
        try:
            page = self.doc.load_page(self.current_page)
            annot = page.add_ink_annot([[(point.x, point.y) for point in self.drag_points]])
            annot.set_colors(stroke=self._active_rgb())
            annot.set_border(width=2.0)
            annot.set_info(title="Lumen PDF", subject="Desenho à mão livre", content="")
            annot.update()
            self._annotation_added(annot, "Desenho adicionado")
        except Exception as exc:
            messagebox.showerror("Não foi possível desenhar", str(exc), parent=self.root)
        finally:
            self.drag_points.clear()

    def _add_comment(self, point: fitz.Point):
        text = simpledialog.askstring("Novo comentário", "Digite seu comentário para esta posição do PDF:", parent=self.root)
        if not text or not text.strip():
            return
        try:
            page = self.doc.load_page(self.current_page)
            annot = page.add_text_annot(point, text.strip())
            annot.set_info(title="Lumen PDF", subject="Comentário", content=text.strip())
            annot.update()
            self._annotation_added(annot, "Comentário adicionado")
        except Exception as exc:
            messagebox.showerror("Não foi possível comentar", str(exc), parent=self.root)

    def _annotation_added(self, annot: fitz.Annot, status: str):
        self.dirty = True
        self.page_image_cache.clear()
        self.undo_stack.append((self.current_page, annot.xref))
        self.refresh_annotations()
        self.render_current_page()
        self._set_status(status + " · salve o PDF para manter as alterações")

    def undo_last_annotation(self):
        if self.doc is None or not self.undo_stack:
            self._set_status("Não há marcações recentes para desfazer")
            return
        page_index, xref = self.undo_stack.pop()
        try:
            page = self.doc.load_page(page_index)
            annot = page.load_annot(xref)
            if annot is not None:
                page.delete_annot(annot)
                self.dirty = True
                self.page_image_cache.clear()
                self.refresh_annotations()
                self.go_to_page(page_index)
                self._set_status("Última marcação desfeita · salve para manter a alteração")
        except Exception as exc:
            messagebox.showerror("Não foi possível desfazer", str(exc), parent=self.root)

    def delete_selected_annotation(self):
        selected = self.annotation_tree.selection() if hasattr(self, "annotation_tree") else ()
        if not selected:
            self._set_status("Selecione uma marcação na aba Marcações")
            return
        item = selected[0]
        if item not in self.annotation_map:
            return
        page_index, xref = self.annotation_map[item]
        if not messagebox.askyesno("Excluir marcação", "Deseja excluir esta marcação do documento?", parent=self.root):
            return
        try:
            page = self.doc.load_page(page_index)
            annot = page.load_annot(xref)
            if annot is not None:
                page.delete_annot(annot)
            self.undo_stack = [(p, x) for p, x in self.undo_stack if not (p == page_index and x == xref)]
            self.dirty = True
            self.page_image_cache.clear()
            self.refresh_annotations()
            self.go_to_page(page_index)
            self._set_status("Marcação excluída · salve para manter a alteração")
        except Exception as exc:
            messagebox.showerror("Não foi possível excluir", str(exc), parent=self.root)

    def _copy_words_in_rect(self, rect: fitz.Rect):
        if rect.width < 3 and rect.height < 3:
            return
        page = self.doc.load_page(self.current_page)
        words = page.get_text("words")
        chosen = []
        for word in words:
            word_rect = fitz.Rect(word[:4])
            if word_rect.intersects(rect):
                chosen.append((round(word[1], 1), round(word[0], 1), str(word[4])))
        chosen.sort(key=lambda item: (item[0], item[1]))
        text = " ".join(item[2] for item in chosen).strip()
        if text:
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(text)
                self.root.update_idletasks()
                preview = text.replace("\n", " ")[:90]
                self._set_status(f"Texto copiado ({len(text)} caracteres): {preview}")
            except tk.TclError:
                self._set_status("Não foi possível acessar a área de transferência")
        else:
            self._set_status("Nenhum texto reconhecido nessa seleção. Em PDFs escaneados, pode ser necessário OCR externo.")

    def copy_page_text(self):
        if self.doc is None:
            return
        text = self.doc.load_page(self.current_page).get_text("text")
        if not text.strip():
            messagebox.showinfo("Copiar texto", "Não foi encontrado texto nesta página. Ela pode ser uma imagem digitalizada.", parent=self.root)
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update_idletasks()
        self._set_status(f"Texto da página {self.current_page + 1} copiado ({len(text)} caracteres)")

    def _show_canvas_context_menu(self, event):
        if self.doc is None:
            return
        menu = tk.Menu(self.root, tearoff=False, bg=COLORS["panel"], fg=COLORS["text"], activebackground=COLORS["accent_dark"], activeforeground=COLORS["text"])
        menu.add_command(label="Copiar texto da página", command=self.copy_page_text)
        menu.add_command(label="Adicionar comentário", command=lambda: self._context_comment(event))
        menu.add_command(label="Adicionar marcador", command=self.add_bookmark)
        menu.tk_popup(event.x_root, event.y_root)

    def _context_comment(self, event):
        cx, cy = self.page_canvas.canvasx(event.x), self.page_canvas.canvasy(event.y)
        point = self._canvas_to_page(cx, cy)
        if point is not None:
            self._add_comment(point)

    # -------------------------------- Busca ---------------------------------
    def _focus_search(self):
        self.search_entry.focus_set()
        self.search_entry.select_range(0, "end")

    def search_document(self):
        if self.doc is None:
            messagebox.showinfo("Buscar", "Abra um PDF primeiro.", parent=self.root)
            return
        query = self.search_var.get().strip()
        if not query:
            self._focus_search()
            return
        self.search_results = []
        self.search_result_index = -1
        self._set_status(f"Buscando ‘{query}’…")
        self.root.update_idletasks()
        try:
            for page_index in range(len(self.doc)):
                page = self.doc.load_page(page_index)
                for rect in page.search_for(query, quads=False):
                    self.search_results.append((page_index, fitz.Rect(rect)))
                    if len(self.search_results) >= 5000:
                        break
                if (page_index + 1) % 100 == 0:
                    self.status_var.set(f"Buscando… página {page_index + 1} de {len(self.doc)}")
                    self.root.update_idletasks()
                if len(self.search_results) >= 5000:
                    break
            if not self.search_results:
                self.render_current_page()
                self._set_status(f"Nenhum resultado para ‘{query}’")
                messagebox.showinfo("Busca concluída", f"Não encontrei ‘{query}’ neste PDF.\n\nEm documentos escaneados, a busca depende de OCR.", parent=self.root)
                return
            self.search_result_index = 0
            self.go_to_page(self.search_results[0][0])
            self._draw_search_overlays()
            self._set_status(f"{len(self.search_results)} resultado(s) para ‘{query}’ · use ↑ e ↓ para navegar")
        except Exception as exc:
            messagebox.showerror("Erro na busca", str(exc), parent=self.root)

    def move_search_result(self, direction: int):
        if not self.search_results:
            return
        self.search_result_index = (self.search_result_index + direction) % len(self.search_results)
        page_index = self.search_results[self.search_result_index][0]
        self.go_to_page(page_index)
        # render_current_page desenha as ocorrências; a atual usa uma borda distinta.
        self.page_canvas.delete("search-mark")
        self._draw_search_overlays()
        self._set_status(f"Resultado {self.search_result_index + 1} de {len(self.search_results)}")

    # ------------------------------ Marcadores -----------------------------
    def add_bookmark(self):
        if self.doc is None:
            messagebox.showinfo("Marcador", "Abra um PDF primeiro.", parent=self.root)
            return
        title = simpledialog.askstring("Adicionar marcador", f"Nome do marcador para a página {self.current_page + 1}:", parent=self.root)
        if not title or not title.strip():
            return
        try:
            toc = self.doc.get_toc(simple=False)
            toc.append([1, title.strip(), self.current_page + 1])
            self.doc.set_toc(toc)
            self.dirty = True
            self.refresh_outline()
            self._set_status(f"Marcador ‘{title.strip()}’ adicionado · salve o PDF para mantê-lo")
        except Exception as exc:
            messagebox.showerror("Não foi possível criar o marcador", str(exc), parent=self.root)

    def refresh_outline(self):
        if not hasattr(self, "outline_tree"):
            return
        for item in self.outline_tree.get_children(""):
            self.outline_tree.delete(item)
        self.outline_map.clear()
        if self.doc is None:
            return
        try:
            toc = self.doc.get_toc(simple=True)
        except Exception:
            toc = []
        if not toc:
            item = self.outline_tree.insert("", "end", text="Este PDF não tem sumário", values=("—",))
            self.outline_map[item] = 0
            return
        for i, row in enumerate(toc):
            level, title, page_num = row[:3]
            prefix = "  " * max(0, int(level) - 1)
            item = self.outline_tree.insert("", "end", iid=f"outline_{i}", text=prefix + str(title), values=(page_num,))
            self.outline_map[item] = max(0, int(page_num) - 1)

    def _jump_to_outline(self, _event=None):
        selection = self.outline_tree.selection()
        if not selection:
            return
        page = self.outline_map.get(selection[0])
        if page is not None and self.doc is not None:
            self.go_to_page(page)

    # ------------------------------ Anotações ------------------------------
    def refresh_annotations(self):
        if not hasattr(self, "annotation_tree"):
            return
        for item in self.annotation_tree.get_children(""):
            self.annotation_tree.delete(item)
        self.annotation_map.clear()
        if self.doc is None:
            self.annotation_count_var.set("0 marcações")
            return
        count = 0
        for page_index in range(len(self.doc)):
            try:
                page = self.doc.load_page(page_index)
                for annot in page.annots() or []:
                    count += 1
                    info = annot.info or {}
                    kind = annot.type[1] if annot.type else "Anotação"
                    content = (info.get("content") or "").strip().replace("\n", " ")
                    if not content:
                        subject = (info.get("subject") or "").strip()
                        content = subject or self._friendly_annotation_name(kind)
                    content = content[:115]
                    iid = f"ann_{page_index}_{annot.xref}"
                    self.annotation_tree.insert("", "end", iid=iid, values=(page_index + 1, self._short_kind(kind), content))
                    self.annotation_map[iid] = (page_index, annot.xref)
            except Exception:
                continue
        self.annotation_count_var.set(f"{count} marcação(ões)")

    @staticmethod
    def _friendly_annotation_name(kind: str) -> str:
        mapping = {
            "Square": "Realce / área", "Highlight": "Realce", "Underline": "Sublinhado",
            "StrikeOut": "Tachado", "Ink": "Desenho à mão livre", "Text": "Comentário",
            "FreeText": "Texto livre", "Line": "Linha", "Caret": "Inserção de texto",
            "Squiggly": "Sublinhado ondulado", "Stamp": "Carimbo", "Circle": "Círculo",
        }
        return mapping.get(kind, kind or "Anotação")

    @staticmethod
    def _short_kind(kind: str) -> str:
        mapping = {"Square": "Realce", "Highlight": "Realce", "Underline": "Sublinhar", "StrikeOut": "Tachar", "Ink": "Caneta", "Text": "Comentário", "FreeText": "Texto", "Line": "Linha", "Circle": "Círculo", "Squiggly": "Ondulado"}
        return mapping.get(kind, kind[:12] if kind else "Anotação")

    def _jump_to_annotation(self, _event=None):
        selection = self.annotation_tree.selection()
        if not selection:
            return
        info = self.annotation_map.get(selection[0])
        if info:
            self.go_to_page(info[0])

    def _annotation_context_menu(self, event):
        row = self.annotation_tree.identify_row(event.y)
        if row:
            self.annotation_tree.selection_set(row)
            self.annotation_menu.tk_popup(event.x_root, event.y_root)

    # ------------------------------- Utilidades ----------------------------
    def _set_status(self, message: str):
        self.status_var.set(message)

    def show_shortcuts(self):
        messagebox.showinfo(
            "Atalhos do Lumen PDF",
            "ARQUIVOS\n"
            "Ctrl + O   Abrir PDF\n"
            "Ctrl + S   Salvar PDF anotado\n\n"
            "LEITURA\n"
            "← / →      Página anterior / próxima\n"
            "Page Up / Page Down   Navegar páginas\n"
            "Ctrl + + / Ctrl + -   Zoom\n"
            "Ctrl + roda do mouse   Zoom\n"
            "Ctrl + F   Buscar texto\n\n"
            "MARCAÇÕES\n"
            "Arraste no documento para realçar, sublinhar ou tachar\n"
            "Use Caneta para desenhar à mão livre\n"
            "Selecione Comentário e clique no local desejado\n"
            "Ctrl + Z   Desfazer a última marcação criada\n\n"
            "Dica: as alterações ficam na memória até você salvar o PDF anotado.",
            parent=self.root,
        )

    def show_about(self):
        messagebox.showinfo(
            f"Sobre o {APP_NAME}",
            f"{APP_NAME} {APP_VERSION}\n\n"
            "Leitor de PDF leve com navegação, miniaturas, busca, seleção/cópia de texto, realces, sublinhados, tachados, caneta livre, comentários e marcadores.\n\n"
            "O processamento é local: seus documentos não são enviados para servidores.\n"
            "Feito com Python, Tkinter, PyMuPDF e Pillow.",
            parent=self.root,
        )

    def close_app(self):
        if self.doc is not None and self.dirty:
            answer = messagebox.askyesnocancel("Sair do Lumen PDF", "Você tem alterações não salvas. Deseja salvar antes de sair?", parent=self.root)
            if answer is None:
                return
            if answer and not self.save_pdf():
                return
        try:
            if self.doc is not None:
                self.doc.close()
        except Exception:
            pass
        self.root.destroy()


def main():
    root = tk.Tk()
    # Melhora renderização de fontes em telas HiDPI quando suportado.
    if platform.system() == "Windows":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    LumenPDFApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
