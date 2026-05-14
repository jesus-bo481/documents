"""
Auto-GD — Web App v3.0
Servidor Flask local que reemplaza la interfaz Tkinter.
"""
import sys, threading, importlib, queue, json, io, contextlib, traceback, subprocess
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, Response, jsonify, stream_with_context

BASE_DIR = Path(__file__).parent
MCP_DIR  = BASE_DIR.parent / "MCP AUTOCAD"
OUT_DIR  = BASE_DIR / "output"
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(MCP_DIR))

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True

_DXF_TOOLS = [
    ("strings",  "Generar Strings DC"),
    ("met_mom",  "Metrado DC — MOMOTUS"),
    ("met_iso",  "Metrado DC — ISIDORI"),
    ("mleader",  "Corregir MULTILEADER"),
]


# ── File dialog via PowerShell ─────────────────────────────────────────────────
def _browse_ps(mode, file_types=None):
    if mode == "dir":
        ps = """
Add-Type -AssemblyName System.Windows.Forms
$d = New-Object System.Windows.Forms.FolderBrowserDialog
$d.Description = 'Seleccionar carpeta'
if ($d.ShowDialog() -eq 'OK') { Write-Output $d.SelectedPath }
"""
    else:
        types = file_types or [{"name": "Todos", "ext": "*.*"}]
        flt = "|".join(f"{t['name']} ({t['ext']})|{t['ext']}" for t in types)
        ps = f"""
Add-Type -AssemblyName System.Windows.Forms
$d = New-Object System.Windows.Forms.OpenFileDialog
$d.Filter = '{flt}'
if ($d.ShowDialog() -eq 'OK') {{ Write-Output $d.FileName }}
"""
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        capture_output=True, text=True, timeout=60,
    )
    return r.stdout.strip()


# ── Routes ─────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template(
        "index.html",
        out_dir=str(OUT_DIR),
        mcp_out=str(MCP_DIR / "output"),
    )


@app.route("/api/browse", methods=["POST"])
def browse():
    data = request.json
    path = _browse_ps(data.get("mode", "file"), data.get("types"))
    return jsonify({"path": path})


@app.route("/api/run/retie", methods=["POST"])
def run_retie():
    data = request.json
    errs = _validate_retie(data)
    if errs:
        return jsonify({"errors": errs}), 400
    return _sse_stream(_worker_retie, data)


@app.route("/api/run/dxf", methods=["POST"])
def run_dxf():
    data = request.json
    if not data.get("dxf_in") or not Path(data["dxf_in"]).exists():
        return jsonify({"errors": ["Selecciona un archivo DXF de entrada válido."]}), 400
    return _sse_stream(_worker_dxf, data)


# ── SSE helper ─────────────────────────────────────────────────────────────────
def _sse_stream(worker_fn, data):
    q = queue.Queue()

    def run():
        worker_fn(q, data)
        q.put(None)

    threading.Thread(target=run, daemon=True).start()

    @stream_with_context
    def generate():
        while True:
            msg = q.get()
            if msg is None:
                yield 'data: {"done":true}\n\n'
                break
            yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _log(q, text, tag=None):
    q.put({"text": text, "tag": tag or ""})


# ── Validation ─────────────────────────────────────────────────────────────────
def _validate_retie(data):
    errs = []
    if not data.get("nombre", "").strip():
        errs.append("Falta el nombre del proyecto.")
    try:
        datetime.strptime(data.get("fecha", ""), "%Y-%m-%d")
    except ValueError:
        errs.append("Fecha inválida (usa YYYY-MM-DD).")
    for lbl, key in [("Temp. mínima", "tmin"), ("Temp. máxima", "tmax"), ("Temp. promedio", "tprom")]:
        try:
            float(data.get(key, ""))
        except (ValueError, TypeError):
            errs.append(f"{lbl} no es un número válido.")
    for i, v in enumerate(data.get("ac_inv", [])):
        try:
            float(v)
        except (ValueError, TypeError):
            errs.append(f"Longitud AC inversor {i+1} no es válida.")
    for nombre, key in [
        ("Metrado Excel", "metrado"),
        ("Plantilla Excel", "excel_base"),
        ("Memoria Word base", "word_base"),
    ]:
        val = data.get(key, "")
        if val and not Path(val).exists():
            errs.append(f"Archivo no encontrado: {nombre}")
    return errs


