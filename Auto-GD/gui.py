"""
Auto-GD — Interfaz gráfica
Ingresa los datos del proyecto y ejecuta el pipeline completo.
"""

import sys
import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
from pathlib import Path

# Asegurar que el directorio de Auto-GD esté en el path
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))


# ─────────────────────────────────────────────────────────────────
# COLORES Y FUENTE
# ─────────────────────────────────────────────────────────────────
BG        = "#1e1e2e"
BG2       = "#2a2a3e"
BG3       = "#313145"
ACCENT    = "#5c9bd6"
ACCENT2   = "#3a7abf"
GREEN     = "#4caf7d"
RED       = "#e05c5c"
TEXT      = "#e0e0f0"
TEXT_DIM  = "#8888aa"
FONT      = ("Segoe UI", 10)
FONT_B    = ("Segoe UI", 10, "bold")
FONT_H    = ("Segoe UI", 12, "bold")
FONT_LOG  = ("Consolas", 9)


# ─────────────────────────────────────────────────────────────────
# WIDGET HELPERS
# ─────────────────────────────────────────────────────────────────
def lbl(parent, text, bold=False, dim=False, **kw):
    color = TEXT_DIM if dim else TEXT
    f = FONT_B if bold else FONT
    return tk.Label(parent, text=text, bg=BG2, fg=color, font=f, **kw)


def entry(parent, width=30, **kw):
    e = tk.Entry(parent, width=width, bg=BG3, fg=TEXT, insertbackground=TEXT,
                 relief="flat", font=FONT, highlightthickness=1,
                 highlightbackground=ACCENT, highlightcolor=ACCENT, **kw)
    return e


def section(parent, title):
    """Frame con título de sección."""
    outer = tk.Frame(parent, bg=BG2, padx=12, pady=8)
    tk.Label(outer, text=title, bg=BG2, fg=ACCENT, font=FONT_H).pack(anchor="w", pady=(0, 6))
    return outer


def file_row(parent, label_text, var, filetypes=None, is_dir=False, row=0):
    """Fila con label + entry + botón de explorador."""
    lbl(parent, label_text).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)
    e = tk.Entry(parent, textvariable=var, width=48, bg=BG3, fg=TEXT,
                 insertbackground=TEXT, relief="flat", font=FONT,
                 highlightthickness=1, highlightbackground=ACCENT, highlightcolor=ACCENT)
    e.grid(row=row, column=1, sticky="ew", pady=3)

    def browse():
        if is_dir:
            path = filedialog.askdirectory()
        else:
            path = filedialog.askopenfilename(filetypes=filetypes or [("Todos", "*.*")])
        if path:
            var.set(path)

    btn = tk.Button(parent, text="...", bg=BG3, fg=ACCENT, font=FONT,
                    relief="flat", cursor="hand2", command=browse,
                    activebackground=ACCENT, activeforeground="white", padx=6)
    btn.grid(row=row, column=2, padx=(6, 0), pady=3)
    parent.columnconfigure(1, weight=1)


