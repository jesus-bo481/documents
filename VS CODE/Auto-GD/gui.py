"""
Auto-GD — Interfaz gráfica v4.0
Diseño: sidebar + contenido principal, espejo de la web app.
"""
import sys, threading, importlib, tkinter as tk
from tkinter import ttk, filedialog
from datetime import datetime
from pathlib import Path
import io, contextlib, traceback

BASE_DIR = Path(__file__).parent
MCP_DIR  = BASE_DIR.parent / "MCP AUTOCAD"
OUT_DIR  = BASE_DIR / "output"
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(MCP_DIR))

# ── Paleta idéntica a la web ───────────────────────────────────────────────────
SB_BG   = "#F0EFEB"
SB_BD   = "#E2E1DC"
BG      = "#FFFFFF"
SURF    = "#FAFAF8"
BORDER  = "#E5E5E3"
INP_BD  = "#D4D4D0"
ACCENT  = "#D97706"
ACC_H   = "#B45309"
GREEN   = "#059669"
GREEN_BG= "#ECFDF5"
RED     = "#DC2626"
WARN    = "#B45309"
TEXT    = "#1A1A1A"
TEXT2   = "#404040"
MUTED   = "#737373"
LIGHT   = "#A3A3A3"
HOVER   = "#E8E7E3"
ACTIVE_C= "#E0DFD9"

F_BRAND = ("Segoe UI", 13, "bold")
F_NAV   = ("Segoe UI", 11)
F_NAVB  = ("Segoe UI", 11, "bold")
F_TITLE = ("Segoe UI", 18, "bold")
F_DESC  = ("Segoe UI", 10)
F_SEC   = ("Segoe UI", 9, "bold")
F_LABEL = ("Segoe UI", 9)
F_UI    = ("Segoe UI", 10)
F_BTN   = ("Segoe UI", 10, "bold")
F_LOG   = ("Consolas", 9)
F_SMALL = ("Segoe UI", 9)

