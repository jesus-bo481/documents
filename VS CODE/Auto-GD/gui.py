"""
Auto-GD — Interfaz gráfica v3.0
Integra: Memoria RETIE (Auto-GD) + Herramientas DXF (MCP AutoCAD) + Prompts
"""
import sys, threading, importlib, tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
from pathlib import Path
import io, contextlib, traceback

BASE_DIR = Path(__file__).parent
MCP_DIR  = BASE_DIR.parent / "MCP AUTOCAD"
OUT_DIR  = BASE_DIR / "output"
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(MCP_DIR))

# ── Paleta clara ───────────────────────────────────────────────────────────────
BG      = "#FAFAF9"
SURF    = "#FFFFFF"
SURF2   = "#F5F5F4"
BORDER  = "#E7E5E4"
BORDER2 = "#D6D3D1"
ACCENT  = "#D97706"
ACC_H   = "#B45309"
GREEN   = "#16A34A"
RED     = "#DC2626"
WARN    = "#CA8A04"
TEXT    = "#1C1917"
TEXT2   = "#44403C"
MUTED   = "#78716C"
HDR_BG  = "#292524"
SHELL   = "#1C1917"
SHELL2  = "#292524"

F_TITLE = ("Segoe UI", 14, "bold")
F_SEC   = ("Segoe UI", 10, "bold")
F_UI    = ("Segoe UI", 10)
F_SMALL = ("Segoe UI", 9)
F_LABEL = ("Segoe UI", 8)
F_BTN   = ("Segoe UI", 10, "bold")
F_LOG   = ("Consolas", 9)

_DXF_TOOLS = [
    ("strings",  "Generar Strings DC"),
    ("met_mom",  "Metrado DC — MOMOTUS"),
    ("met_iso",  "Metrado DC — ISIDORI"),
    ("mleader",  "Corregir MULTILEADER"),
]
_DXF_LABELS = [v for _, v in _DXF_TOOLS]
_DXF_KEY    = {v: k for k, v in _DXF_TOOLS}
_DXF_DESC   = {
    "strings": "Dibuja LWPOLYLINE + etiquetas IxSy + anotaciones MULTILEADER en el DXF",
    "met_mom":  "Calcula longitud de conductores DC (arquitectura tipo MOMOTUS)",
    "met_iso":  "Calcula longitud de conductores DC (arquitectura tipo ISIDORI / horizontal)",
    "mleader":  "Actualiza texto de MULTILEADER preservando estilo ISO-25 del template",
}

_PROMPT_TPLS = {
    "Strings DC — MOMOTUS": (
        "Genera strings DC para el archivo DXF adjunto.\n"
        "N inversores: 3 | Strings / inv: 26 | String inicial: 1\n"
        "Bajante: derecha | Bloque de panel: PANEL_615"
    ),
    "Metrado ISIDORI": (
        "Ejecuta metrado DC para el archivo DXF adjunto.\n"
        "N inversores: 5 | MAX strings / inv: 28\n"
        "Rellena con cero las filas sin conductor asignado."
    ),
    "Corregir MULTILEADER": (
        "Corrige el contenido de los MULTILEADER en el archivo DXF.\n"
        "Preservar estilo ISO-25 intacto — solo actualizar texto de conductores."
    ),
    "Memoria RETIE": (
        "Genera la memoria de calculo RETIE para el proyecto.\n"
        "Proyecto: {NOMBRE} | Ciudad: {CIUDAD}\n"
        "Temperatura min/max/prom: {TMIN}/{TMAX}/{TPROM} C"
    ),
}


# ── Estilos TTK ────────────────────────────────────────────────────────────────
def _ttk_style():
    s = ttk.Style()
    s.theme_use("clam")
    s.configure("TNotebook", background=BG, borderwidth=0, tabmargins=[0, 4, 0, 0])
    s.configure("TNotebook.Tab",
                background=SURF2, foreground=MUTED,
                padding=[18, 8], font=("Segoe UI", 9, "bold"), borderwidth=0)
    s.map("TNotebook.Tab",
          background=[("selected", SURF), ("active", BORDER)],
          foreground=[("selected", ACCENT), ("active", TEXT2)])
    s.configure("V.Vertical.TScrollbar",
                gripcount=0, background=BORDER2, troughcolor=BG,
                bordercolor=BG, arrowcolor=MUTED, arrowsize=10)
    s.map("V.Vertical.TScrollbar", background=[("active", MUTED)])
    s.configure("Amber.Horizontal.TProgressbar",
                troughcolor=SURF2, background=ACCENT,
                darkcolor=ACCENT, lightcolor=ACCENT, borderwidth=0)
    s.configure("TCombobox",
                fieldbackground=SURF2, background=BORDER,
                foreground=TEXT, arrowcolor=MUTED,
                lightcolor=BORDER, darkcolor=BORDER)
    s.map("TCombobox", fieldbackground=[("readonly", SURF2)])