# ── Worker RETIE ───────────────────────────────────────────────────────────────
def _worker_retie(q, data):
    try:
        from auto_gd import leer_metrado, llenar_excel
        from capturar_tablas import ejecutar as cap_exec, TABLA_MAP

        fecha = datetime.strptime(data["fecha"], "%Y-%m-%d")
        proyecto = {
            "nombre":        data["nombre"].strip().upper(),
            "ciudad":        data["ciudad"].strip().upper(),
            "departamento":  data["depto"].strip().upper(),
            "fecha":         fecha,
            "temp_min":      float(data["tmin"]),
            "temp_max":      float(data["tmax"]),
            "temp_prom":     float(data["tprom"]),
            "long_ac_inv":   [float(x) for x in data["ac_inv"]],
            "paneles_serie": int(data["paneles"]),
            "modulos":       int(data["modulos"]),
        }
        slug      = proyecto["nombre"].replace(" ", "_")
        fecha_str = fecha.strftime("%Y%m%d")
        out_dir   = Path(data.get("salida") or str(OUT_DIR))
        out_dir.mkdir(parents=True, exist_ok=True)
        excel_out = str(out_dir / f"PRGD-CALCULO-{slug}-{fecha_str}.xlsm")
        word_out  = str(out_dir / f"PRGD-MEMORIA-{slug}-{fecha_str}.docx")

        if data.get("incl_prompt") and data.get("prompt_text", "").strip():
            _log(q, "NOTAS:", "accent")
            for line in data["prompt_text"].strip().splitlines():
                _log(q, "  " + line, "muted")
            _log(q, "")

        if data.get("fase1"):
            _log(q, "=" * 54, "accent")
            _log(q, "  FASE 1 — Llenando Excel de cálculo", "accent")
            _log(q, "=" * 54, "accent")
            metrado = leer_metrado(data["metrado"])
            _log(q, f"  Metrado cargado: {len(metrado)} strings", "muted")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                llenar_excel(metrado, proyecto, data["excel_base"], excel_out)
            for line in buf.getvalue().splitlines():
                tag = "ok" if any(x in line for x in ["OK", "ok", "✓"]) else "muted"
                _log(q, "  " + line, tag)

        if data.get("fase2"):
            _log(q, "\n" + "=" * 54, "accent")
            _log(q, "  FASE 2+3 — Captura de tablas → Word", "accent")
            _log(q, "=" * 54, "accent")
            buf2 = io.StringIO()
            with contextlib.redirect_stdout(buf2):
                cap_exec(excel_out, data["word_base"], word_out, TABLA_MAP,
                         paneles_serie=proyecto["paneles_serie"],
                         proyecto_info=proyecto)
            for line in buf2.getvalue().splitlines():
                if "[OK]" in line or "OK" in line:   tag = "ok"
                elif "[ERROR]" in line:               tag = "err"
                elif "[ADVERTENCIA]" in line:         tag = "warning"
                else:                                 tag = "muted"
                _log(q, "  " + line, tag)

        _log(q, "\n  ✓  PROCESO COMPLETADO", "ok")
        if data.get("fase1"):
            _log(q, f"     Excel  →  {excel_out}", "muted")
        if data.get("fase2"):
            _log(q, f"     Word   →  {word_out}", "muted")

    except Exception:
        _log(q, "\n[ERROR CRÍTICO]", "err")
        _log(q, traceback.format_exc(), "err")


