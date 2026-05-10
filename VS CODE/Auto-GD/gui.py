"""
Auto-GD — Interfaz gráfica
"""
import sys, threading, tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

# ──────────────────────────────────────────────────────────────────
#  PALETA  —  tonos cálidos / Claude-inspired
# ──────────────────────────────────────────────────────────────────
BG      = "#1c1917"
SURF    = "#292524"
SURF2   = "#3c3835"
BORDER  = "#57534e"
ACCENT  = "#d97706"
ACC_H   = "#f59e0b"
GREEN   = "#4ade80"
RED     = "#f87171"
WARN    = "#fbbf24"
TEXT    = "#fafaf9"
TEXT2   = "#d6d3d1"
MUTED   = "#78716c"
HEADER  = "#0c0a09"

F_TITLE = ("Segoe UI", 14, "bold")
F_SEC   = ("Segoe UI", 10, "bold")
F_UI    = ("Segoe UI", 10)
F_SMALL = ("Segoe UI", 9)
F_LABEL = ("Segoe UI", 8)
F_BTN   = ("Segoe UI", 10, "bold")
F_LOG   = ("Consolas", 9)


# ──────────────────────────────────────────────────────────────────
#  TTK STYLES
# ──────────────────────────────────────────────────────────────────
def _ttk_style():
    s = ttk.Style()
    s.theme_use("clam")
    s.configure("V.Vertical.TScrollbar",
                gripcount=0, background=SURF2, troughcolor=BG,
                bordercolor=BG, arrowcolor=MUTED, arrowsize=10)
    s.map("V.Vertical.TScrollbar", background=[("active", BORDER)])
    s.configure("Amber.Horizontal.TProgressbar",
                troughcolor=SURF2, background=ACCENT,
                darkcolor=ACCENT, lightcolor=ACC_H, borderwidth=0)


# ──────────────────────────────────────────────────────────────────
#  COMPONENTES
# ──────────────────────────────────────────────────────────────────
class _HoverBtn(tk.Button):
    def __init__(self, parent, bg0, bg1, fg0, fg1=None, **kw):
        super().__init__(parent, bg=bg0, fg=fg0, relief="flat", bd=0,
                         cursor="hand2",
                         activebackground=bg1, activeforeground=fg1 or fg0,
                         **kw)
        self._bg0, self._bg1 = bg0, bg1
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)

    def _enter(self, _):
        if str(self["state"]) != "disabled":
            self.config(bg=self._bg1)

    def _leave(self, _):
        self.config(bg=self._bg0)


def _entry(parent, var, width=22):
    f = tk.Frame(parent, bg=SURF2,
                 highlightbackground=BORDER, highlightthickness=1)
    e = tk.Entry(f, textvariable=var, width=width,
                 bg=SURF2, fg=TEXT, insertbackground=ACCENT,
                 relief="flat", font=F_UI, bd=8)
    e.pack(fill="x")
    e.bind("<FocusIn>",  lambda _: f.config(highlightbackground=ACCENT))
    e.bind("<FocusOut>", lambda _: f.config(highlightbackground=BORDER))
    return f, e


def _lbl(parent, text, muted=False, font=F_LABEL):
    return tk.Label(parent, text=text, bg=parent["bg"],
                    fg=MUTED if muted else TEXT2, font=font)


def _card(parent, title, color=ACCENT):
    outer = tk.Frame(parent, bg=SURF,
                     highlightbackground=BORDER, highlightthickness=1)
    tk.Frame(outer, bg=color, height=2).pack(fill="x")
    inner = tk.Frame(outer, bg=SURF, padx=16, pady=14)
    inner.pack(fill="both", expand=True)
    hdr = tk.Frame(inner, bg=SURF)
    hdr.pack(fill="x", pady=(0, 12))
    tk.Label(hdr, text=title, bg=SURF, fg=TEXT, font=F_SEC).pack(side="left")
    return inner


def _field(parent, label, var, width=22, row=None, col=None, span=1):
    wrap = tk.Frame(parent, bg=SURF)
    _lbl(wrap, label, muted=True).pack(anchor="w", pady=(0, 3))
    f, _ = _entry(wrap, var, width)
    f.pack(fill="x")
    if row is not None:
        wrap.grid(row=row, column=col, columnspan=span,
                  sticky="ew", padx=5, pady=5)
    return wrap