# ── Widgets reutilizables ──────────────────────────────────────────────────────
class _HoverBtn(tk.Button):
    def __init__(self, parent, bg0, bg1, fg0, fg1=None, **kw):
        super().__init__(parent, bg=bg0, fg=fg0, relief="flat", bd=0,
                         cursor="hand2",
                         activebackground=bg1, activeforeground=fg1 or fg0, **kw)
        self._bg0, self._bg1 = bg0, bg1
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)

    def _enter(self, _):
        if str(self["state"]) != "disabled":
            self.config(bg=self._bg1)

    def _leave(self, _):
        self.config(bg=self._bg0)


def _scrollable(parent):
    wrap = tk.Frame(parent, bg=BG)
    wrap.pack(fill="both", expand=True)
    canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0)
    sb = ttk.Scrollbar(wrap, orient="vertical", command=canvas.yview,
                       style="V.Vertical.TScrollbar")
    canvas.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    body = tk.Frame(canvas, bg=BG, padx=24, pady=20)
    win  = canvas.create_window((0, 0), window=body, anchor="nw")
    body.bind("<Configure>",
              lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>",
                lambda e: canvas.itemconfig(win, width=e.width))
    canvas.bind_all("<MouseWheel>",
                    lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))
    return body


def _lbl(parent, text, muted=False, font=F_LABEL):
    return tk.Label(parent, text=text, bg=parent["bg"],
                    fg=MUTED if muted else TEXT2, font=font)


def _entry(parent, var, width=22):
    f = tk.Frame(parent, bg=SURF2, highlightbackground=BORDER2, highlightthickness=1)
    e = tk.Entry(f, textvariable=var, width=width,
                 bg=SURF2, fg=TEXT, insertbackground=ACCENT,
                 relief="flat", font=F_UI, bd=8)
    e.pack(fill="x")
    e.bind("<FocusIn>",  lambda _: f.config(highlightbackground=ACCENT))
    e.bind("<FocusOut>", lambda _: f.config(highlightbackground=BORDER2))
    return f, e


def _spinbox(parent, var, from_, to, width=7):
    f = tk.Frame(parent, bg=SURF2, highlightbackground=BORDER2, highlightthickness=1)
    sb = tk.Spinbox(f, from_=from_, to=to, textvariable=var, width=width,
                    bg=SURF2, fg=TEXT, buttonbackground=BORDER,
                    relief="flat", font=F_UI, bd=6, insertbackground=ACCENT)
    sb.pack(fill="x")
    sb.bind("<FocusIn>",  lambda _: f.config(highlightbackground=ACCENT))
    sb.bind("<FocusOut>", lambda _: f.config(highlightbackground=BORDER2))
    return f


def _card(parent, title, color=ACCENT, subtitle=None):
    outer = tk.Frame(parent, bg=SURF, highlightbackground=BORDER, highlightthickness=1)
    tk.Frame(outer, bg=color, height=3).pack(fill="x")
    inner = tk.Frame(outer, bg=SURF, padx=16, pady=14)
    inner.pack(fill="both", expand=True)
    hdr = tk.Frame(inner, bg=SURF)
    hdr.pack(fill="x", pady=(0, 10))
    tk.Label(hdr, text=title, bg=SURF, fg=TEXT, font=F_SEC).pack(side="left")
    if subtitle:
        tk.Label(hdr, text=subtitle, bg=SURF, fg=MUTED, font=F_SMALL).pack(
            side="left", padx=(10, 0), pady=(2, 0))
    return inner


def _field(parent, label, var, width=22, row=None, col=None, span=1):
    wrap = tk.Frame(parent, bg=SURF)
    _lbl(wrap, label, muted=True).pack(anchor="w", pady=(0, 3))
    f, _ = _entry(wrap, var, width)
    f.pack(fill="x")
    if row is not None:
        wrap.grid(row=row, column=col, columnspan=span, sticky="ew", padx=5, pady=5)
    return wrap


def _file_field(parent, label, var, types=None, is_dir=False, row=0):
    wrap = tk.Frame(parent, bg=SURF)
    _lbl(wrap, label, muted=True).pack(anchor="w", pady=(0, 3))
    row_f = tk.Frame(wrap, bg=SURF)
    row_f.pack(fill="x")
    box = tk.Frame(row_f, bg=SURF2, highlightbackground=BORDER2, highlightthickness=1)
    box.pack(side="left", fill="x", expand=True)
    e = tk.Entry(box, textvariable=var, bg=SURF2, fg=TEXT,
                 insertbackground=ACCENT, relief="flat", font=F_SMALL, bd=8)
    e.pack(fill="x")
    e.bind("<FocusIn>",  lambda _: box.config(highlightbackground=ACCENT))
    e.bind("<FocusOut>", lambda _: box.config(highlightbackground=BORDER2))

    def _browse():
        p = filedialog.askdirectory() if is_dir else \
            filedialog.askopenfilename(filetypes=types or [("Todos", "*.*")])
        if p:
            var.set(p)

    _HoverBtn(row_f, SURF2, BORDER, MUTED, TEXT,
              text="...", font=("Segoe UI", 11),
              highlightbackground=BORDER2, highlightthickness=1,
              padx=10, pady=3,
              command=_browse).pack(side="left", padx=(5, 0))

    if row is not None:
        wrap.grid(row=row, column=0, columnspan=3, sticky="ew", pady=5)
    return wrap