# ─────────────────────────────────────────────────────────────────
# VENTANA PRINCIPAL
# ─────────────────────────────────────────────────────────────────
class AutoGDApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Auto-GD — Generador de Memorias de Cálculo")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.geometry("800x880")

        # Variables de datos
        self.v_nombre    = tk.StringVar(value="LA MARTINA 1")
        self.v_ciudad    = tk.StringVar(value="PARATEBUENO")
        self.v_depto     = tk.StringVar(value="CUNDINAMARCA")
        self.v_fecha     = tk.StringVar(value="2026-03-31")
        self.v_tmin      = tk.StringVar(value="18")
        self.v_tmax      = tk.StringVar(value="30")
        self.v_tprom     = tk.StringVar(value="28")
        self.v_num_inv      = tk.IntVar(value=3)
        self.v_paneles_serie = tk.StringVar(value="24")
        self.v_ac_inv       = []          # se crean dinámicamente

        # Rutas
        self.v_metrado   = tk.StringVar(value=r"C:\Users\JesúsAndrésBustilloO\Documents\GD\Proyectos\MARTINA 1 Y 2\MARTINA_1\04. Editables\03. Tablas de Cálculo\Calculo de metros cable MARTINA 1 - copia.xlsx")
        self.v_excel_base= tk.StringVar(value=r"C:\Users\JesúsAndrésBustilloO\Documents\GD\Proyectos\MARTINA 1 Y 2\MARTINA_1\04. Editables\03. Tablas de Cálculo\PRGD-ENTRENAMIENTO CLAUDE.xlsm")
        self.v_word_base = tk.StringVar(value=r"C:\Users\JesúsAndrésBustilloO\Documents\GD\Proyectos\MARTINA 1 Y 2\MARTINA_1\04. Editables\02. Memoria Retie\PRGD-MEMORIA ENEL.docx")
        self.v_salida    = tk.StringVar(value=str(BASE_DIR / "output"))

        self._build_ui()

    # ── Construcción UI ──────────────────────────────────────────
    def _build_ui(self):
        canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self.inner = tk.Frame(canvas, bg=BG, padx=16, pady=12)
        win_id = canvas.create_window((0, 0), window=self.inner, anchor="nw")

        def on_configure(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(win_id, width=canvas.winfo_width())

        self.inner.bind("<Configure>", on_configure)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))

        self._section_proyecto()
        self._section_archivos()
        self._section_ac_inv()
        self._section_log()
        self._btn_ejecutar()

    def _section_proyecto(self):
        sec = section(self.inner, "Datos del Proyecto")
        sec.pack(fill="x", pady=(0, 10))

        grid = tk.Frame(sec, bg=BG2)
        grid.pack(fill="x")

        campos = [
            ("Nombre del proyecto",  self.v_nombre,  0, 0),
            ("Ciudad",               self.v_ciudad,  1, 0),
            ("Departamento",         self.v_depto,   2, 0),
            ("Fecha (YYYY-MM-DD)",   self.v_fecha,   3, 0),
            ("Temp. mínima (°C)",    self.v_tmin,    0, 2),
            ("Temp. máxima (°C)",    self.v_tmax,    1, 2),
            ("Temp. promedio (°C)",  self.v_tprom,   2, 2),
        ]

        for text, var, row, col in campos:
            lbl(grid, text).grid(row=row, column=col,   sticky="w", padx=(0,6), pady=4)
            entry(grid, textvariable=var, width=22).grid(row=row, column=col+1, sticky="ew", pady=4, padx=(0,16))

        # Número de inversores
        lbl(grid, "Número de inversores").grid(row=3, column=2, sticky="w", padx=(0,6), pady=4)
        spin = tk.Spinbox(grid, from_=1, to=10, width=5, textvariable=self.v_num_inv,
                          bg=BG3, fg=TEXT, buttonbackground=BG3, relief="flat", font=FONT,
                          command=self._actualizar_ac_inv)
        spin.grid(row=3, column=3, sticky="w", pady=4)

        # Paneles en serie
        lbl(grid, "Paneles en serie").grid(row=4, column=0, sticky="w", padx=(0,6), pady=4)
        entry(grid, textvariable=self.v_paneles_serie, width=8).grid(
            row=4, column=1, sticky="w", pady=4)

        grid.columnconfigure(1, weight=1)
        grid.columnconfigure(3, weight=1)

    def _section_archivos(self):
        sec = section(self.inner, "Archivos")
        sec.pack(fill="x", pady=(0, 10))

        grid = tk.Frame(sec, bg=BG2)
        grid.pack(fill="x")

        file_row(grid, "Metrado (Excel .xlsx)", self.v_metrado,
                 [("Excel", "*.xlsx *.xls")], row=0)
        file_row(grid, "Plantilla cálculo (.xlsm)", self.v_excel_base,
                 [("Excel macro", "*.xlsm")], row=1)
        file_row(grid, "Memoria base (.docx)", self.v_word_base,
                 [("Word", "*.docx")], row=2)
        file_row(grid, "Carpeta de salida", self.v_salida,
                 is_dir=True, row=3)

    def _section_ac_inv(self):
        self.sec_ac = section(self.inner, "Longitud cable AC por inversor [m]")
        self.sec_ac.pack(fill="x", pady=(0, 10))
        self._actualizar_ac_inv()

    def _actualizar_ac_inv(self):
        # Limpiar widgets anteriores (excepto el título)
        for w in self.sec_ac.winfo_children():
            if isinstance(w, tk.Frame):
                w.destroy()

        n = self.v_num_inv.get()
        # Preservar valores existentes
        while len(self.v_ac_inv) < n:
            self.v_ac_inv.append(tk.StringVar(value="0"))
        self.v_ac_inv = self.v_ac_inv[:n]

        grid = tk.Frame(self.sec_ac, bg=BG2)
        grid.pack(fill="x")

        for i in range(n):
            col_base = (i % 4) * 2
            row      = i // 4
            lbl(grid, f"Inversor {i+1}").grid(row=row, column=col_base,   sticky="w", padx=(0,4), pady=4)
            entry(grid, textvariable=self.v_ac_inv[i], width=8).grid(
                row=row, column=col_base+1, sticky="w", padx=(0,16), pady=4)

    def _section_log(self):
        sec = section(self.inner, "Log de ejecución")
        sec.pack(fill="both", expand=True, pady=(0, 10))

        self.log = tk.Text(sec, height=14, bg="#0d0d1a", fg="#a0f0a0",
                           font=FONT_LOG, relief="flat", wrap="word",
                           state="disabled", insertbackground=TEXT)
        sb = ttk.Scrollbar(sec, command=self.log.yview)
        self.log.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log.pack(fill="both", expand=True)

    def _btn_ejecutar(self):
        bar = tk.Frame(self.inner, bg=BG)
        bar.pack(fill="x", pady=(4, 12))

        self.btn_run = tk.Button(
            bar, text="▶  EJECUTAR PIPELINE", font=FONT_B,
            bg=GREEN, fg="white", activebackground="#3a8f5c", activeforeground="white",
            relief="flat", cursor="hand2", padx=20, pady=8,
            command=self._ejecutar
        )
        self.btn_run.pack(side="left")

        tk.Button(
            bar, text="Limpiar log", font=FONT,
            bg=BG3, fg=TEXT_DIM, activebackground=BG2, activeforeground=TEXT,
            relief="flat", cursor="hand2", padx=12, pady=8,
            command=self._limpiar_log
        ).pack(side="left", padx=(10, 0))

    # ── Lógica ──────────────────────────────────────────────────
    def _log(self, msg, color=None):
        self.log.configure(state="normal")
        tag = None
        if color:
            tag = f"color_{color}"
            self.log.tag_configure(tag, foreground=color)
        self.log.insert("end", msg + "\n", tag or "")
        self.log.see("end")
        self.log.configure(state="disabled")
        self.update_idletasks()

    def _limpiar_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _validar(self):
        errores = []
        if not self.v_nombre.get().strip():
            errores.append("Falta el nombre del proyecto.")
        try:
            datetime.strptime(self.v_fecha.get().strip(), "%Y-%m-%d")
        except ValueError:
            errores.append("Fecha inválida — usa formato YYYY-MM-DD.")
        for campo, var in [("Temp. mínima", self.v_tmin),
                           ("Temp. máxima", self.v_tmax),
                           ("Temp. promedio", self.v_tprom)]:
            try:
                float(var.get())
            except ValueError:
                errores.append(f"{campo} no es un número válido.")
        try:
            v = int(self.v_paneles_serie.get())
            if v <= 0:
                raise ValueError
        except ValueError:
            errores.append("Paneles en serie debe ser un entero positivo.")
        for i, v in enumerate(self.v_ac_inv):
            try:
                float(v.get())
            except ValueError:
                errores.append(f"Longitud AC inversor {i+1} no es válida.")
        for nombre, var in [("Metrado Excel", self.v_metrado),
                             ("Plantilla Excel", self.v_excel_base),
                             ("Memoria Word base", self.v_word_base)]:
            if not Path(var.get()).exists():
                errores.append(f"Archivo no encontrado: {nombre}")
        return errores

    def _ejecutar(self):
        errores = self._validar()
        if errores:
            messagebox.showerror("Campos inválidos", "\n".join(errores))
            return

        self.btn_run.configure(state="disabled", text="Ejecutando…")
        self._limpiar_log()
        threading.Thread(target=self._pipeline, daemon=True).start()

    def _pipeline(self):
        import traceback

        try:
            from auto_gd import leer_metrado, llenar_excel, TABLA_MAP as TABLA_MAP_BASE
            from capturar_tablas import ejecutar as cap_ejecutar, TABLA_MAP

            # ── Construir objetos desde los campos ────────────────
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
                "paneles_serie": int(self.v_paneles_serie.get()),
            }

            nombre_archivo = proyecto["nombre"].replace(" ", "_")
            fecha_str      = fecha.strftime("%Y%m%d")
            salida_dir     = Path(self.v_salida.get())
            salida_dir.mkdir(parents=True, exist_ok=True)

            excel_salida = str(salida_dir / f"PRGD-CALCULO-{nombre_archivo}-{fecha_str}.xlsm")
            word_salida  = str(salida_dir / f"PRGD-MEMORIA-{nombre_archivo}-{fecha_str}.docx")

            # ── Fase 1: llenar Excel ──────────────────────────────
            self._log("═" * 55, ACCENT)
            self._log("  FASE 1 — Llenando Excel de cálculo", ACCENT)
            self._log("═" * 55, ACCENT)

            metrado = leer_metrado(self.v_metrado.get())
            self._log(f"  Metrado cargado: {len(metrado)} strings")

            # Redirigir print → log
            import io, contextlib
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                llenar_excel(metrado, proyecto, self.v_excel_base.get(), excel_salida)
            for line in buf.getvalue().splitlines():
                self._log("  " + line)

            self._log(f"\n  ✓ Excel guardado:", GREEN)
            self._log(f"    {excel_salida}")

            # ── Fase 2+3: capturar e insertar en Word ─────────────
            self._log("\n" + "═" * 55, ACCENT)
            self._log("  FASE 2+3 — Capturando tablas e insertando en Word", ACCENT)
            self._log("═" * 55, ACCENT)

            buf2 = io.StringIO()
            with contextlib.redirect_stdout(buf2):
                cap_ejecutar(excel_salida, self.v_word_base.get(), word_salida, TABLA_MAP,
                             paneles_serie=proyecto["paneles_serie"])
            for line in buf2.getvalue().splitlines():
                color = GREEN if "[OK]" in line else (RED if "[ERROR]" in line else None)
                self._log("  " + line, color)

            self._log("\n✓ PROCESO COMPLETADO", GREEN)
            self._log(f"  Excel  → {excel_salida}")
            self._log(f"  Word   → {word_salida}")

        except Exception:
            self._log("\n[ERROR CRÍTICO]", RED)
            self._log(traceback.format_exc(), RED)

        finally:
            self.btn_run.configure(state="normal", text="▶  EJECUTAR PIPELINE")


# ─────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = AutoGDApp()
    app.mainloop()
