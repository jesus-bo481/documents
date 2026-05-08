"""
Auto-GD — Interfaz gráfica
"""
import sys, os, threading, tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

# ─────────────────────────────────────────────────────────────────
# PALETA
# ─────────────────────────────────────────────────────────────────
BG       = "#0d1117"
SURF     = "#161b22"
SURF2    = "#21262d"
BORDER   = "#30363d"
ACCENT   = "#58a6ff"
GREEN    = "#3fb950"
RED      = "#f85149"
TEXT     = "#e6edf3"
MUTED    = "#8b949e"
HEADER   = "#010409"

F_UI    = ("Segoe UI", 10)
F_SMALL = ("Segoe UI", 9)
F_BOLD  = ("Segoe UI", 10, "bold")
F_SEC   = ("Segoe UI", 9, "bold")
F_TITLE = ("Segoe UI", 13, "bold")
F_BTN   = ("Segoe UI", 11, "bold")
F_LOG   = ("Consolas", 9)


# ─────────────────────────────────────────────────────────────────
# COMPONENTES BASE
# ─────────────────────────────────────────────────────────────────
def _entry(parent, var, width=22):
    f = tk.Frame(parent, bg=SURF2, highlightbackground=BORDER,
                 highlightthickness=1)
    e = tk.Entry(f, textvariable=var, width=width, bg=SURF2, fg=TEXT,
                 insertbackground=ACCENT, relief="flat", font=F_UI,
                 bd=6)
    e.pack(fill="x")
    return f, e


def _label(parent, text, muted=False, bold=False):
    return tk.Label(parent, text=text, bg=parent["bg"],
                    fg=MUTED if muted else TEXT,
                    font=F_BOLD if bold else F_SMALL)


def _section_card(parent, title, color=ACCENT):
    """Tarjeta con borde izquierdo de color y título."""
    outer = tk.Frame(parent, bg=SURF, highlightbackground=BORDER,
                     highlightthickness=1)
    # Borde izquierdo de color
    tk.Frame(outer, bg=color, width=3).pack(side="left", fill="y")
    inner = tk.Frame(outer, bg=SURF, padx=14, pady=10)
    inner.pack(fill="both", expand=True)
    tk.Label(inner, text=title.upper(), bg=SURF, fg=color,
             font=F_SEC).pack(anchor="w", pady=(0, 8))
    return inner


def _divider(parent):
    tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", pady=6)


def _field(parent, label, var, width=22, row=None, col=None, colspan=1):
    """Label encima de entry, colocado en grid."""
    wrap = tk.Frame(parent, bg=SURF)
    _label(wrap, label, muted=True).pack(anchor="w")
    frm, _ = _entry(wrap, var, width)
    frm.pack(fill="x", pady=(2, 0))
    if row is not None:
        wrap.grid(row=row, column=col, columnspan=colspan,
                  sticky="ew", padx=4, pady=4)
    return wrap


def _file_field(parent, label, var, filetypes=None, is_dir=False, row=0):
    wrap = tk.Frame(parent, bg=SURF)
    _label(wrap, label, muted=True).pack(anchor="w")

    row_f = tk.Frame(wrap, bg=SURF)
    row_f.pack(fill="x", pady=(2, 0))

    frm = tk.Frame(row_f, bg=SURF2, highlightbackground=BORDER, highlightthickness=1)
    frm.pack(side="left", fill="x", expand=True)
    tk.Entry(frm, textvariable=var, bg=SURF2, fg=TEXT, insertbackground=ACCENT,
             relief="flat", font=F_UI, bd=6).pack(fill="x")

    def browse():
        p = filedialog.askdirectory() if is_dir else \
            filedialog.askopenfilename(filetypes=filetypes or [("Todos", "*.*")])
        if p:
            var.set(p)

    tk.Button(row_f, text="  …  ", bg=SURF2, fg=ACCENT, font=F_SMALL,
              relief="flat", cursor="hand2", command=browse,
              activebackground=BORDER, activeforeground=TEXT,
              highlightbackground=BORDER, highlightthickness=1,
              padx=2).pack(side="left", padx=(4, 0))

    wrap.grid(row=row, column=0, columnspan=3, sticky="ew", padx=4, pady=3)
    return wrap