_DXF_TOOLS  = [
    ("strings", "Generar Ruta DC"),
    ("met_mom", "Metrado DC"),
    ("ground",  "Diagrama de tierras"),
]
_DXF_LABELS = [v for _, v in _DXF_TOOLS]
_DXF_KEY    = {v: k for k, v in _DXF_TOOLS}
_DXF_DESC   = {
    "strings": "Dibuja conductores DC (LWPOLYLINE), etiquetas IxSy y marquillas MULTILEADER en el DXF.",
    "met_mom": "Calcula longitud de conductores DC y exporta Excel + CSV de metrado.",
    "ground":  "Inserta Ground Clamps, tubo interflex y etiquetas de tierra entre mesas de paneles.",
}
_PROMPT_TPLS = {
    "Generar Ruta DC": (
        "Genera ruta DC para el archivo DXF adjunto.\n"
        "N inversores: 3 | Strings / inv: 26 | String inicial: 1\n"
        "Bajante: derecha | Bloque de panel: PANEL_615"
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


# ── TTK styles ────────────────────────────────────────────────────────────────
def _apply_styles():
    s = ttk.Style()
    s.theme_use("clam")
    s.configure("V.Vertical.TScrollbar",
                gripcount=0, background=INP_BD, troughcolor=BG,
                bordercolor=BG, arrowcolor=MUTED, arrowsize=10)
    s.map("V.Vertical.TScrollbar", background=[("active", MUTED)])
    s.configure("Amber.Horizontal.TProgressbar",
                troughcolor=SURF, background=ACCENT,
                darkcolor=ACCENT, lightcolor=ACCENT, borderwidth=0)
    s.configure("TCombobox", fieldbackground=BG, background=INP_BD,
                foreground=TEXT, arrowcolor=MUTED, relief="flat",
                borderwidth=1, lightcolor=INP_BD, darkcolor=INP_BD)
    s.map("TCombobox",
          fieldbackground=[("readonly", BG)],
          bordercolor=[("focus", ACCENT), ("!focus", INP_BD)])


# ── Widgets helpers ────────────────────────────────────────────────────────────
def _section_title(parent, text):
    """Título de sección con línea divisoria (igual que la web)."""
    row = tk.Frame(parent, bg=BG)
    row.pack(fill="x", pady=(22, 10))
    tk.Label(row, text=text.upper(), bg=BG, fg=MUTED, font=F_SEC).pack(side="left")
    tk.Frame(row, bg=BORDER, height=1).pack(
        side="left", fill="x", expand=True, padx=(8, 0), pady=(0, 2))
    return row


def _field_label(parent, text):
    tk.Label(parent, text=text, bg=BG, fg=MUTED, font=F_LABEL).pack(
        anchor="w", pady=(0, 3))


def _entry_box(parent, var, width=None, focus_ring=True):
    """Entry con borde y ring de foco ámbar."""
    wrap = tk.Frame(parent, bg=BG, highlightbackground=INP_BD, highlightthickness=1)
    kw = dict(textvariable=var, bg=BG, fg=TEXT, relief="flat",
              font=F_UI, insertbackground=ACCENT, bd=6)
    if width:
        kw["width"] = width
    e = tk.Entry(wrap, **kw)
    e.pack(fill="x")
    if focus_ring:
        e.bind("<FocusIn>",  lambda _: wrap.config(highlightbackground=ACCENT))
        e.bind("<FocusOut>", lambda _: wrap.config(highlightbackground=INP_BD))
    return wrap, e


def _spinbox_box(parent, var, from_, to, width=6, inc=1):
    wrap = tk.Frame(parent, bg=BG, highlightbackground=INP_BD, highlightthickness=1)
    sb = tk.Spinbox(wrap, from_=from_, to=to, increment=inc, textvariable=var, width=width,
                    bg=BG, fg=TEXT, buttonbackground=SURF,
                    relief="flat", font=F_UI, bd=6, insertbackground=ACCENT)
    sb.pack(fill="x")
    sb.bind("<FocusIn>",  lambda _: wrap.config(highlightbackground=ACCENT))
    sb.bind("<FocusOut>", lambda _: wrap.config(highlightbackground=INP_BD))
    return wrap


def _file_row(parent, label, var, types=None, is_dir=False):
    """Label + input + botón en fila, todo con borde unificado (igual que la web)."""
    _field_label(parent, label)
    outer = tk.Frame(parent, bg=BG, highlightbackground=INP_BD, highlightthickness=1)
    outer.pack(fill="x", pady=(0, 10))

    e = tk.Entry(outer, textvariable=var, bg=BG, fg=TEXT, relief="flat",
                 font=F_SMALL, insertbackground=ACCENT, bd=6)
    e.pack(side="left", fill="x", expand=True)
    e.bind("<FocusIn>",  lambda _: outer.config(highlightbackground=ACCENT))
    e.bind("<FocusOut>", lambda _: outer.config(highlightbackground=INP_BD))

    # Divider vertical
    tk.Frame(outer, bg=BORDER, width=1).pack(side="left", fill="y")

    def _browse():
        if is_dir:
            p = filedialog.askdirectory(title="Seleccionar carpeta")
        else:
            p = filedialog.askopenfilename(
                title="Seleccionar archivo",
                filetypes=types or [("Todos", "*.*")])
        if p:
            var.set(p)
            outer.config(highlightbackground=INP_BD)

    txt = "📁 Carpeta" if is_dir else "📂 Abrir"
    btn = tk.Label(outer, text=txt, bg=SURF, fg=TEXT2, font=F_LABEL,
                   padx=12, pady=6, cursor="hand2")
    btn.pack(side="left")
    btn.bind("<Button-1>", lambda _: _browse())
    btn.bind("<Enter>", lambda _: btn.config(bg=HOVER, fg=TEXT))
    btn.bind("<Leave>", lambda _: btn.config(bg=SURF, fg=TEXT2))


def _checkbox(parent, var, text):
    return tk.Checkbutton(parent, variable=var, text=text,
                          bg=BG, fg=TEXT2, font=F_UI,
                          selectcolor=BG, activebackground=BG,
                          relief="flat", bd=0, highlightthickness=0,
                          activeforeground=TEXT, cursor="hand2")


def _run_btn(parent, text, command):
    f = tk.Frame(parent, bg=BG)
    f.pack(anchor="w", pady=(4, 0))
    btn = tk.Button(f, text=text, command=command,
                    bg=ACCENT, fg="#FFFFFF", font=F_BTN,
                    relief="flat", bd=0, padx=24, pady=10,
                    cursor="hand2", activebackground=ACC_H, activeforeground="#FFFFFF")
    btn.pack(side="left")
    pb = ttk.Progressbar(f, maximum=100, length=160, mode="indeterminate",
                         style="Amber.Horizontal.TProgressbar")
    return btn, pb, f


# ── Aplicación principal ───────────────────────────────────────────────────────
class AutoGDApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Auto-GD  v4.0  —  Herramientas FV")
        self.configure(bg=BG)
        self.geometry("980x820")
        self.minsize(780, 580)
        _apply_styles()

        # ── Variables RETIE ─────────────────────────────────────────────────
        self.v_nombre    = tk.StringVar(value="LA MARTINA 1")
        self.v_ciudad    = tk.StringVar(value="PARATEBUENO")
        self.v_depto     = tk.StringVar(value="CUNDINAMARCA")
        self.v_fecha     = tk.StringVar(value="2026-03-31")
        self.v_tmin      = tk.StringVar(value="18")
        self.v_tmax      = tk.StringVar(value="30")
        self.v_tprom     = tk.StringVar(value="28")
        self.v_paneles   = tk.StringVar(value="24")
        self.v_modulos   = tk.StringVar(value="1728")
        self.v_num_inv   = tk.IntVar(value=3)
        self.v_ac_inv    = []
        self.v_metrado   = tk.StringVar()
        self.v_excel_base= tk.StringVar()
        self.v_word_base = tk.StringVar()
        self.v_salida    = tk.StringVar(value=str(OUT_DIR))
        self.cb_fase1    = tk.BooleanVar(value=True)
        self.cb_fase2    = tk.BooleanVar(value=True)

        # ── Variables DXF ───────────────────────────────────────────────────
        self.v_dxf_tool      = tk.StringVar(value=_DXF_LABELS[0])
        self.v_dxf_in        = tk.StringVar()
        self.v_dxf_outdir    = tk.StringVar(value=str(MCP_DIR / "output"))
        self.v_dxf_n_inv     = tk.IntVar(value=3)
        self.v_dxf_str_inv   = tk.IntVar(value=26)
        self.v_dxf_start     = tk.IntVar(value=1)
        self.v_dxf_max_str   = tk.IntVar(value=28)
        self.v_dxf_bajante   = tk.StringVar(value="R")
        self.v_dxf_panel     = tk.StringVar(value="PANEL_615")
        self.v_dxf_baj_down  = tk.DoubleVar(value=3.0)

        # ── Variables Prompts ───────────────────────────────────────────────
        self.cb_incl_prompt = tk.BooleanVar(value=False)

        self._active_view = None
        self._nav_btns    = {}

        self._build()
        self.v_nombre.trace_add("write",
            lambda *_: self._lbl_proyecto.config(text=self.v_nombre.get() or "—"))

    # ── Layout principal ───────────────────────────────────────────────────────
    def _build(self):
        # Sidebar | separador | main
        self._sidebar = tk.Frame(self, bg=SB_BG, width=230)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)
        tk.Frame(self, bg=SB_BD, width=1).pack(side="left", fill="y")

        self._main = tk.Frame(self, bg=BG)
        self._main.pack(side="left", fill="both", expand=True)

        self._build_sidebar()
        self._build_content()
        self._build_output()
        self._show_view("retie")

    # ── Sidebar ───────────────────────────────────────────────────────────────
    def _build_sidebar(self):
        sb = self._sidebar

        # Brand
        brand = tk.Frame(sb, bg=SB_BG, padx=16, pady=18)
        brand.pack(fill="x")
        tk.Frame(sb, bg=SB_BD, height=1).pack(fill="x")

        row = tk.Frame(brand, bg=SB_BG)
        row.pack(anchor="w")
        icon_f = tk.Frame(row, bg=ACCENT, width=34, height=34)
        icon_f.pack(side="left")
        icon_f.pack_propagate(False)
        tk.Label(icon_f, text="☀", bg=ACCENT, fg="#FFFFFF",
                 font=("Segoe UI", 15)).pack(expand=True)
        txt_f = tk.Frame(row, bg=SB_BG, padx=10)
        txt_f.pack(side="left")
        tk.Label(txt_f, text="Auto-GD", bg=SB_BG, fg=TEXT,
                 font=F_BRAND).pack(anchor="w")
        tk.Label(txt_f, text="v4.0 · Herramientas FV", bg=SB_BG, fg=MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w")

        # Nav
        nav = tk.Frame(sb, bg=SB_BG, pady=8)
        nav.pack(fill="x")
        tk.Label(nav, text="HERRAMIENTAS", bg=SB_BG, fg=LIGHT,
                 font=("Segoe UI", 8, "bold"), padx=16).pack(
            anchor="w", pady=(8, 4))

        for vid, icon, label in [
            ("retie",   "☀", "Memoria RETIE"),
            ("dxf",     "⚡", "Herramientas DXF"),
            ("prompts", "📝", "Prompts / Notas"),
        ]:
            self._nav_btns[vid] = self._make_nav_btn(nav, icon, label, vid)

        # Footer
        tk.Frame(sb, bg=SB_BD, height=1).pack(fill="x", side="bottom")
        foot = tk.Frame(sb, bg=SB_BG, padx=16, pady=12)
        foot.pack(fill="x", side="bottom")
        tk.Label(foot, text="Proyecto activo", bg=SB_BG, fg=LIGHT,
                 font=("Segoe UI", 9)).pack(anchor="w")
        self._lbl_proyecto = tk.Label(foot,
                                      text=self.v_nombre.get() or "—",
                                      bg=SB_BG, fg=TEXT2,
                                      font=("Segoe UI", 9, "bold"))
        self._lbl_proyecto.pack(anchor="w")

    def _make_nav_btn(self, parent, icon, label, vid):
        wrap = tk.Frame(parent, bg=SB_BG, padx=8)
        wrap.pack(fill="x", pady=1)
        inner = tk.Frame(wrap, bg=SB_BG, padx=10, pady=8, cursor="hand2")
        inner.pack(fill="x")
        ico_l = tk.Label(inner, text=icon, bg=SB_BG, fg=TEXT2,
                         font=("Segoe UI", 13), width=2)
        ico_l.pack(side="left")
        txt_l = tk.Label(inner, text=label, bg=SB_BG, fg=TEXT2,
                         font=F_NAV, anchor="w")
        txt_l.pack(side="left", fill="x", expand=True)

        widgets = (inner, ico_l, txt_l)

        def _click(_=None):
            self._show_view(vid)

        def _enter(_):
            if self._active_view != vid:
                for w in widgets:
                    w.config(bg=HOVER)

        def _leave(_):
            if self._active_view != vid:
                for w in widgets:
                    w.config(bg=SB_BG)

        for w in widgets:
            w.bind("<Button-1>", _click)
            w.bind("<Enter>",   _enter)
            w.bind("<Leave>",   _leave)

        return {"widgets": widgets, "txt": txt_l}

    def _show_view(self, vid):
        # Desactivar anterior
        if self._active_view:
            old = self._nav_btns.get(self._active_view)
            if old:
                for w in old["widgets"]:
                    w.config(bg=SB_BG)
                old["txt"].config(fg=TEXT2, font=F_NAV)
            old_frame = getattr(self, f"_vf_{self._active_view}", None)
            if old_frame:
                old_frame.pack_forget()

        # Activar nuevo
        self._active_view = vid
        new = self._nav_btns.get(vid)
        if new:
            for w in new["widgets"]:
                w.config(bg=ACTIVE_C)
            new["txt"].config(fg=TEXT, font=F_NAVB)
        new_frame = getattr(self, f"_vf_{vid}", None)
        if new_frame:
            new_frame.pack(fill="both", expand=True)

        self._canvas.update_idletasks()
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        self._canvas.yview_moveto(0)

    # ── Área de contenido scrollable ──────────────────────────────────────────
    def _build_content(self):
        wrap = tk.Frame(self._main, bg=BG)
        wrap.pack(fill="both", expand=True)

        self._canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(wrap, orient="vertical",
                            command=self._canvas.yview,
                            style="V.Vertical.TScrollbar")
        self._canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._inner = tk.Frame(self._canvas, bg=BG)
        self._cwin  = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")

        self._inner.bind("<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>",
            lambda e: self._canvas.itemconfig(self._cwin, width=e.width))
        self._canvas.bind_all("<MouseWheel>",
            lambda e: self._canvas.yview_scroll(-1*(e.delta//120), "units"))

        # Construir vistas (ocultas hasta _show_view)
        self._vf_retie   = self._view_retie(self._inner)
        self._vf_dxf     = self._view_dxf(self._inner)
        self._vf_prompts = self._view_prompts(self._inner)

    # ── Panel de output ───────────────────────────────────────────────────────
    def _build_output(self):
        tk.Frame(self._main, bg=BORDER, height=1).pack(fill="x")

        self._out_wrap = tk.Frame(self._main, bg=BG)
        self._out_wrap.pack(fill="x")
        self._out_wrap.pack_forget()   # oculto hasta primera ejecución

        # Header
        hdr = tk.Frame(self._out_wrap, bg=SURF, padx=14, pady=9)
        hdr.pack(fill="x")
        tk.Frame(self._out_wrap, bg=BORDER, height=1).pack(fill="x")

        left = tk.Frame(hdr, bg=SURF)
        left.pack(side="left")
        self._dot = tk.Frame(left, bg=LIGHT, width=8, height=8)
        self._dot.pack(side="left", padx=(0, 10))
        self._dot.pack_propagate(False)
        tk.Label(left, text="Resultado", bg=SURF, fg=TEXT2,
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        self._out_status = tk.Label(left, text="", bg=SURF, fg=MUTED, font=F_LABEL)
        self._out_status.pack(side="left", padx=(12, 0))

        clr = tk.Label(hdr, text="✕", bg=SURF, fg=LIGHT,
                       font=("Segoe UI", 12), cursor="hand2", padx=4)
        clr.pack(side="right")
        clr.bind("<Button-1>", lambda _: self._clear_log())
        clr.bind("<Enter>", lambda _: clr.config(fg=TEXT2))
        clr.bind("<Leave>", lambda _: clr.config(fg=LIGHT))

        # Log body
        body = tk.Frame(self._out_wrap, bg=BG)
        body.pack(fill="both", expand=True)
        self.log = tk.Text(body, height=11, bg=BG, fg=TEXT2,
                           font=F_LOG, relief="flat", wrap="word",
                           state="disabled", padx=14, pady=8,
                           insertbackground=TEXT, selectbackground=ACCENT)
        vsb2 = ttk.Scrollbar(body, orient="vertical",
                             command=self.log.yview,
                             style="V.Vertical.TScrollbar")
        self.log.configure(yscrollcommand=vsb2.set)
        vsb2.pack(side="right", fill="y")
        self.log.pack(fill="both", expand=True)
        self.log.tag_configure("ok",      foreground=GREEN)
        self.log.tag_configure("err",     foreground=RED,   font=("Consolas", 9, "bold"))
        self.log.tag_configure("accent",  foreground=ACCENT, font=("Consolas", 9, "bold"))
        self.log.tag_configure("muted",   foreground=LIGHT)
        self.log.tag_configure("warning", foreground=WARN)

    # ── Vistas ────────────────────────────────────────────────────────────────
    def _view_retie(self, parent):
        f = tk.Frame(parent, bg=BG, padx=40, pady=32)

        tk.Label(f, text="Memoria RETIE", bg=BG, fg=TEXT, font=F_TITLE).pack(anchor="w")
        tk.Label(f, text="Genera el Excel de cálculo y la memoria Word para el expediente técnico.",
                 bg=BG, fg=MUTED, font=F_DESC).pack(anchor="w", pady=(4, 0))

        # ── Datos del proyecto
        _section_title(f, "Datos del proyecto")
        g = tk.Frame(f, bg=BG)
        g.pack(fill="x")
        g.columnconfigure((0, 1, 2), weight=1, uniform="col")

        def _gfield(label, var, r, c, span=1):
            w = tk.Frame(g, bg=BG)
            w.grid(row=r, column=c, columnspan=span, sticky="ew",
                   pady=5, padx=(0, 14) if c < span else (0, 0))
            _field_label(w, label)
            _entry_box(w, var)[0].pack(fill="x")

        _gfield("Nombre del proyecto", self.v_nombre, 0, 0, 2)
        _gfield("Fecha (YYYY-MM-DD)",  self.v_fecha,  0, 2)
        _gfield("Ciudad",        self.v_ciudad, 1, 0)
        _gfield("Departamento",  self.v_depto,  1, 1)

        # Temperaturas
        tw = tk.Frame(g, bg=BG)
        tw.grid(row=1, column=2, sticky="ew", pady=5)
        _field_label(tw, "Temp. mín / máx / prom (°C)")
        trow = tk.Frame(tw, bg=BG)
        trow.pack(anchor="w")
        for v in (self.v_tmin, self.v_tmax, self.v_tprom):
            b, _ = _entry_box(trow, v, width=5)
            b.pack(side="left", padx=(0, 6))

        _gfield("Paneles en serie", self.v_paneles, 2, 0)
        _gfield("Total de módulos", self.v_modulos, 2, 1)

        inv_w = tk.Frame(g, bg=BG)
        inv_w.grid(row=2, column=2, sticky="ew", pady=5)
        _field_label(inv_w, "N° de inversores")
        _spinbox_box(inv_w, self.v_num_inv, 1, 10).pack(anchor="w")
        self.v_num_inv.trace_add("write", lambda *_: self._rebuild_ac())

        # ── Archivos de entrada
        _section_title(f, "Archivos de entrada")
        _file_row(f, "Metrado de cables (.xlsx)",
                  self.v_metrado, [("Excel", "*.xlsx *.xls")])
        _file_row(f, "Plantilla de cálculo (.xlsm)",
                  self.v_excel_base, [("Excel macro", "*.xlsm")])
        _file_row(f, "Memoria base (.docx)",
                  self.v_word_base, [("Word", "*.docx")])
        _file_row(f, "Carpeta de salida", self.v_salida, is_dir=True)

        # ── Cable AC
        _section_title(f, "Longitud cable AC por inversor (m)")
        self._ac_frame = tk.Frame(f, bg=BG)
        self._ac_frame.pack(fill="x", pady=(0, 4))
        self._rebuild_ac()

        # ── Procesos
        _section_title(f, "Procesos a ejecutar")
        cb_row = tk.Frame(f, bg=BG)
        cb_row.pack(fill="x", pady=(0, 14))
        _checkbox(cb_row, self.cb_fase1,
                  "  Fase 1 — Llenar Excel de cálculo").pack(side="left", padx=(0, 24))
        _checkbox(cb_row, self.cb_fase2,
                  "  Fase 2+3 — Capturar tablas → Word").pack(side="left")

        self.btn_retie, self.pb_retie, _ = _run_btn(f, "▶  Ejecutar pipeline",
                                                     self._run_retie)
        return f

    def _view_dxf(self, parent):
        f = tk.Frame(parent, bg=BG, padx=40, pady=32)

        tk.Label(f, text="Herramientas DXF", bg=BG, fg=TEXT, font=F_TITLE).pack(anchor="w")
        tk.Label(f, text="Genera ruta DC con conductores y marquillas, o calcula metrado de cables.",
                 bg=BG, fg=MUTED, font=F_DESC).pack(anchor="w", pady=(4, 0))

        # ── Herramienta
        _section_title(f, "Herramienta")
        tool_row = tk.Frame(f, bg=BG)
        tool_row.pack(fill="x", pady=(0, 4))

        tool_cb = ttk.Combobox(tool_row, textvariable=self.v_dxf_tool,
                               values=_DXF_LABELS, state="readonly",
                               width=22, font=F_UI)
        tool_cb.pack(side="left")

        # Borde manual alrededor del combobox (Tkinter no lo estila bien)
        self._dxf_desc_lbl = tk.Label(tool_row, text=_DXF_DESC["strings"],
                                      bg=SURF, fg=MUTED, font=F_SMALL,
                                      wraplength=380, justify="left",
                                      padx=12, pady=8,
                                      highlightbackground=BORDER,
                                      highlightthickness=1)
        self._dxf_desc_lbl.pack(side="left", padx=(14, 0), fill="x", expand=True)

        # ── Archivos
        _section_title(f, "Archivos")
        _file_row(f, "DXF de entrada (.dxf)",
                  self.v_dxf_in, [("DXF", "*.dxf")])
        _file_row(f, "Carpeta de salida", self.v_dxf_outdir, is_dir=True)

        # ── Parámetros dinámicos
        self._dxf_params = tk.Frame(f, bg=BG)
        self._dxf_params.pack(fill="x")
        self._build_dxf_params()

        # ── Ejecutar
        _section_title(f, "Ejecutar")
        self.btn_dxf, self.pb_dxf, _ = _run_btn(f, "▶  Ejecutar herramienta",
                                                  self._run_dxf)
        self.v_dxf_tool.trace_add("write", self._on_tool_change)
        return f

    def _build_dxf_params(self):
        frame = self._dxf_params

        # Params Strings DC
        self._pf_strings = tk.Frame(frame, bg=BG)
        _section_title(self._pf_strings, "Parámetros — Generar Ruta DC")
        pg = tk.Frame(self._pf_strings, bg=BG)
        pg.pack(fill="x")
        pg.columnconfigure((0, 1, 2, 3), weight=1, uniform="col")

        for (lbl, var, fr, to), c in zip([
            ("N° inversores",   self.v_dxf_n_inv,   1, 20),
            ("Strings / inv.",  self.v_dxf_str_inv, 1, 60),
            ("String inicial",  self.v_dxf_start,   1, 99),
        ], range(3)):
            w = tk.Frame(pg, bg=BG)
            w.grid(row=0, column=c, sticky="ew", pady=4, padx=(0, 14))
            _field_label(w, lbl)
            _spinbox_box(w, var, fr, to).pack(fill="x")

        baj_w = tk.Frame(pg, bg=BG)
        baj_w.grid(row=0, column=3, sticky="ew", pady=4)
        _field_label(baj_w, "Bajante (R/L)")
        _entry_box(baj_w, self.v_dxf_bajante, width=4)[0].pack(anchor="w")

        pnl_w = tk.Frame(self._pf_strings, bg=BG)
        pnl_w.pack(fill="x")
        _field_label(pnl_w, "Nombre del bloque de panel")
        _entry_box(pnl_w, self.v_dxf_panel, width=20)[0].pack(anchor="w")

        # Params Diagrama de Tierras
        self._pf_ground = tk.Frame(frame, bg=BG)
        _section_title(self._pf_ground, "Parámetros — Diagrama de tierras")
        gg = tk.Frame(self._pf_ground, bg=BG)
        gg.pack(fill="x")
        gg.columnconfigure((0, 1, 2), weight=1, uniform="gcol")

        baj_gw = tk.Frame(gg, bg=BG)
        baj_gw.grid(row=0, column=0, sticky="ew", pady=4, padx=(0, 14))
        _field_label(baj_gw, "Bajante (R/L)")
        _entry_box(baj_gw, self.v_dxf_bajante, width=4)[0].pack(anchor="w")

        down_w = tk.Frame(gg, bg=BG)
        down_w.grid(row=0, column=1, sticky="ew", pady=4, padx=(0, 14))
        _field_label(down_w, "Long. bajante (m)")
        _spinbox_box(down_w, self.v_dxf_baj_down, 0.5, 20.0, inc=0.5).pack(fill="x")

        pnl_gw = tk.Frame(gg, bg=BG)
        pnl_gw.grid(row=0, column=2, sticky="ew", pady=4)
        _field_label(pnl_gw, "Bloque panel")
        _entry_box(pnl_gw, self.v_dxf_panel, width=16)[0].pack(anchor="w")

        self._on_tool_change()

    def _on_tool_change(self, *_):
        tool = _DXF_KEY.get(self.v_dxf_tool.get(), "strings")
        self._dxf_desc_lbl.config(text=_DXF_DESC.get(tool, ""))
        self._pf_strings.pack_forget()
        self._pf_ground.pack_forget()
        if tool == "strings":
            self._pf_strings.pack(fill="x")
        elif tool == "ground":
            self._pf_ground.pack(fill="x")

    def _view_prompts(self, parent):
        f = tk.Frame(parent, bg=BG, padx=40, pady=32)

        tk.Label(f, text="Prompts / Notas", bg=BG, fg=TEXT, font=F_TITLE).pack(anchor="w")
        tk.Label(f, text="Prepara instrucciones para Claude Code o guarda parámetros del proyecto.",
                 bg=BG, fg=MUTED, font=F_DESC).pack(anchor="w", pady=(4, 0))

        _section_title(f, "Editor")

        tpl_row = tk.Frame(f, bg=BG)
        tpl_row.pack(fill="x", pady=(0, 10))
        tk.Label(tpl_row, text="Plantilla:", bg=BG, fg=MUTED, font=F_LABEL).pack(
            side="left", padx=(0, 10))
        self._tpl_var = tk.StringVar(value="Seleccionar…")
        tpl_cb = ttk.Combobox(tpl_row, textvariable=self._tpl_var,
                              values=list(_PROMPT_TPLS.keys()),
                              state="readonly", width=28, font=F_SMALL)
        tpl_cb.pack(side="left")

        def _load(*_):
            k = self._tpl_var.get()
            if k in _PROMPT_TPLS:
                self._prompt_ta.delete("1.0", "end")
                self._prompt_ta.insert("1.0", _PROMPT_TPLS[k])

        tpl_cb.bind("<<ComboboxSelected>>", _load)

        ta_wrap = tk.Frame(f, bg=BG, highlightbackground=INP_BD, highlightthickness=1)
        ta_wrap.pack(fill="both", expand=True, pady=(0, 10))
        self._prompt_ta = tk.Text(ta_wrap, height=14, bg=BG, fg=TEXT,
                                  font=F_UI, relief="flat", wrap="word",
                                  insertbackground=ACCENT,
                                  selectbackground=ACCENT,
                                  selectforeground="#FFFFFF",
                                  padx=12, pady=10)
        self._prompt_ta.bind("<FocusIn>",
            lambda _: ta_wrap.config(highlightbackground=ACCENT))
        self._prompt_ta.bind("<FocusOut>",
            lambda _: ta_wrap.config(highlightbackground=INP_BD))
        vsb = ttk.Scrollbar(ta_wrap, command=self._prompt_ta.yview,
                           style="V.Vertical.TScrollbar")
        self._prompt_ta.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._prompt_ta.pack(fill="both", expand=True)

        btn_row = tk.Frame(f, bg=BG)
        btn_row.pack(fill="x")
        _checkbox(btn_row, self.cb_incl_prompt,
                  "  Incluir en el log al ejecutar").pack(side="left")

        def _copy():
            txt = self._prompt_ta.get("1.0", "end").strip()
            self.clipboard_clear()
            self.clipboard_append(txt)
            copy_btn.config(text="✓ Copiado")
            self.after(1800, lambda: copy_btn.config(text="Copiar al portapapeles"))

        copy_btn = tk.Button(btn_row, text="Copiar al portapapeles",
                             command=_copy, bg=SURF, fg=TEXT2,
                             font=F_SMALL, relief="flat", bd=0,
                             padx=14, pady=7, cursor="hand2",
                             highlightbackground=BORDER, highlightthickness=1,
                             activebackground=HOVER, activeforeground=TEXT)
        copy_btn.pack(side="right")

        _section_title(f, "Cómo usar")
        for n, tip in enumerate([
            "Escribe o carga una plantilla con la configuración del proceso que necesitas.",
            "Copia el texto y pégalo en Claude Code para que interprete los parámetros.",
            "Activa 'Incluir en log' para que quede registrado en cada ejecución local.",
            "Puedes usar este espacio como bitácora de parámetros del proyecto activo.",
        ], 1):
            row = tk.Frame(f, bg=BG, pady=4)
            row.pack(fill="x")
            tk.Label(row, text=str(n), bg=BG, fg=LIGHT,
                     font=("Segoe UI", 9, "bold"), width=3, anchor="nw").pack(side="left")
            tk.Label(row, text=tip, bg=BG, fg=TEXT2,
                     font=F_SMALL, anchor="w", justify="left").pack(
                side="left", fill="x", expand=True)
            tk.Frame(f, bg=BORDER, height=1).pack(fill="x")

        return f

    # ── AC Inversor rebuild ───────────────────────────────────────────────────
    def _rebuild_ac(self):
        for w in self._ac_frame.winfo_children():
            w.destroy()
        n = self.v_num_inv.get()
        while len(self.v_ac_inv) < n:
            self.v_ac_inv.append(tk.StringVar(value="0"))
        self.v_ac_inv = self.v_ac_inv[:n]
        for i in range(n):
            col = tk.Frame(self._ac_frame, bg=BG)
            col.pack(side="left", padx=(0, 14))
            _field_label(col, f"Inversor {i+1}")
            _entry_box(col, self.v_ac_inv[i], width=7)[0].pack()

    # ── Log helpers ───────────────────────────────────────────────────────────
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
        self._out_wrap.pack_forget()

    def _log_prompt(self):
        if self.cb_incl_prompt.get():
            txt = self._prompt_ta.get("1.0", "end").strip()
            if txt:
                self._log("NOTAS:", "accent")
                for line in txt.splitlines():
                    self._log("  " + line, "muted")
                self._log("")

    def _show_output(self, running=True):
        self._out_wrap.pack(fill="x")
        color = ACCENT if running else GREEN
        self._dot.config(bg=color)
        self._out_status.config(text="Ejecutando…" if running else "")

    def _btn_lock(self, btn, pb, label="  Ejecutando…"):
        btn.config(state="disabled", text=label,
                   bg=BORDER, fg=MUTED, cursor="arrow")
        pb.pack(side="left", padx=(12, 0))
        pb.start(10)

    def _btn_unlock(self, btn, pb, orig_text):
        pb.stop()
        pb.pack_forget()
        btn.config(state="normal", text=orig_text,
                   bg=ACCENT, fg="#FFFFFF", cursor="hand2")

    # ── Validación RETIE ──────────────────────────────────────────────────────
    def _validar_retie(self):
        err = []
        if not self.v_nombre.get().strip():
            err.append("Falta el nombre del proyecto.")
        try:
            datetime.strptime(self.v_fecha.get().strip(), "%Y-%m-%d")
        except ValueError:
            err.append("Fecha inválida (usa YYYY-MM-DD).")
        for lbl, var in [("Temp. mínima", self.v_tmin),
                         ("Temp. máxima", self.v_tmax),
                         ("Temp. promedio", self.v_tprom)]:
            try:
                float(var.get())
            except ValueError:
                err.append(f"{lbl} no es un número válido.")
        for i, v in enumerate(self.v_ac_inv):
            try:
                float(v.get())
            except ValueError:
                err.append(f"Longitud AC inversor {i+1} no es válida.")
        for nombre, var in [("Metrado Excel", self.v_metrado),
                            ("Plantilla Excel", self.v_excel_base),
                            ("Memoria Word base", self.v_word_base)]:
            val = var.get().strip()
            if val and not Path(val).exists():
                err.append(f"Archivo no encontrado: {nombre}")
        return err

    # ── Run RETIE ─────────────────────────────────────────────────────────────
    def _run_retie(self):
        if not self.cb_fase1.get() and not self.cb_fase2.get():
            from tkinter import messagebox
            messagebox.showwarning("Sin proceso",
                                   "Selecciona al menos una fase.")
            return
        errs = self._validar_retie()
        if errs:
            from tkinter import messagebox
            messagebox.showerror("Campos inválidos", "\n".join(errs))
            return
        self._btn_lock(self.btn_retie, self.pb_retie)
        self._clear_log()
        self._show_output(running=True)
        self._log_prompt()
        threading.Thread(target=self._pipeline_retie, daemon=True).start()

    def _pipeline_retie(self):
        try:
            from auto_gd import leer_metrado, llenar_excel
            from capturar_tablas import ejecutar as cap_exec, TABLA_MAP

            fecha   = datetime.strptime(self.v_fecha.get().strip(), "%Y-%m-%d")
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
                self._log("FASE 1 — Llenando Excel de cálculo", "accent")
                metrado = leer_metrado(self.v_metrado.get())
                self._log(f"  Metrado cargado: {len(metrado)} strings", "muted")
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    llenar_excel(metrado, proyecto, self.v_excel_base.get(), excel_out)
                self._dump_buf(buf)

            if self.cb_fase2.get():
                self._log("FASE 2+3 — Captura de tablas → Word", "accent")
                buf2 = io.StringIO()
                with contextlib.redirect_stdout(buf2):
                    cap_exec(excel_out, self.v_word_base.get(), word_out, TABLA_MAP,
                             paneles_serie=proyecto["paneles_serie"],
                             proyecto_info=proyecto)
                self._dump_buf(buf2)

            self._log("✓  PROCESO COMPLETADO", "ok")
            if self.cb_fase1.get():
                self._log(f"   Excel  →  {excel_out}", "muted")
            if self.cb_fase2.get():
                self._log(f"   Word   →  {word_out}", "muted")
            self.after(0, lambda: self._dot.config(bg=GREEN))
            self.after(0, lambda: self._out_status.config(text="Completado"))

        except Exception:
            self._log("[ERROR CRÍTICO]", "err")
            self._log(traceback.format_exc(), "err")
            self.after(0, lambda: self._dot.config(bg=RED))
            self.after(0, lambda: self._out_status.config(text="Error"))
        finally:
            self.after(0, lambda: self._btn_unlock(
                self.btn_retie, self.pb_retie, "▶  Ejecutar pipeline"))

    # ── Run DXF ───────────────────────────────────────────────────────────────
    def _run_dxf(self):
        dxf_in = self.v_dxf_in.get().strip()
        if not dxf_in or not Path(dxf_in).exists():
            from tkinter import messagebox
            messagebox.showerror("Archivo inválido",
                                 "Selecciona un archivo DXF de entrada válido.")
            return
        self._btn_lock(self.btn_dxf, self.pb_dxf)
        self._clear_log()
        self._show_output(running=True)
        self._log_prompt()
        tool    = _DXF_KEY.get(self.v_dxf_tool.get(), "strings")
        out_dir = self.v_dxf_outdir.get().strip() or str(MCP_DIR / "output")
        threading.Thread(target=self._pipeline_dxf,
                         args=(tool, dxf_in, out_dir), daemon=True).start()

    def _pipeline_dxf(self, tool, dxf_in, out_dir):
        try:
            Path(out_dir).mkdir(parents=True, exist_ok=True)
            dxf_stem = Path(dxf_in).stem

            if tool == "strings":
                self._log("GENERAR RUTA DC — Conductores + IxSy + MULTILEADER", "accent")
                import generate_strings_dxf as _gsd
                importlib.reload(_gsd)
                run_generate_strings = _gsd.run_generate_strings
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
                self._log(f"✓  →  {output}", "ok")

            elif tool == "met_mom":
                self._log("METRADO DC", "accent")
                import metrado_strings_dxf as mod
                importlib.reload(mod)
                mod.SOURCE      = dxf_in
                mod.OUTPUT_XLSX = str(Path(out_dir) / f"metrado_{dxf_stem}.xlsx")
                mod.OUTPUT_CSV  = str(Path(out_dir) / f"metrado_{dxf_stem}.csv")
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    mod.main()
                self._dump_buf(buf)
                self._log(f"✓  →  {mod.OUTPUT_XLSX}", "ok")

            elif tool == "met_iso":
                self._log("METRADO DC — ISIDORI", "accent")
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
                self._log(f"✓  →  {mod.OUTPUT_XLSX}", "ok")

            elif tool == "ground":
                self._log("DIAGRAMA DE TIERRAS — Ground Clamps + interflex + etiquetas", "accent")
                from generate_ground_dxf import run_generate_ground
                output = str(Path(out_dir) / f"{dxf_stem}_tierra.dxf")
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    run_generate_ground(
                        source_dxf   = dxf_in,
                        output_dxf   = output,
                        bajante_side = self.v_dxf_bajante.get().strip().upper() or "R",
                        panel_block  = self.v_dxf_panel.get().strip() or "PANEL_615",
                        bajante_down = self.v_dxf_baj_down.get(),
                    )
                self._dump_buf(buf)
                self._log(f"✓  →  {output}", "ok")

            elif tool == "mleader":
                self._log("FIX MULTILEADER — corrigiendo contenido", "accent")
                import fix_mleader_content as mod
                importlib.reload(mod)
                mod.SOURCE = dxf_in
                mod.OUTPUT = str(Path(out_dir) / f"{dxf_stem}_fixed.dxf")
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    mod.main()
                self._dump_buf(buf)
                self._log(f"✓  →  {mod.OUTPUT}", "ok")

            self.after(0, lambda: self._dot.config(bg=GREEN))
            self.after(0, lambda: self._out_status.config(text="Completado"))

        except Exception:
            self._log("[ERROR CRÍTICO]", "err")
            self._log(traceback.format_exc(), "err")
            self.after(0, lambda: self._dot.config(bg=RED))
            self.after(0, lambda: self._out_status.config(text="Error"))
        finally:
            self.after(0, lambda: self._btn_unlock(
                self.btn_dxf, self.pb_dxf, "▶  Ejecutar herramienta"))

    def _dump_buf(self, buf):
        for line in buf.getvalue().splitlines():
            if "ERROR" in line:  tag = "err"
            elif "WARN" in line: tag = "warning"
            elif "OK" in line:   tag = "ok"
            else:                tag = "muted"
            self._log("  " + line, tag)


# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = AutoGDApp()
    app.mainloop()