# ── Worker DXF ─────────────────────────────────────────────────────────────────
def _worker_dxf(q, data):
    try:
        tool     = data["tool"]
        dxf_in   = data["dxf_in"]
        out_dir  = Path(data.get("out_dir") or str(MCP_DIR / "output"))
        out_dir.mkdir(parents=True, exist_ok=True)
        dxf_stem = Path(dxf_in).stem

        def dump_buf(buf):
            for line in buf.getvalue().splitlines():
                tag = "err" if "ERROR" in line else (
                      "warning" if "WARN" in line else (
                      "ok" if "OK" in line else "muted"))
                _log(q, "  " + line, tag)

        if tool == "strings":
            _log(q, "=" * 54, "accent")
            _log(q, "  STRINGS DC — Conductores + IxSy + MULTILEADER", "accent")
            _log(q, "=" * 54, "accent")
            from generate_strings_dxf import run_generate_strings
            output = str(out_dir / f"{dxf_stem}_strings.dxf")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                run_generate_strings(
                    source_dxf      = dxf_in,
                    output_dxf      = output,
                    bajante_side    = (data.get("bajante") or "R").strip().upper(),
                    panel_block     = data.get("panel") or "PANEL_615",
                    num_inversores  = int(data.get("n_inv", 3)),
                    strings_per_inv = int(data.get("str_inv", 26)),
                    start_from      = str(data.get("start", 1)),
                )
            dump_buf(buf)
            _log(q, f"\n  ✓  →  {output}", "ok")

        elif tool == "met_mom":
            _log(q, "=" * 54, "accent")
            _log(q, "  METRADO DC — estilo MOMOTUS", "accent")
            _log(q, "=" * 54, "accent")
            import metrado_strings_dxf as mod
            importlib.reload(mod)
            mod.SOURCE      = dxf_in
            mod.OUTPUT_XLSX = str(out_dir / f"metrado_{dxf_stem}.xlsx")
            mod.OUTPUT_CSV  = str(out_dir / f"metrado_{dxf_stem}.csv")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                mod.main()
            dump_buf(buf)
            _log(q, f"\n  ✓  →  {mod.OUTPUT_XLSX}", "ok")

        elif tool == "met_iso":
            _log(q, "=" * 54, "accent")
            _log(q, "  METRADO DC — estilo ISIDORI", "accent")
            _log(q, "=" * 54, "accent")
            import metrado_isidori_dxf as mod
            importlib.reload(mod)
            mod.SOURCE         = dxf_in
            mod.OUTPUT_XLSX    = str(out_dir / f"metrado_{dxf_stem}.xlsx")
            mod.OUTPUT_CSV     = str(out_dir / f"metrado_{dxf_stem}.csv")
            mod.NUM_INVERSORES = int(data.get("n_inv", 3))
            mod.MAX_STRINGS    = int(data.get("max_str", 28))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                mod.main()
            dump_buf(buf)
            _log(q, f"\n  ✓  →  {mod.OUTPUT_XLSX}", "ok")

        elif tool == "mleader":
            _log(q, "=" * 54, "accent")
            _log(q, "  FIX MULTILEADER — corrigiendo contenido", "accent")
            _log(q, "=" * 54, "accent")
            import fix_mleader_content as mod
            importlib.reload(mod)
            mod.SOURCE = dxf_in
            mod.OUTPUT = str(out_dir / f"{dxf_stem}_fixed.dxf")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                mod.main()
            dump_buf(buf)
            _log(q, f"\n  ✓  →  {mod.OUTPUT}", "ok")

    except Exception:
        _log(q, "\n[ERROR CRÍTICO]", "err")
        _log(q, traceback.format_exc(), "err")


# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import webbrowser
    url = "http://127.0.0.1:5000"
    print(f"\n  Auto-GD Web App  →  {url}\n")
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    app.run(debug=False, threaded=True, host="127.0.0.1", port=5000)