def _checkbox(parent, var, text, color=None):
    return tk.Checkbutton(parent, variable=var, text=text,
                          bg=parent["bg"], fg=color or TEXT2, font=F_UI,
                          selectcolor=parent["bg"], activebackground=parent["bg"],
                          relief="flat", bd=0, highlightthickness=0,
                          activeforeground=TEXT)


# ── Aplicación principal ───────────────────────────────────────────────────────
class AutoGDApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Auto-GD  v3.0  —  Herramientas FV")
        self.configure(bg=BG)
        self.geometry("880x980")
        self.resizable(True, True)
        self.minsize(720, 740)
        _ttk_style()

        # Variables RETIE
        self.v_nombre   = tk.StringVar(value="LA MARTINA 1")
        self.v_ciudad   = tk.StringVar(value="PARATEBUENO")
        self.v_depto    = tk.StringVar(value="CUNDINAMARCA")
        self.v_fecha    = tk.StringVar(value="2026-03-31")
        self.v_tmin     = tk.StringVar(value="18")
        self.v_tmax     = tk.StringVar(value="30")
        self.v_tprom    = tk.StringVar(value="28")
        self.v_paneles  = tk.StringVar(value="24")
        self.v_modulos  = tk.StringVar(value="1728")
        self.v_num_inv  = tk.IntVar(value=3)
        self.v_ac_inv   = []
        self.v_metrado    = tk.StringVar()
        self.v_excel_base = tk.StringVar()
        self.v_word_base  = tk.StringVar()
        self.v_salida     = tk.StringVar(value=str(OUT_DIR))
        self.cb_fase1   = tk.BooleanVar(value=True)
        self.cb_fase2   = tk.BooleanVar(value=True)

        # Variables DXF
        self.v_dxf_tool    = tk.StringVar(value=_DXF_LABELS[0])
        self.v_dxf_in      = tk.StringVar()
        self.v_dxf_out_dir = tk.StringVar(value=str(MCP_DIR / "output"))
        self.v_dxf_n_inv   = tk.IntVar(value=3)
        self.v_dxf_str_inv = tk.IntVar(value=26)
        self.v_dxf_start   = tk.IntVar(value=1)
        self.v_dxf_max_str = tk.IntVar(value=28)
        self.v_dxf_bajante = tk.StringVar(value="R")
        self.v_dxf_panel   = tk.StringVar(value="PANEL_615")

        # Variable prompts
        self.cb_incl_prompt = tk.BooleanVar(value=False)

        self._build()

    # ── Construccion ──────────────────────────────────────────────────────────
    def _build(self):
        self._make_header()
        self._make_notebook()
        self._make_log()

    def _make_header(self):
        hdr = tk.Frame(self, bg=HDR_BG, padx=24, pady=14)
        hdr.pack(fill="x")
        left = tk.Frame(hdr, bg=HDR_BG)
        left.pack(side="left")
        top = tk.Frame(left, bg=HDR_BG)
        top.pack(anchor="w")
        tk.Label(top, text="☀", bg=HDR_BG, fg=ACCENT,
                 font=("Segoe UI", 16)).pack(side="left", padx=(0, 8))
        tk.Label(top, text="Auto-GD", bg=HDR_BG, fg="#FAFAF9",
                 font=F_TITLE).pack(side="left")
        tk.Label(top, text="  v3.0", bg=HDR_BG, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left", pady=(5, 0))
        tk.Label(left,
                 text="Memoria RETIE  |  Strings DC  |  Metrado  |  MULTILEADER",
                 bg=HDR_BG, fg=MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(4, 0))
        tk.Frame(self, bg=ACCENT, height=2).pack(fill="x")

    def _make_notebook(self):
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)

        f1 = tk.Frame(nb, bg=BG)
        nb.add(f1, text="  ☀  Memoria RETIE  ")
        self._tab_retie(f1)

        f2 = tk.Frame(nb, bg=BG)
        nb.add(f2, text="  ⚡  Herramientas DXF  ")
        self._tab_dxf(f2)

        f3 = tk.Frame(nb, bg=BG)
        nb.add(f3, text="  📝  Prompts / Notas  ")
        self._tab_prompts(f3)

    # ── Tab 1: Memoria RETIE ──────────────────────────────────────────────────
    def _tab_retie(self, parent):
        body = _scrollable(parent)
        self._card_proyecto(body)
        self._card_archivos(body)
        self._card_ac(body)
        self._action_retie(body)

    def _card_proyecto(self, body):
        card = _card(body, "Datos del proyecto", ACCENT)
        card.master.pack(fill="x", pady=(0, 12))
        g = tk.Frame(card, bg=SURF)
        g.pack(fill="x")
        g.columnconfigure((0, 1, 2), weight=1)

        _field(g, "Nombre del proyecto", self.v_nombre, row=0, col=0, span=2)
        _field(g, "Fecha  (YYYY-MM-DD)", self.v_fecha,  row=0, col=2)
        _field(g, "Ciudad",              self.v_ciudad, row=1, col=0)
        _field(g, "Departamento",        self.v_depto,  row=1, col=1)

        t = tk.Frame(g, bg=SURF)
        t.grid(row=1, column=2, sticky="ew", padx=5, pady=5)
        _lbl(t, "Temperatura  min / max / prom  (°C)", muted=True).pack(
            anchor="w", pady=(0, 3))
        t_row = tk.Frame(t, bg=SURF)
        t_row.pack(anchor="w")
        for v in (self.v_tmin, self.v_tmax, self.v_tprom):
            f, _ = _entry(t_row, v, width=5)
            f.pack(side="left", padx=(0, 5))

        _field(g, "Paneles en serie", self.v_paneles, width=8,  row=2, col=0)
        _field(g, "Total de modulos", self.v_modulos, width=10, row=2, col=1)

        inv = tk.Frame(g, bg=SURF)
        inv.grid(row=2, column=2, sticky="ew", padx=5, pady=5)
        _lbl(inv, "Numero de inversores", muted=True).pack(anchor="w", pady=(0, 3))
        tk.Spinbox(inv, from_=1, to=10, width=5, textvariable=self.v_num_inv,
                   bg=SURF2, fg=TEXT, buttonbackground=BORDER, relief="flat",
                   font=F_UI, highlightbackground=BORDER2, highlightthickness=1,
                   insertbackground=ACCENT,
                   command=self._rebuild_ac).pack(anchor="w")

    def _card_archivos(self, body):
        card = _card(body, "Archivos de entrada", WARN)
        card.master.pack(fill="x", pady=(0, 12))
        g = tk.Frame(card, bg=SURF)
        g.pack(fill="x")
        g.columnconfigure(0, weight=1)
        _file_field(g, "Metrado de cables  (.xlsx)",
                    self.v_metrado,    [("Excel", "*.xlsx *.xls")], row=0)
        _file_field(g, "Plantilla de calculo  (.xlsm)",
                    self.v_excel_base, [("Excel macro", "*.xlsm")], row=1)
        _file_field(g, "Memoria base  (.docx)",
                    self.v_word_base,  [("Word", "*.docx")],        row=2)
        _file_field(g, "Carpeta de salida",
                    self.v_salida, is_dir=True, row=3)

    def _card_ac(self, body):
        card = _card(body, "Longitud cable AC por inversor  (m)", GREEN)
        card.master.pack(fill="x", pady=(0, 12))
        self.ac_container = tk.Frame(card, bg=SURF)
        self.ac_container.pack(fill="x")
        self._rebuild_ac()

    def _rebuild_ac(self):
        for w in self.ac_container.winfo_children():
            w.destroy()
        n = self.v_num_inv.get()
        while len(self.v_ac_inv) < n:
            self.v_ac_inv.append(tk.StringVar(value="0"))
        self.v_ac_inv = self.v_ac_inv[:n]
        for i in range(n):
            col = tk.Frame(self.ac_container, bg=SURF)
            col.pack(side="left", padx=(0, 14))
            _lbl(col, f"Inv. {i+1}", muted=True).pack(anchor="w", pady=(0, 3))
            f, _ = _entry(col, self.v_ac_inv[i], width=7)
            f.pack()

    def _action_retie(self, body):
        card = _card(body, "Procesos a ejecutar", MUTED)
        card.master.pack(fill="x", pady=(0, 12))

        cb_row = tk.Frame(card, bg=SURF)
        cb_row.pack(fill="x", pady=(0, 12))
        _checkbox(cb_row, self.cb_fase1,
                  "  Fase 1 — Llenar Excel de calculo", ACCENT).pack(
            side="left", padx=(0, 24))
        _checkbox(cb_row, self.cb_fase2,
                  "  Fase 2+3 — Capturar tablas → Word", GREEN).pack(side="left")

        bar = tk.Frame(card, bg=SURF)
        bar.pack(fill="x")
        self.btn_retie = _HoverBtn(bar, ACCENT, ACC_H, "#FFFFFF",
                                   text="▶  Ejecutar pipeline",
                                   font=F_BTN, padx=28, pady=10,
                                   command=self._run_retie)
        self.btn_retie.pack(side="left")
        self.pb_retie = ttk.Progressbar(bar, maximum=100, length=160,
                                        mode="indeterminate",
                                        style="Amber.Horizontal.TProgressbar")

    # ── Tab 2: DXF ────────────────────────────────────────────────────────────
    def _tab_dxf(self, parent):
        body = _scrollable(parent)

        # Selector de herramienta
        sel = _card(body, "Seleccionar herramienta DXF", ACCENT)
        sel.master.pack(fill="x", pady=(0, 12))
        sel_row = tk.Frame(sel, bg=SURF)
        sel_row.pack(fill="x")
        _lbl(sel_row, "Proceso:", muted=True).pack(side="left", padx=(0, 10))
        tool_cb = ttk.Combobox(sel_row, textvariable=self.v_dxf_tool,
                               values=_DXF_LABELS, state="readonly",
                               width=26, font=F_UI)
        tool_cb.pack(side="left")
        self._tool_desc = tk.Label(sel_row, text=_DXF_DESC["strings"],
                                   bg=SURF, fg=MUTED, font=F_SMALL,
                                   wraplength=300, justify="left")
        self._tool_desc.pack(side="left", padx=(14, 0))

        # Archivos I/O
        io_card = _card(body, "Archivos", WARN)
        io_card.master.pack(fill="x", pady=(0, 12))
        g_io = tk.Frame(io_card, bg=SURF)
        g_io.pack(fill="x")
        g_io.columnconfigure(0, weight=1)
        _file_field(g_io, "DXF de entrada  (.dxf)",
                    self.v_dxf_in, [("DXF", "*.dxf")], row=0)
        _file_field(g_io, "Carpeta de salida",
                    self.v_dxf_out_dir, is_dir=True, row=1)

        # Frame de parametros dinamicos
        self._dxf_params_frame = tk.Frame(body, bg=BG)
        self._dxf_params_frame.pack(fill="x")
        self._build_dxf_params()

        # Accion
        act = _card(body, "Ejecutar", MUTED)
        act.master.pack(fill="x", pady=(0, 12))
        act_bar = tk.Frame(act, bg=SURF)
        act_bar.pack(fill="x")
        self.btn_dxf = _HoverBtn(act_bar, ACCENT, ACC_H, "#FFFFFF",
                                  text="▶  Ejecutar herramienta",
                                  font=F_BTN, padx=28, pady=10,
                                  command=self._run_dxf)
        self.btn_dxf.pack(side="left")
        self.pb_dxf = ttk.Progressbar(act_bar, maximum=100, length=160,
                                       mode="indeterminate",
                                       style="Amber.Horizontal.TProgressbar")

        # Conectar trace despues de construir todo
        self.v_dxf_tool.trace_add("write", self._on_tool_change)

    def _build_dxf_params(self):
        # Params: Strings DC
        self._pf_strings = _card(self._dxf_params_frame,
                                  "Parametros — Strings DC", ACCENT)
        self._pf_strings.master.pack(fill="x", pady=(0, 12))
        g = tk.Frame(self._pf_strings, bg=SURF)
        g.pack(fill="x")
        g.columnconfigure((0, 1, 2, 3), weight=1)
        for (label, var, from_, to), col in zip([
            ("N° inversores",   self.v_dxf_n_inv,   1, 20),
            ("Strings / inv.",  self.v_dxf_str_inv, 1, 60),
            ("String inicial",  self.v_dxf_start,   1, 99),
        ], range(3)):
            wrap = tk.Frame(g, bg=SURF)
            wrap.grid(row=0, column=col, sticky="ew", padx=5, pady=5)
            _lbl(wrap, label, muted=True).pack(anchor="w", pady=(0, 3))
            _spinbox(wrap, var, from_, to).pack(fill="x")

        wrap_baj = tk.Frame(g, bg=SURF)
        wrap_baj.grid(row=0, column=3, sticky="ew", padx=5, pady=5)
        _lbl(wrap_baj, "Bajante (R/L)", muted=True).pack(anchor="w", pady=(0, 3))
        f, _ = _entry(wrap_baj, self.v_dxf_bajante, width=4)
        f.pack(fill="x")

        wrap_pnl = tk.Frame(self._pf_strings, bg=SURF)
        wrap_pnl.pack(fill="x", padx=5, pady=(0, 4))
        _lbl(wrap_pnl, "Nombre del bloque de panel", muted=True).pack(
            anchor="w", pady=(0, 3))
        f2, _ = _entry(wrap_pnl, self.v_dxf_panel, width=20)
        f2.pack(anchor="w")

        # Params: Metrado ISIDORI
        self._pf_iso = _card(self._dxf_params_frame,
                              "Parametros — Metrado ISIDORI", ACCENT)
        self._pf_iso.master.pack(fill="x", pady=(0, 12))
        g2 = tk.Frame(self._pf_iso, bg=SURF)
        g2.pack(fill="x")
        g2.columnconfigure((0, 1), weight=1)
        for (label, var, from_, to), col in zip([
            ("N° inversores",    self.v_dxf_n_inv,   1, 20),
            ("MAX strings/inv.", self.v_dxf_max_str, 1, 80),
        ], range(2)):
            wrap = tk.Frame(g2, bg=SURF)
            wrap.grid(row=0, column=col, sticky="ew", padx=5, pady=5)
            _lbl(wrap, label, muted=True).pack(anchor="w", pady=(0, 3))
            _spinbox(wrap, var, from_, to).pack(fill="x")

        self._on_tool_change()

    def _on_tool_change(self, *_):
        tool = _DXF_KEY.get(self.v_dxf_tool.get(), "strings")
        self._tool_desc.config(text=_DXF_DESC.get(tool, ""))
        if tool == "strings":
            self._pf_strings.master.pack(fill="x", pady=(0, 12))
        else:
            self._pf_strings.master.pack_forget()
        if tool == "met_iso":
            self._pf_iso.master.pack(fill="x", pady=(0, 12))
        else:
            self._pf_iso.master.pack_forget()

    # ── Tab 3: Prompts ────────────────────────────────────────────────────────
    def _tab_prompts(self, parent):
        body = _scrollable(parent)

        card = _card(body, "Instrucciones / Prompt para Claude",
                     ACCENT, subtitle="— copia este texto en Claude Code")
        card.master.pack(fill="x", pady=(0, 12))

        # Fila de plantillas
        tpl_row = tk.Frame(card, bg=SURF)
        tpl_row.pack(fill="x", pady=(0, 10))
        _lbl(tpl_row, "Cargar plantilla:", muted=True).pack(side="left", padx=(0, 10))
        self._tpl_var = tk.StringVar(value="Seleccionar...")
        tpl_cb = ttk.Combobox(tpl_row, textvariable=self._tpl_var,
                               values=list(_PROMPT_TPLS.keys()),
                               state="readonly", width=30, font=F_SMALL)
        tpl_cb.pack(side="left")

        def _load_tpl(*_):
            key = self._tpl_var.get()
            if key in _PROMPT_TPLS:
                self.prompt_box.delete("1.0", "end")
                self.prompt_box.insert("1.0", _PROMPT_TPLS[key])

        tpl_cb.bind("<<ComboboxSelected>>", _load_tpl)

        # Area de texto
        txt_frame = tk.Frame(card, bg=SURF2,
                             highlightbackground=BORDER2, highlightthickness=1)
        txt_frame.pack(fill="both", expand=True, pady=(0, 10))
        self.prompt_box = tk.Text(txt_frame, height=12,
                                  bg=SURF2, fg=TEXT, font=F_UI,
                                  relief="flat", wrap="word",
                                  insertbackground=ACCENT,
                                  selectbackground=ACCENT,
                                  selectforeground="#FFFFFF",
                                  padx=12, pady=10)
        self.prompt_box.bind(
            "<FocusIn>",  lambda _: txt_frame.config(highlightbackground=ACCENT))
        self.prompt_box.bind(
            "<FocusOut>", lambda _: txt_frame.config(highlightbackground=BORDER2))
        vsb = ttk.Scrollbar(txt_frame, command=self.prompt_box.yview,
                            style="V.Vertical.TScrollbar")
        self.prompt_box.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.prompt_box.pack(fill="both", expand=True)

        # Barra inferior
        btn_row = tk.Frame(card, bg=SURF)
        btn_row.pack(fill="x")
        _checkbox(btn_row, self.cb_incl_prompt,
                  "  Incluir estas notas en el log al ejecutar").pack(side="left")

        def _copiar():
            txt = self.prompt_box.get("1.0", "end").strip()
            self.clipboard_clear()
            self.clipboard_append(txt)

        _HoverBtn(btn_row, BORDER, BORDER2, TEXT2,
                  text="Copiar al portapapeles", font=F_SMALL,
                  padx=12, pady=6, command=_copiar).pack(side="right")

        # Instrucciones de uso
        tip = _card(body, "Como usar el espacio de prompts", MUTED)
        tip.master.pack(fill="x", pady=(0, 12))
        tips = [
            "1. Escribe o carga una plantilla con la configuracion del proceso que necesitas.",
            "2. Copia el texto y pegalo en Claude Code para que interprete los parametros.",
            "3. Activa 'Incluir en log' para que quede registrado en cada ejecucion local.",
            "4. Puedes usar este espacio como bitacora de parametros del proyecto.",
        ]
        for tip_txt in tips:
            tk.Label(tip, text=tip_txt, bg=SURF, fg=TEXT2, font=F_SMALL,
                     anchor="w", justify="left").pack(fill="x", pady=2)

    # ── Log compartido ────────────────────────────────────────────────────────
    def _make_log(self):
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")
        shell = tk.Frame(self, bg=SHELL)
        shell.pack(fill="both", expand=False)

        tbar = tk.Frame(shell, bg=SHELL2, pady=6, padx=10)
        tbar.pack(fill="x")
        for c in (RED, WARN, GREEN):
            tk.Frame(tbar, bg=c, width=11, height=11).pack(
                side="left", padx=(0, 5))
        tk.Label(tbar, text="pipeline output",
                 bg=SHELL2, fg=MUTED, font=F_LABEL).pack(
            side="left", padx=(10, 0))
        _HoverBtn(tbar, SHELL2, SHELL, MUTED, TEXT2,
                  text="limpiar", font=F_LABEL, padx=8, pady=2,
                  command=self._clear_log).pack(side="right")

        inner = tk.Frame(shell, bg=SHELL)
        inner.pack(fill="both", expand=True)
        self.log = tk.Text(inner, height=13, bg=SHELL, fg="#D6D3D1",
                           font=F_LOG, relief="flat", wrap="word",
                           state="disabled", insertbackground=TEXT,
                           selectbackground=SHELL2, padx=12, pady=10)
        vsb = ttk.Scrollbar(inner, command=self.log.yview,
                            style="V.Vertical.TScrollbar")
        self.log.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.log.pack(fill="both", expand=True)

        self.log.tag_configure("ok",      foreground=GREEN)
        self.log.tag_configure("err",     foreground=RED)
        self.log.tag_configure("accent",  foreground=ACCENT)
        self.log.tag_configure("muted",   foreground=MUTED)
        self.log.tag_configure("warning", foreground=WARN)

    # ── Helpers log / botones ─────────────────────────────────────────────────
    def _log(self, msg, tag=None):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n", tag or "")
        self.log.see("end")
        self.log.configure(state="disabled")
        self.update_idletasks()

    def _clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _log_prompt(self):
        if self.cb_incl_prompt.get():
            txt = self.prompt_box.get("1.0", "end").strip()
            if txt:
                self._log("NOTAS:", "accent")
                for line in txt.splitlines():
                    self._log("  " + line, "muted")
                self._log("", None)

    def _btn_lock(self, btn, pb, label="  Ejecutando..."):
        btn._bg0 = SURF2
        btn.configure(state="disabled", text=label,
                      bg=SURF2, fg=MUTED, cursor="arrow")
        pb.pack(side="left", padx=(12, 0))
        pb.start(10)

    def _btn_unlock(self, btn, pb, label="▶  Ejecutar"):
        pb.stop()
        pb.pack_forget()
        btn._bg0 = ACCENT
        btn.configure(state="normal", text=label,
                      bg=ACCENT, fg="#FFFFFF", cursor="hand2")

    # ── Run RETIE ─────────────────────────────────────────────────────────────
    def _run_retie(self):
        if not self.cb_fase1.get() and not self.cb_fase2.get():
            messagebox.showwarning("Sin proceso",
                                   "Selecciona al menos una fase para ejecutar.")
            return
        errs = self._validar_retie()
        if errs:
            messagebox.showerror("Campos invalidos", "\n".join(errs))
            return
        self._btn_lock(self.btn_retie, self.pb_retie)
        self._clear_log()
        self._log_prompt()
        threading.Thread(target=self._pipeline_retie, daemon=True).start()

    def _validar_retie(self):
        err = []
        if not self.v_nombre.get().strip():
            err.append("Falta el nombre del proyecto.")
        try:
            datetime.strptime(self.v_fecha.get().strip(), "%Y-%m-%d")
        except ValueError:
            err.append("Fecha invalida (usa YYYY-MM-DD).")
        for lbl, var in [("Temp. minima", self.v_tmin),
                         ("Temp. maxima", self.v_tmax),
                         ("Temp. promedio", self.v_tprom)]:
            try:
                float(var.get())
            except ValueError:
                err.append(f"{lbl} no es un numero valido.")
        for i, v in enumerate(self.v_ac_inv):
            try:
                float(v.get())
            except ValueError:
                err.append(f"Longitud AC inversor {i+1} no es valida.")
        for nombre, var in [("Metrado Excel",     self.v_metrado),
                            ("Plantilla Excel",   self.v_excel_base),
                            ("Memoria Word base", self.v_word_base)]:
            if var.get() and not Path(var.get()).exists():
                err.append(f"Archivo no encontrado: {nombre}")
        return err

    def _pipeline_retie(self):
        try:
            from auto_gd import leer_metrado, llenar_excel
            from capturar_tablas import ejecutar as cap_exec, TABLA_MAP

            fecha = datetime.strptime(self.v_fecha.get().strip(), "%Y-%m-%d")
            proyecto = {
                "nombre":        self.v_nombre.get().strip().upper(),
                "ciudad":        self.v_ciudad.get().strip().upper(),
                "departamento":  self.v_depto.get().strip().upper(),
                "fecha":         fecha,
                "temp_min":      float(self.v_tmin.get()),
                "temp_max":      float(self.v_tmax.get()),
                "temp_prom":     float(self.v_tprom.get()),
                "long_ac_inv":   [float(v.get()) for v in self.v_ac_inv],
                "paneles_serie": int(self.v_paneles.get()),
                "modulos":       int(self.v_modulos.get()),
            }
            slug      = proyecto["nombre"].replace(" ", "_")
            fecha_str = fecha.strftime("%Y%m%d")
            out_dir   = Path(self.v_salida.get())
            out_dir.mkdir(parents=True, exist_ok=True)
            excel_out = str(out_dir / f"PRGD-CALCULO-{slug}-{fecha_str}.xlsm")
            word_out  = str(out_dir / f"PRGD-MEMORIA-{slug}-{fecha_str}.docx")

            if self.cb_fase1.get():
                self._log("=" * 54, "accent")
                self._log("  FASE 1 — Llenando Excel de calculo", "accent")
                self._log("=" * 54, "accent")
                metrado = leer_metrado(self.v_metrado.get())
                self._log(f"  Metrado cargado: {len(metrado)} strings", "muted")
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    llenar_excel(metrado, proyecto, self.v_excel_base.get(), excel_out)
                for line in buf.getvalue().splitlines():
                    tag = "ok" if any(x in line for x in ["OK", "ok", "✓"]) else "muted"
                    self._log("  " + line, tag)

            if self.cb_fase2.get():
                self._log("\n" + "=" * 54, "accent")
                self._log("  FASE 2+3 — Captura de tablas → Word", "accent")
                self._log("=" * 54, "accent")
                buf2 = io.StringIO()
                with contextlib.redirect_stdout(buf2):
                    cap_exec(excel_out, self.v_word_base.get(), word_out, TABLA_MAP,
                             paneles_serie=proyecto["paneles_serie"],
                             proyecto_info=proyecto)
                for line in buf2.getvalue().splitlines():
                    if "[OK]" in line or "OK" in line:   tag = "ok"
                    elif "[ERROR]" in line:               tag = "err"
                    elif "[ADVERTENCIA]" in line:         tag = "warning"
                    else:                                 tag = "muted"
                    self._log("  " + line, tag)

            self._log("\n  OK  PROCESO COMPLETADO", "ok")
            if self.cb_fase1.get():
                self._log(f"     Excel  →  {excel_out}", "muted")
            if self.cb_fase2.get():
                self._log(f"     Word   →  {word_out}", "muted")

        except Exception:
            self._log("\n[ERROR CRITICO]", "err")
            self._log(traceback.format_exc(), "err")
        finally:
            self.after(0, lambda: self._btn_unlock(
                self.btn_retie, self.pb_retie, "▶  Ejecutar pipeline"))

    # ── Run DXF ───────────────────────────────────────────────────────────────
    def _run_dxf(self):
        dxf_in = self.v_dxf_in.get().strip()
        if not dxf_in or not Path(dxf_in).exists():
            messagebox.showerror("Archivo invalido",
                                 "Selecciona un archivo DXF de entrada valido.")
            return
        self._btn_lock(self.btn_dxf, self.pb_dxf)
        self._clear_log()
        self._log_prompt()
        out_dir = self.v_dxf_out_dir.get().strip() or str(MCP_DIR / "output")
        tool    = _DXF_KEY.get(self.v_dxf_tool.get(), "strings")
        threading.Thread(target=self._pipeline_dxf,
                         args=(tool, dxf_in, out_dir), daemon=True).start()

    def _pipeline_dxf(self, tool, dxf_in, out_dir):
        try:
            Path(out_dir).mkdir(parents=True, exist_ok=True)
            dxf_stem = Path(dxf_in).stem

            if tool == "strings":
                self._log("=" * 54, "accent")
                self._log("  STRINGS DC — Conductores + IxSy + MULTILEADER", "accent")
                self._log("=" * 54, "accent")
                from generate_strings_dxf import run_generate_strings
                output = str(Path(out_dir) / f"{dxf_stem}_strings.dxf")
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    run_generate_strings(
                        source_dxf      = dxf_in,
                        output_dxf      = output,
                        bajante_side    = self.v_dxf_bajante.get().strip().upper() or "R",
                        panel_block     = self.v_dxf_panel.get().strip() or "PANEL_615",
                        num_inversores  = self.v_dxf_n_inv.get(),
                        strings_per_inv = self.v_dxf_str_inv.get(),
                        start_from      = str(self.v_dxf_start.get()),
                    )
                self._dump_buf(buf)
                self._log(f"\n  OK  →  {output}", "ok")

            elif tool == "met_mom":
                self._log("=" * 54, "accent")
                self._log("  METRADO DC — estilo MOMOTUS", "accent")
                self._log("=" * 54, "accent")
                import metrado_strings_dxf as mod
                importlib.reload(mod)
                mod.SOURCE      = dxf_in
                mod.OUTPUT_XLSX = str(Path(out_dir) / f"metrado_{dxf_stem}.xlsx")
                mod.OUTPUT_CSV  = str(Path(out_dir) / f"metrado_{dxf_stem}.csv")
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    mod.main()
                self._dump_buf(buf)
                self._log(f"\n  OK  →  {mod.OUTPUT_XLSX}", "ok")

            elif tool == "met_iso":
                self._log("=" * 54, "accent")
                self._log("  METRADO DC — estilo ISIDORI", "accent")
                self._log("=" * 54, "accent")
                import metrado_isidori_dxf as mod
                importlib.reload(mod)
                mod.SOURCE         = dxf_in
                mod.OUTPUT_XLSX    = str(Path(out_dir) / f"metrado_{dxf_stem}.xlsx")
                mod.OUTPUT_CSV     = str(Path(out_dir) / f"metrado_{dxf_stem}.csv")
                mod.NUM_INVERSORES = self.v_dxf_n_inv.get()
                mod.MAX_STRINGS    = self.v_dxf_max_str.get()
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    mod.main()
                self._dump_buf(buf)
                self._log(f"\n  OK  →  {mod.OUTPUT_XLSX}", "ok")

            elif tool == "mleader":
                self._log("=" * 54, "accent")
                self._log("  FIX MULTILEADER — corrigiendo contenido", "accent")
                self._log("=" * 54, "accent")
                import fix_mleader_content as mod
                importlib.reload(mod)
                mod.SOURCE = dxf_in
                mod.OUTPUT = str(Path(out_dir) / f"{dxf_stem}_fixed.dxf")
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    mod.main()
                self._dump_buf(buf)
                self._log(f"\n  OK  →  {mod.OUTPUT}", "ok")

        except Exception:
            self._log("\n[ERROR CRITICO]", "err")
            self._log(traceback.format_exc(), "err")
        finally:
            self.after(0, lambda: self._btn_unlock(
                self.btn_dxf, self.pb_dxf, "▶  Ejecutar herramienta"))

    def _dump_buf(self, buf):
        for line in buf.getvalue().splitlines():
            if "ERROR" in line:   tag = "err"
            elif "WARN" in line:  tag = "warning"
            elif "OK" in line:    tag = "ok"
            else:                 tag = "muted"
            self._log("  " + line, tag)


# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = AutoGDApp()
    app.mainloop()