def _file_field(parent, label, var, types=None, is_dir=False, row=0):
    wrap = tk.Frame(parent, bg=SURF)
    _lbl(wrap, label, muted=True).pack(anchor="w", pady=(0, 3))

    row_f = tk.Frame(wrap, bg=SURF)
    row_f.pack(fill="x")

    box = tk.Frame(row_f, bg=SURF2,
                   highlightbackground=BORDER, highlightthickness=1)
    box.pack(side="left", fill="x", expand=True)
    e = tk.Entry(box, textvariable=var, bg=SURF2, fg=TEXT,
                 insertbackground=ACCENT, relief="flat", font=F_SMALL, bd=8)
    e.pack(fill="x")
    e.bind("<FocusIn>",  lambda _: box.config(highlightbackground=ACCENT))
    e.bind("<FocusOut>", lambda _: box.config(highlightbackground=BORDER))

    def _browse():
        p = filedialog.askdirectory() if is_dir else \
            filedialog.askopenfilename(filetypes=types or [("Todos", "*.*")])
        if p:
            var.set(p)

    _HoverBtn(row_f, SURF2, BORDER, MUTED, TEXT,
              text="…", font=("Segoe UI", 12),
              highlightbackground=BORDER, highlightthickness=1,
              padx=10, pady=3,
              command=_browse).pack(side="left", padx=(5, 0))

    wrap.grid(row=row, column=0, columnspan=3, sticky="ew", pady=5)
    return wrap


