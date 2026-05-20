"""
generate_ground_dxf.py — Diagrama de tierras DC
Dibuja Ground Clamps, interflex y conexiones de tierra entre mesas de paneles.

Lógica:
  - Entre mesas adyacentes: par de GROUND_CLAMP + bracket + bloque interflex
  - Mesa bajante: GROUND_CLAMP único + extensión vertical hacia abajo
  - Etiquetas MULTILEADER con conteo de conductores acumulados hacia el bajante
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    import ezdxf
except ImportError:
    sys.exit("ERROR: pip install ezdxf")

from generate_strings_dxf import (
    collect_mesas,
    group_by_row,
    detect_layout,
    ensure_layer,
    ensure_mleader_style,
    get_block_bbox,
    _draw_multileader,
    LAYER_LABELS,
)

# ─── Constantes ───────────────────────────────────────────────────────────────
LAYER_TIERRA         = "TIERRA"
COLOR_TIERRA         = 90          # ACI verde
GC_BLOCK             = "GROUND_CLAMP"
IFL_BLOCK            = "interflex"
GC_SCALE             = 0.4778
IFL_SCALE_X          = -20.5827    # escala negativa (espejo)
IFL_SCALE_Y          = 20.5827
IFL_ROTATION         = 270.0
GC_PAIR_HALF         = 0.25        # semidistancia entre el par de GC en cada límite
STUB_UP              = 1.422       # altura del stub vertical ascendente desde el GC (medido en referencia)
GC_PANEL_OFFSET      = 0.497       # distancia desde y_bottom del panel superior hasta el GC (medido en referencia)
TEXT_HEIGHT_GROUND   = 0.5         # altura de texto para etiquetas de tierras (medido en referencia)
LABEL_UP             = 3.611       # distancia vertical del leader por encima del GC (medido en referencia: 4.108 - 0.497)
BAJANTE_DOWN_DEFAULT = 3.0         # profundidad del bajante descendente
CONDUCTORS_PER_TUBE  = 6           # conductores máx por tubo Ø2"
PANEL_BLOCK_DEFAULT  = "PANEL_615"
REF_DXF_DEFAULT      = r"C:\Users\JesúsAndrésBustilloO\Documents\MOMOTUS_Tierras CLD.dxf"

# Propiedades DXF del MULTILEADER de referencia (copiadas exactamente de MOMOTUS_Tierras CLD.dxf)
_REF_ML_ATTRIBS = {
    "color":                      0,
    "lineweight":                 0,
    "leader_type":                1,
    "leader_line_color":          -1056964608,
    "leader_lineweight":          -2,
    "has_landing":                1,
    "has_dogleg":                 1,
    "dogleg_length":              0.2,
    "arrow_head_size":            0.3,
    "text_left_attachment_type":  1,
    "text_right_attachment_type": 1,
    "text_angle_type":            1,
    "text_alignment_type":        0,
    "text_color":                 -1056964608,
    "has_text_frame":             0,
    "scale":                      1.0,
    "property_override_flags":    84364930,
    # text_attachment_point se establece por etiqueta en _draw_multileader (3=top-right para texto
    # a la izquierda, 1=top-left para texto a la derecha)
}


# ─── Estilo de texto ──────────────────────────────────────────────────────────

def _ensure_romans_style(doc) -> str:
    """Crea el text style 'ROMANS' si no existe. Devuelve su handle."""
    name = "ROMANS"
    existing = [s.dxf.name for s in doc.styles]
    if name not in existing:
        doc.styles.new(name, dxfattribs={"font": "romans.shx"})
    return doc.styles.get(name).dxf.handle


def _apply_ref_ml_style(msp, doc):
    """
    Post-procesamiento: aplica las propiedades visuales del MULTILEADER de referencia
    a todos los MULTILEADER generados en la capa TEXTO del diagrama de tierras.
    """
    romans_handle = _ensure_romans_style(doc)
    updated = 0
    for e in msp:
        if e.dxftype() != "MULTILEADER" or e.dxf.get("layer", "") != LAYER_LABELS:
            continue
        for key, val in _REF_ML_ATTRIBS.items():
            try:
                e.dxf.set(key, val)
            except Exception:
                pass
        try:
            e.dxf.text_style_handle = romans_handle
        except Exception:
            pass
        try:
            e.context.mtext.style_handle = romans_handle
        except Exception:
            pass
        try:
            e.context.char_height = TEXT_HEIGHT_GROUND
            e.context.arrow_head_size = 0.3
            e.context.landing_gap_size = 0.01875
        except Exception:
            pass
        updated += 1
    if updated:
        print(f"  ML estilo  : {updated} etiquetas actualizadas con formato de referencia")


# ─── Contenido MLEADER ────────────────────────────────────────────────────────

def _content_inter(n_cond: int, n_tubes: int) -> str:
    return f'\\A1;Tubo Interflex\\P{n_tubes} x %%C2"\\P{n_cond} x 6 AWG CU\\P '


def _content_bajante(n_cond: int, n_tubes: int) -> str:
    return f'\\A1;Bajante en \\PTubo Interflex {n_tubes} x %%C2" \\P{n_cond} x 6 AWG CU'


# ─── Copia de bloques desde referencia ────────────────────────────────────────

def _copy_blocks_from_ref(ref_path: str, target_doc) -> bool:
    """Copia GROUND_CLAMP e interflex desde el DXF de referencia."""
    needed = [GC_BLOCK, IFL_BLOCK]
    to_copy = [b for b in needed if b not in target_doc.blocks]
    if not to_copy:
        return True

    try:
        ref_doc = ezdxf.readfile(ref_path)
        for bname in to_copy:
            src = ref_doc.blocks.get(bname)
            if src is None:
                print(f"  WARN: bloque '{bname}' no encontrado en referencia.")
                continue
            tgt = target_doc.blocks.new(bname)
            for e in src:
                if e.dxftype() in ("ATTDEF", "SEQEND"):
                    continue
                try:
                    tgt.add_entity(e.copy())
                except Exception:
                    pass
        copied = [b for b in to_copy if b in target_doc.blocks]
        print(f"  Bloques copiados: {copied}")
        return True
    except FileNotFoundError:
        print(f"  WARN: referencia no encontrada: {ref_path}")
        return False
    except Exception as exc:
        print(f"  WARN: error al copiar bloques: {exc}")
        return False


# ─── Primitivas de dibujo ─────────────────────────────────────────────────────

def _place_gc(msp, x: float, y: float):
    msp.add_blockref(GC_BLOCK, (x, y), dxfattribs={
        "layer":  LAYER_TIERRA,
        "xscale": GC_SCALE,
        "yscale": GC_SCALE,
        "zscale": GC_SCALE,
    })


def _draw_bracket(msp, x1: float, x2: float, y: float):
    """Polilínea en U que conecta el par de GC en un límite intermeso."""
    pts = [
        (x1 + 0.001, y),
        (x1 - 0.837, y),
        (x1 - 0.837, y - 0.482),
        (x2 + 0.833, y - 0.482),
        (x2 + 0.833, y - 0.004),
        (x2 + 0.001, y - 0.004),
    ]
    msp.add_lwpolyline(pts, dxfattribs={"layer": LAYER_TIERRA, "color": COLOR_TIERRA})


def _draw_stub_up(msp, x: float, y: float):
    """Stub vertical ascendente desde un GC hacia el nivel del ducto."""
    msp.add_lwpolyline(
        [(x, y - 0.492), (x, y + STUB_UP)],
        dxfattribs={"layer": LAYER_TIERRA, "color": COLOR_TIERRA},
    )


def _draw_gc_conn_line(msp, x: float, y: float):
    """Línea vertical en el GC opuesto al stub: desde el tope hasta el nivel del bracket."""
    msp.add_lwpolyline(
        [(x, y + STUB_UP), (x, y - 0.482)],
        dxfattribs={"layer": LAYER_TIERRA, "color": COLOR_TIERRA},
    )


def _draw_stub_down(msp, x: float, y: float, depth: float):
    """Extensión del bajante descendente desde el GC."""
    msp.add_lwpolyline(
        [(x, y), (x, y - depth)],
        dxfattribs={"layer": LAYER_TIERRA, "color": COLOR_TIERRA},
    )


def _place_interflex(msp, x: float, y: float):
    """Bloque interflex (símbolo de tubo conduit) en el límite intermeso."""
    msp.add_blockref(IFL_BLOCK, (x, y), dxfattribs={
        "layer":  "0",
        "xscale": IFL_SCALE_X,
        "yscale": IFL_SCALE_Y,
        "zscale": IFL_SCALE_Y,
        "rotation": IFL_ROTATION,
    })


# ─── Función principal ────────────────────────────────────────────────────────

def run_generate_ground(
    source_dxf:    str,
    output_dxf:    str,
    bajante_side:  str   = "R",
    panel_block:   str   = PANEL_BLOCK_DEFAULT,
    num_inversores: int  = 3,
    strings_per_inv: int = 26,
    bajante_down:  float = BAJANTE_DOWN_DEFAULT,
    ref_dxf:       str   = None,
):
    print(f"\n=== DIAGRAMA DE TIERRAS ===")
    print(f"  Fuente  : {source_dxf}")
    print(f"  Salida  : {output_dxf}")
    print(f"  Bajante : {bajante_side.upper()}")

    doc = ezdxf.readfile(source_dxf)
    msp = doc.modelspace()

    # Copiar definiciones de bloques
    ref_path = ref_dxf or REF_DXF_DEFAULT
    _copy_blocks_from_ref(ref_path, doc)

    # Asegurar capas
    ensure_layer(doc, LAYER_TIERRA, COLOR_TIERRA)
    ensure_layer(doc, LAYER_LABELS, 7)

    # Detectar layout
    info = detect_layout(doc)
    mode      = info["mode"]
    strings_pm = info["strings_per_mesa"]
    print(f"  Modo    : {mode}  |  Strings/mesa: {strings_pm}")

    # Altura del panel para calcular y_gc correctamente
    _bbox = get_block_bbox(doc, panel_block)
    panel_ph = (_bbox[3] - _bbox[1]) if _bbox else 2.384  # by1 - by0

    # Recolectar mesas
    mesas = collect_mesas(doc, panel_block, mode,
                          panel_rows_per_mesa=strings_pm,
                          skip_layers=set())
    if not mesas:
        print("  ERROR: no se encontraron mesas en el DXF.")
        return

    print(f"  Mesas   : {len(mesas)}")

    rows = group_by_row(mesas)
    print(f"  Filas   : {len(rows)}")

    # Garantizar ROMANS y MLEADERSTYLE antes de cualquier _draw_multileader
    _ensure_romans_style(doc)
    ensure_mleader_style(doc)

    cnt_gc = cnt_ifl = cnt_lbl = 0
    bajante_up = bajante_side.upper()

    for row in rows:
        ordered = sorted(row, key=lambda m: m["x_left"])
        n       = len(ordered)
        # y_gc = borde inferior del panel superior de la mesa + offset medido en referencia
        y_row   = sum(m["y_top"] - panel_ph + GC_PANEL_OFFSET for m in ordered) / n

        if bajante_up == "R":
            # Límites intermedios: de izq (k=1) a derecha (k=n-1)
            for k in range(1, n):
                m_L = ordered[k - 1]
                m_R = ordered[k]
                x_mid = (m_L["x_right"] + m_R["x_left"]) / 2.0
                x1    = x_mid - GC_PAIR_HALF
                x2    = x_mid + GC_PAIR_HALF

                n_dc_str = k * strings_pm
                n_tubes  = math.ceil(n_dc_str / CONDUCTORS_PER_TUBE)
                n_ground = n_tubes

                _place_gc(msp, x1, y_row)
                _place_gc(msp, x2, y_row)
                cnt_gc += 2
                _draw_bracket(msp, x1, x2, y_row)
                _draw_stub_up(msp, x2, y_row)           # stub en el GC derecho (lado bajante)
                _draw_gc_conn_line(msp, x1, y_row)      # línea vertical en el GC izquierdo
                _place_interflex(msp, x_mid, y_row)
                cnt_ifl += 1

                content = _content_inter(n_ground, n_tubes)
                _draw_multileader(
                    msp, doc, content,
                    x_arrow=x_mid,  y_arrow=y_row,
                    x_elbow=x_mid,  y_elbow=y_row + LABEL_UP,
                    char_height=TEXT_HEIGHT_GROUND,
                    text_left=False,
                )
                cnt_lbl += 1

            # Bajante (mesa más a la derecha)
            x_baj       = ordered[-1]["x_right"]
            n_dc_baj    = n * strings_pm
            n_tubes_baj = math.ceil(n_dc_baj / CONDUCTORS_PER_TUBE)
            n_ground_baj = n_tubes_baj

            _place_gc(msp, x_baj, y_row)
            cnt_gc += 1
            _draw_stub_down(msp, x_baj, y_row, bajante_down)
            _draw_multileader(
                msp, doc, _content_bajante(n_ground_baj, n_tubes_baj),
                x_arrow=x_baj,      y_arrow=y_row,
                x_elbow=x_baj,      y_elbow=y_row + LABEL_UP,
                char_height=TEXT_HEIGHT_GROUND,
                text_left=False,
            )
            cnt_lbl += 1

        else:  # bajante = L
            # Límites intermedios: de der (k=n-1) a izq (k=1)
            for k in range(n - 1, 0, -1):
                m_L = ordered[k - 1]
                m_R = ordered[k]
                x_mid = (m_L["x_right"] + m_R["x_left"]) / 2.0
                x1    = x_mid - GC_PAIR_HALF
                x2    = x_mid + GC_PAIR_HALF

                n_dc_str = (n - k) * strings_pm
                n_tubes  = math.ceil(n_dc_str / CONDUCTORS_PER_TUBE)
                n_ground = n_tubes

                _place_gc(msp, x1, y_row)
                _place_gc(msp, x2, y_row)
                cnt_gc += 2
                _draw_bracket(msp, x1, x2, y_row)
                _draw_stub_up(msp, x1, y_row)           # stub en el GC izquierdo (lado bajante)
                _draw_gc_conn_line(msp, x2, y_row)      # línea vertical en el GC derecho
                _place_interflex(msp, x_mid, y_row)
                cnt_ifl += 1

                content = _content_inter(n_ground, n_tubes)
                _draw_multileader(
                    msp, doc, content,
                    x_arrow=x_mid,  y_arrow=y_row,
                    x_elbow=x_mid,  y_elbow=y_row + LABEL_UP,
                    char_height=TEXT_HEIGHT_GROUND,
                    text_left=True,
                )
                cnt_lbl += 1

            # Bajante (mesa más a la izquierda)
            x_baj        = ordered[0]["x_left"]
            n_dc_baj     = n * strings_pm
            n_tubes_baj  = math.ceil(n_dc_baj / CONDUCTORS_PER_TUBE)
            n_ground_baj = n_tubes_baj

            _place_gc(msp, x_baj, y_row)
            cnt_gc += 1
            _draw_stub_down(msp, x_baj, y_row, bajante_down)
            _draw_multileader(
                msp, doc, _content_bajante(n_ground_baj, n_tubes_baj),
                x_arrow=x_baj,      y_arrow=y_row,
                x_elbow=x_baj,      y_elbow=y_row + LABEL_UP,
                char_height=TEXT_HEIGHT_GROUND,
                text_left=True,
            )
            cnt_lbl += 1

    print(f"\n  GC colocados : {cnt_gc}")
    print(f"  Interflex    : {cnt_ifl}")
    print(f"  Etiquetas    : {cnt_lbl}")

    # Aplicar formato visual de referencia a las etiquetas MULTILEADER
    _apply_ref_ml_style(msp, doc)

    # Eliminar cables DC y etiquetas IxSy si provienen del DXF fuente
    _LAYERS_STRIP = {"STRINGS_AUTO", "CONEXION"}
    to_del = [e for e in msp if e.dxf.get("layer", "") in _LAYERS_STRIP]
    for e in to_del:
        msp.delete_entity(e)
    if to_del:
        print(f"  Limpieza     : {len(to_del)} entidades strings/IxSy eliminadas")

    Path(output_dxf).parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(output_dxf)

    size_mb = Path(output_dxf).stat().st_size / 1_048_576
    print(f"\n  Guardado: {output_dxf} ({size_mb:.1f} MB)")
    print(f"  OK")


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Genera diagrama de tierras DC")
    ap.add_argument("source", help="DXF de entrada con paneles")
    ap.add_argument("-o", "--output", default=None)
    ap.add_argument("--bajante", default="R", choices=["R", "L"])
    ap.add_argument("--panel", default=PANEL_BLOCK_DEFAULT)
    ap.add_argument("--bajante-down", type=float, default=BAJANTE_DOWN_DEFAULT)
    ap.add_argument("--ref", default=None, help="DXF de referencia con bloques GC/interflex")
    args = ap.parse_args()

    stem   = Path(args.source).stem
    output = args.output or str(Path(args.source).parent / f"{stem}_tierra.dxf")
    run_generate_ground(
        source_dxf    = args.source,
        output_dxf    = output,
        bajante_side  = args.bajante,
        panel_block   = args.panel,
        bajante_down  = args.bajante_down,
        ref_dxf       = args.ref,
    )