# ─────────────────────────────────────────────────────────────────
# APLICACIÓN
# ─────────────────────────────────────────────────────────────────
class AutoGDApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Auto-GD")
        self.configure(bg=BG)
        self.geometry("780x900")
        self.resizable(True, True)
        self.minsize(680, 700)

        # Variables
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

        self.v_metrado   = tk.StringVar(value=r"C:\Users\JesúsAndrésBustilloO\Documents\GD\Proyectos\MARTINA 1 Y 2\MARTINA_1\04. Editables\03. Tablas de Cálculo\Calculo de metros cable MARTINA 1 - copia.xlsx")
        self.v_excel_base= tk.StringVar(value=r"C:\Users\JesúsAndrésBustilloO\Documents\GD\Proyectos\MARTINA 1 Y 2\MARTINA_1\04. Editables\03. Tablas de Cálculo\PRGD-ENTRENAMIENTO CLAUDE.xlsm")
        self.v_word_base = tk.StringVar(value=r"C:\Users\JesúsAndrésBustilloO\Documents\GD\Proyectos\MARTINA 1 Y 2\MARTINA_1\04. Editables\02. Memoria Retie\PRGD-MEMORIA ENEL.docx")
        self.v_salida    = tk.StringVar(value=str(BASE_DIR / "output"))

        self._build()

    # ── Layout principal ─────────────────────────────────────────
    def _build(self):
        self._header()
        self._scroll_body()

    def _header(self):
        hdr = tk.Frame(self, bg=HEADER, pady=16)
        hdr.pack(fill="x")
        tk.Label(hdr, text="☀  AUTO-GD", bg=HEADER, fg=ACCENT,
                 font=F_TITLE).pack()
        tk.Label(hdr, text="Generador automático de memorias de cálculo fotovoltaico GD",
                 bg=HEADER, fg=MUTED, font=F_SMALL).pack(pady=(2, 0))
        tk.Frame(self, bg=ACCENT, height=2).pack(fill="x")

    def _scroll_body(self):
        wrap = tk.Frame(self, bg=BG)
        wrap.pack(fill="both", expand=True)

        canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self.body = tk.Frame(canvas, bg=BG, padx=20, pady=16)
        win = canvas.create_window((0, 0), window=self.body, anchor="nw")

        def _resize(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(win, width=canvas.winfo_width())

        self.body.bind("<Configure>", _resize)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))

        self._card_proyecto()
        self._card_archivos()
        self._card_ac()
        self._btn_run()
        self._card_log()

    # ── Tarjetas ─────────────────────────────────────────────────
    def _card_proyecto(self):
        card = _section_card(self.body, "Datos del Proyecto", ACCENT)
        card.master.pack(fill="x", pady=(0, 10))

        g = tk.Frame(card, bg=SURF)
        g.pack(fill="x")
        g.columnconfigure((0, 1, 2), weight=1)

        _field(g, "Nombre del proyecto",  self.v_nombre, row=0, col=0, colspan=2)
        _field(g, "Fecha  (YYYY-MM-DD)",  self.v_fecha,  row=0, col=2)

        _field(g, "Ciudad",               self.v_ciudad, row=1, col=0)
        _field(g, "Departamento",         self.v_depto,  row=1, col=1)

        # Temperatura
        t_frame = tk.Frame(g, bg=SURF)
        t_frame.grid(row=1, column=2, sticky="ew", padx=4, pady=4)
        _label(t_frame, "Temperaturas  (mín / máx / prom)  °C", muted=True).pack(anchor="w")
        t_row = tk.Frame(t_frame, bg=SURF)
        t_row.pack(fill="x", pady=(2, 0))
        for var in (self.v_tmin, self.v_tmax, self.v_tprom):
            frm, _ = _entry(t_row, var, width=6)
            frm.pack(side="left", padx=(0, 4))

        # Fila 2: Paneles en serie | Total de módulos | Número de inversores
        p_frame = tk.Frame(g, bg=SURF)
        p_frame.grid(row=2, column=0, sticky="ew", padx=4, pady=4)
        _label(p_frame, "Paneles en serie", muted=True).pack(anchor="w")
        frm, _ = _entry(p_frame, self.v_paneles, width=8)
        frm.pack(anchor="w", pady=(2, 0))

        m_frame = tk.Frame(g, bg=SURF)
        m_frame.grid(row=2, column=1, sticky="ew", padx=4, pady=4)
        _label(m_frame, "Total de módulos", muted=True).pack(anchor="w")
        frm, _ = _entry(m_frame, self.v_modulos, width=10)
        frm.pack(anchor="w", pady=(2, 0))

        n_frame = tk.Frame(g, bg=SURF)
        n_frame.grid(row=2, column=2, sticky="ew", padx=4, pady=4)
        _label(n_frame, "Número de inversores", muted=True).pack(anchor="w")
        spin_row = tk.Frame(n_frame, bg=SURF)
        spin_row.pack(anchor="w", pady=(2, 0))
        tk.Spinbox(spin_row, from_=1, to=10, width=5, textvariable=self.v_num_inv,
                   bg=SURF2, fg=TEXT, buttonbackground=SURF2, relief="flat",
                   font=F_UI, highlightbackground=BORDER, highlightthickness=1,
                   command=self._rebuild_ac).pack(side="left")

    def _card_archivos(self):
        card = _section_card(self.body, "Archivos", "#d29922")
        card.master.pack(fill="x", pady=(0, 10))

        g = tk.Frame(card, bg=SURF)
        g.pack(fill="x")
        g.columnconfigure(0, weight=1)

        _file_field(g, "Metrado de cables  (.xlsx)",
                    self.v_metrado, [("Excel", "*.xlsx *.xls")], row=0)
        _file_field(g, "Plantilla de cálculo  (.xlsm)",
                    self.v_excel_base, [("Excel macro", "*.xlsm")], row=1)
        _file_field(g, "Memoria base  (.docx)",
                    self.v_word_base, [("Word", "*.docx")], row=2)
        _file_field(g, "Carpeta de salida",
                    self.v_salida, is_dir=True, row=3)

    def _card_ac(self):
        self.card_ac = _section_card(self.body, "Longitud cable AC por inversor  [m]", "#3fb950")
        self.card_ac.master.pack(fill="x", pady=(0, 10))
        self._rebuild_ac()

    def _rebuild_ac(self):
        for w in self.card_ac.winfo_children():
            if isinstance(w, tk.Frame):
                w.destroy()

        n = self.v_num_inv.get()
        while len(self.v_ac_inv) < n:
            self.v_ac_inv.append(tk.StringVar(value="0"))
        self.v_ac_inv = self.v_ac_inv[:n]

        row_f = tk.Frame(self.card_ac, bg=SURF)
        row_f.pack(fill="x")

        for i in range(n):
            wrap = tk.Frame(row_f, bg=SURF)
            wrap.pack(side="left", padx=(0, 12))
            _label(wrap, f"Inv {i+1}", muted=True).pack(anchor="w")
            frm, _ = _entry(wrap, self.v_ac_inv[i], width=7)
            frm.pack(pady=(2, 0))

    def _btn_run(self):
        bar = tk.Frame(self.body, bg=BG, pady=6)
        bar.pack(fill="x")

        # Botón principal con marco de color
        btn_wrap = tk.Frame(bar, bg=GREEN, padx=2, pady=2)
        btn_wrap.pack(side="left")
        self.btn = tk.Button(btn_wrap, text="▶   EJECUTAR PIPELINE",
                             font=F_BTN, bg="#1a3a2a", fg=GREEN,
                             activebackground="#152d20", activeforeground=GREEN,
                             relief="flat", cursor="hand2",
                             padx=28, pady=10, command=self._run)
        self.btn.pack()

        tk.Button(bar, text="Limpiar log", font=F_SMALL,
                  bg=SURF, fg=MUTED, relief="flat", cursor="hand2",
                  activebackground=SURF2, activeforeground=TEXT,
                  padx=12, pady=6,
                  command=self._clear_log).pack(side="left", padx=(10, 0))

        # Barra de progreso (oculta por defecto)
        self.pb_var = tk.DoubleVar()
        self.pb = ttk.Progressbar(bar, variable=self.pb_var,
                                  maximum=100, length=200, mode="indeterminate")

    def _card_log(self):
        card = _section_card(self.body, "Log de ejecución", MUTED)
        card.master.pack(fill="both", expand=True, pady=(0, 4))

        log_frame = tk.Frame(card, bg="#010409", highlightbackground=BORDER,
                             highlightthickness=1)
        log_frame.pack(fill="both", expand=True)

        self.log = tk.Text(log_frame, height=16, bg="#010409", fg="#8b949e",
                           font=F_LOG, relief="flat", wrap="word",
                           state="disabled", insertbackground=TEXT,
                           selectbackground=SURF2, padx=8, pady=8)
        sb = ttk.Scrollbar(log_frame, command=self.log.yview)
        self.log.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log.pack(fill="both", expand=True)

        # Tags de color
        self.log.tag_configure("ok",      foreground=GREEN)
        self.log.tag_configure("err",     foreground=RED)
        self.log.tag_configure("accent",  foreground=ACCENT)
        self.log.tag_configure("muted",   foreground=MUTED)
        self.log.tag_configure("warning", foreground="#d29922")

    # ── Lógica ───────────────────────────────────────────────────
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
        for lbl, var in [("Temp. mínima", self.v_tmin),
                         ("Temp. máxima", self.v_tmax),
                         ("Temp. promedio", self.v_tprom)]:
            try:
                float(var.get())
            except ValueError:
                err.append(f"{lbl} no es un número válido.")
        try:
            v = int(self.v_paneles.get())
            if v <= 0: raise ValueError
        except ValueError:
            err.append("Paneles en serie debe ser entero positivo.")
        try:
            v = int(self.v_modulos.get())
            if v <= 0: raise ValueError
        except ValueError:
            err.append("Total de módulos debe ser entero positivo.")
        for i, v in enumerate(self.v_ac_inv):
            try:
                float(v.get())
            except ValueError:
                err.append(f"Longitud AC inversor {i+1} no es válida.")
        for nombre, var in [("Metrado Excel", self.v_metrado),
                            ("Plantilla Excel", self.v_excel_base),
                            ("Memoria Word base", self.v_word_base)]:
            if not Path(var.get()).exists():
                err.append(f"Archivo no encontrado: {nombre}")
        return err

    def _run(self):
        err = self._validar()
        if err:
            messagebox.showerror("Campos inválidos", "\n".join(err))
            return
        self.btn.configure(state="disabled", text="  Ejecutando…")
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

            slug       = proyecto["nombre"].replace(" ", "_")
            fecha_str  = fecha.strftime("%Y%m%d")
            out_dir    = Path(self.v_salida.get())
            out_dir.mkdir(parents=True, exist_ok=True)
            excel_out  = str(out_dir / f"PRGD-CALCULO-{slug}-{fecha_str}.xlsm")
            word_out   = str(out_dir / f"PRGD-MEMORIA-{slug}-{fecha_str}.docx")

            # ── Fase 1 ──────────────────────────────────────────
            self._log("━" * 52, "accent")
            self._log("  FASE 1  —  Llenando Excel de cálculo", "accent")
            self._log("━" * 52, "accent")

            metrado = leer_metrado(self.v_metrado.get())
            self._log(f"  Metrado cargado: {len(metrado)} strings", "muted")

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                llenar_excel(metrado, proyecto, self.v_excel_base.get(), excel_out)
            for line in buf.getvalue().splitlines():
                tag = "ok" if "✓" in line else "muted"
                self._log("  " + line, tag)

            # ── Fase 2+3 ─────────────────────────────────────────
            self._log("\n" + "━" * 52, "accent")
            self._log("  FASE 2+3  —  Tablas → Word", "accent")
            self._log("━" * 52, "accent")

            buf2 = io.StringIO()
            with contextlib.redirect_stdout(buf2):
                cap_exec(excel_out, self.v_word_base.get(), word_out, TABLA_MAP,
                         paneles_serie=proyecto["paneles_serie"],
                         proyecto_info=proyecto)
            for line in buf2.getvalue().splitlines():
                if "[OK]" in line or "✓" in line:
                    tag = "ok"
                elif "[ERROR]" in line or "[ADVERTENCIA]" in line:
                    tag = "err"
                elif "━" in line or "FASE" in line:
                    tag = "accent"
                else:
                    tag = "muted"
                self._log("  " + line, tag)

            self._log("\n  ✓  PROCESO COMPLETADO", "ok")
            self._log(f"     Excel  →  {excel_out}", "muted")
            self._log(f"     Word   →  {word_out}",  "muted")

        except Exception:
            self._log("\n[ERROR CRÍTICO]", "err")
            self._log(traceback.format_exc(), "err")

        finally:
            self.pb.stop()
            self.pb.pack_forget()
            self.btn.configure(state="normal", text="▶   EJECUTAR PIPELINE")


# ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = AutoGDApp()
    app.mainloop()