# ──────────────────────────────────────────────────────────────────
#  APLICACIÓN
# ──────────────────────────────────────────────────────────────────
class AutoGDApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Auto-GD")
        self.configure(bg=BG)
        self.geometry("800x900")
        self.resizable(True, True)
        self.minsize(680, 700)
        _ttk_style()

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

        self.v_metrado    = tk.StringVar(value=r"C:\Users\JesúsAndrésBustilloO\Documents\GD\Proyectos\MARTINA 1 Y 2\MARTINA_1\04. Editables\03. Tablas de Cálculo\Calculo de metros cable MARTINA 1 - copia.xlsx")
        self.v_excel_base = tk.StringVar(value=r"C:\Users\JesúsAndrésBustilloO\Documents\GD\Proyectos\MARTINA 1 Y 2\MARTINA_1\04. Editables\03. Tablas de Cálculo\PRGD-ENTRENAMIENTO CLAUDE.xlsm")
        self.v_word_base  = tk.StringVar(value=r"C:\Users\JesúsAndrésBustilloO\Documents\GD\Proyectos\MARTINA 1 Y 2\MARTINA_1\04. Editables\02. Memoria Retie\PRGD-MEMORIA ENEL.docx")
        self.v_salida     = tk.StringVar(value=str(BASE_DIR / "output"))

        self._build()

    # ── Layout ────────────────────────────────────────────────────
    def _build(self):
        self._make_header()
        self._make_body()

    def _make_header(self):
        hdr = tk.Frame(self, bg=HEADER, padx=24, pady=16)
        hdr.pack(fill="x")

        left = tk.Frame(hdr, bg=HEADER)
        left.pack(side="left")

        top = tk.Frame(left, bg=HEADER)
        top.pack(anchor="w")
        tk.Label(top, text="☀", bg=HEADER, fg=ACCENT,
                 font=("Segoe UI", 16)).pack(side="left", padx=(0, 8))
        tk.Label(top, text="Auto-GD", bg=HEADER, fg=TEXT,
                 font=F_TITLE).pack(side="left")
        tk.Label(top, text="  v2.0", bg=HEADER, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left", pady=(5, 0))

        tk.Label(left,
                 text="Generador automático de memorias de cálculo RETIE para sistemas FV",
                 bg=HEADER, fg=MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(5, 0))

        tk.Frame(self, bg=ACCENT, height=1).pack(fill="x")
        tk.Frame(self, bg=SURF,   height=2).pack(fill="x")

    def _make_body(self):
        wrap = tk.Frame(self, bg=BG)
        wrap.pack(fill="both", expand=True)

        canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical",
                           command=canvas.yview, style="V.Vertical.TScrollbar")
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self.body = tk.Frame(canvas, bg=BG, padx=24, pady=20)
        win = canvas.create_window((0, 0), window=self.body, anchor="nw")

        self.body.bind("<Configure>",
                       lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(win, width=e.width))
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))

        self._card_proyecto()
        self._card_archivos()
        self._card_ac()
        self._action_bar()
        self._card_log()

    # ── Tarjetas ──────────────────────────────────────────────────
    def _card_proyecto(self):
        card = _card(self.body, "Datos del proyecto", ACCENT)
        card.master.pack(fill="x", pady=(0, 12))

        g = tk.Frame(card, bg=SURF)
        g.pack(fill="x")
        g.columnconfigure((0, 1, 2), weight=1)

        _field(g, "Nombre del proyecto", self.v_nombre, row=0, col=0, span=2)
        _field(g, "Fecha  (YYYY-MM-DD)", self.v_fecha,  row=0, col=2)
        _field(g, "Ciudad",              self.v_ciudad, row=1, col=0)
        _field(g, "Departamento",        self.v_depto,  row=1, col=1)

        # Temperaturas
        t = tk.Frame(g, bg=SURF)
        t.grid(row=1, column=2, sticky="ew", padx=5, pady=5)
        _lbl(t, "Temperatura  mín / máx / prom  (°C)", muted=True).pack(anchor="w", pady=(0, 3))
        t_row = tk.Frame(t, bg=SURF)
        t_row.pack(anchor="w")
        for v in (self.v_tmin, self.v_tmax, self.v_tprom):
            f, _ = _entry(t_row, v, width=5)
            f.pack(side="left", padx=(0, 5))

        # Paneles / módulos / inversores
        _field(g, "Paneles en serie", self.v_paneles, width=8,  row=2, col=0)
        _field(g, "Total de módulos", self.v_modulos, width=10, row=2, col=1)

        inv = tk.Frame(g, bg=SURF)
        inv.grid(row=2, column=2, sticky="ew", padx=5, pady=5)
        _lbl(inv, "Número de inversores", muted=True).pack(anchor="w", pady=(0, 3))
        tk.Spinbox(inv, from_=1, to=10, width=5, textvariable=self.v_num_inv,
                   bg=SURF2, fg=TEXT, buttonbackground=SURF2, relief="flat",
                   font=F_UI, highlightbackground=BORDER, highlightthickness=1,
                   insertbackground=ACCENT,
                   command=self._rebuild_ac).pack(anchor="w")

    def _card_archivos(self):
        card = _card(self.body, "Archivos de entrada", WARN)
        card.master.pack(fill="x", pady=(0, 12))

        g = tk.Frame(card, bg=SURF)
        g.pack(fill="x")
        g.columnconfigure(0, weight=1)

        _file_field(g, "Metrado de cables  (.xlsx)",
                    self.v_metrado,    [("Excel",      "*.xlsx *.xls")], row=0)
        _file_field(g, "Plantilla de cálculo  (.xlsm)",
                    self.v_excel_base, [("Excel macro", "*.xlsm")],      row=1)
        _file_field(g, "Memoria base  (.docx)",
                    self.v_word_base,  [("Word",        "*.docx")],       row=2)
        _file_field(g, "Carpeta de salida",
                    self.v_salida, is_dir=True, row=3)

    def _card_ac(self):
        card = _card(self.body, "Longitud cable AC por inversor  (m)", GREEN)
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

    def _action_bar(self):
        bar = tk.Frame(self.body, bg=BG, pady=10)
        bar.pack(fill="x")

        self.btn = _HoverBtn(bar, ACCENT, ACC_H, HEADER,
                             text="▶  Ejecutar pipeline",
                             font=F_BTN, padx=28, pady=11,
                             command=self._run)
        self.btn.pack(side="left")

        _HoverBtn(bar, BG, SURF, MUTED, TEXT2,
                  text="Limpiar log", font=F_SMALL,
                  padx=14, pady=8,
                  highlightbackground=BORDER, highlightthickness=1,
                  command=self._clear_log).pack(side="left", padx=(10, 0))

        self.pb_var = tk.DoubleVar()
        self.pb = ttk.Progressbar(bar, variable=self.pb_var, maximum=100,
                                  length=180, mode="indeterminate",
                                  style="Amber.Horizontal.TProgressbar")

    def _card_log(self):
        card = _card(self.body, "Salida del proceso", MUTED)
        card.master.pack(fill="both", expand=True, pady=(0, 8))

        shell = tk.Frame(card, bg=HEADER,
                         highlightbackground=BORDER, highlightthickness=1)
        shell.pack(fill="both", expand=True)

        # barra estilo terminal macOS
        tbar = tk.Frame(shell, bg="#1a1714", pady=7, padx=10)
        tbar.pack(fill="x")
        for c in ("#f87171", "#fbbf24", "#4ade80"):
            tk.Frame(tbar, bg=c, width=11, height=11).pack(side="left", padx=(0, 5))
        tk.Label(tbar, text="pipeline output",
                 bg="#1a1714", fg=MUTED, font=F_LABEL).pack(side="left", padx=(10, 0))

        inner = tk.Frame(shell, bg=HEADER)
        inner.pack(fill="both", expand=True)

        self.log = tk.Text(inner, height=14, bg=HEADER, fg=TEXT2,
                           font=F_LOG, relief="flat", wrap="word",
                           state="disabled", insertbackground=TEXT,
                           selectbackground=SURF2, padx=12, pady=10)
        vsb = ttk.Scrollbar(inner, command=self.log.yview, style="V.Vertical.TScrollbar")
        self.log.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.log.pack(fill="both", expand=True)

        self.log.tag_configure("ok",      foreground=GREEN)
        self.log.tag_configure("err",     foreground=RED)
        self.log.tag_configure("accent",  foreground=ACCENT)
        self.log.tag_configure("muted",   foreground=MUTED)
        self.log.tag_configure("warning", foreground=WARN)

    # ── Lógica ────────────────────────────────────────────────────
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

    def _validar(self):
        err = []
        if not self.v_nombre.get().strip():
            err.append("Falta el nombre del proyecto.")
        try:
            datetime.strptime(self.v_fecha.get().strip(), "%Y-%m-%d")
        except ValueError:
            err.append("Fecha inválida — usa YYYY-MM-DD.")
        for lbl, var in [("Temp. mínima",   self.v_tmin),
                         ("Temp. máxima",   self.v_tmax),
                         ("Temp. promedio", self.v_tprom)]:
            try:
                float(var.get())
            except ValueError:
                err.append(f"{lbl} no es un número válido.")
        try:
            if int(self.v_paneles.get()) <= 0: raise ValueError
        except ValueError:
            err.append("Paneles en serie debe ser entero positivo.")
        try:
            if int(self.v_modulos.get()) <= 0: raise ValueError
        except ValueError:
            err.append("Total de módulos debe ser entero positivo.")
        for i, v in enumerate(self.v_ac_inv):
            try:
                float(v.get())
            except ValueError:
                err.append(f"Longitud AC inversor {i+1} no es válida.")
        for nombre, var in [("Metrado Excel",     self.v_metrado),
                            ("Plantilla Excel",   self.v_excel_base),
                            ("Memoria Word base", self.v_word_base)]:
            if not Path(var.get()).exists():
                err.append(f"Archivo no encontrado: {nombre}")
        return err

    def _run(self):
        errs = self._validar()
        if errs:
            messagebox.showerror("Campos inválidos", "\n".join(errs))
            return
        self.btn._bg0 = SURF2
        self.btn.configure(state="disabled", text="  Ejecutando…",
                           bg=SURF2, fg=MUTED, cursor="arrow")
        self.pb.pack(side="left", padx=(12, 0))
        self.pb.start(10)
        self._clear_log()
        threading.Thread(target=self._pipeline, daemon=True).start()

    def _pipeline(self):
        import traceback, io, contextlib
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

            self._log("━" * 54, "accent")
            self._log("  FASE 1  —  Llenando Excel de cálculo", "accent")
            self._log("━" * 54, "accent")

            metrado = leer_metrado(self.v_metrado.get())
            self._log(f"  Metrado cargado: {len(metrado)} strings", "muted")

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                llenar_excel(metrado, proyecto, self.v_excel_base.get(), excel_out)
            for line in buf.getvalue().splitlines():
                self._log("  " + line, "ok" if "✓" in line else "muted")

            self._log("\n" + "━" * 54, "accent")
            self._log("  FASE 2+3  —  Captura de tablas → Word", "accent")
            self._log("━" * 54, "accent")

            buf2 = io.StringIO()
            with contextlib.redirect_stdout(buf2):
                cap_exec(excel_out, self.v_word_base.get(), word_out, TABLA_MAP,
                         paneles_serie=proyecto["paneles_serie"],
                         proyecto_info=proyecto)
            for line in buf2.getvalue().splitlines():
                if   "[OK]" in line or "✓" in line:      tag = "ok"
                elif "[ERROR]" in line:                   tag = "err"
                elif "[ADVERTENCIA]" in line:             tag = "warning"
                elif "━" in line or "FASE" in line:       tag = "accent"
                else:                                     tag = "muted"
                self._log("  " + line, tag)

            self._log("\n  ✓  PROCESO COMPLETADO", "ok")
            self._log(f"     Excel  →  {excel_out}", "muted")
            self._log(f"     Word   →  {word_out}",  "muted")

        except Exception:
            self._log("\n[ERROR CRÍTICO]", "err")
            self._log(traceback.format_exc(), "err")

        finally:
            def _restore():
                self.pb.stop()
                self.pb.pack_forget()
                self.btn._bg0 = ACCENT
                self.btn.configure(state="normal",
                                   text="▶  Ejecutar pipeline",
                                   bg=ACCENT, fg=HEADER, cursor="hand2")
            self.after(0, _restore)


# ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = AutoGDApp()
    app.mainloop()
