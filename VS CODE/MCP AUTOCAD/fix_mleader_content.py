"""
fix_mleader_content.py
Corrige el contenido de los MULTILEADER en MOMOTUS_strings_v5_ixsy.dxf
manteniendo su estilo ISO-25 de AutoCAD intacto.

Solo actualiza ml.context.mtext.default_content — no toca geometria ni estilo.
"""
import math
import sys
from pathlib import Path

# Permite importar generate_strings_dxf desde el mismo directorio
sys.path.insert(0, str(Path(__file__).parent))

try:
    import ezdxf
except ImportError:
    sys.exit("ERROR: pip install ezdxf")

from generate_strings_dxf import (
    collect_mesas,
    group_by_row,
    get_block_bbox,
    detect_layout,
    MODULE_GAP,
    LAYER_LABELS,
)

SOURCE = r"C:\Users\JesúsAndrésBustilloO\Documents\VS CODE\MCP AUTOCAD\output\MOMOTUS_strings_v5_ixsy.dxf"
OUTPUT = r"C:\Users\JesúsAndrésBustilloO\Documents\VS CODE\MCP AUTOCAD\output\MOMOTUS_strings_v6_final2.dxf"

BAJANTE_SIDE   = "R"    # lado del bajante
PANEL_BLOCK    = "PANEL_615"   # bloque de panel individual


# ─── Generación de contenido ──────────────────────────────────────────────────

def content_inter(n_cond: int) -> str:
    n_tubes = math.ceil(n_cond / 6)
    return (
        f"\\A1;Tubo Interflex\\P"
        f"{n_tubes} x %%C2\"\\P"
        f"{n_cond}x6mm2(+) + {n_cond}x6mm2 (-)\\P "
    )


def content_bajante(n_cond: int) -> str:
    n_tubes = math.ceil(n_cond / 6)
    return (
        f"\\A1;Bajante en \\P"
        f"Tubo Interflex {n_tubes} x %%C2\" \\P"
        f"{n_cond}x6mm2(+) + {n_cond}x6mm2 (-)"
    )


# ─── Posiciones esperadas ─────────────────────────────────────────────────────

class ExpPos:
    __slots__ = ("x", "y", "n_cond", "kind")

    def __init__(self, x, y, n_cond, kind):
        self.x = x; self.y = y
        self.n_cond = n_cond
        self.kind = kind  # 'inter' | 'bajante'

    def content(self):
        return content_inter(self.n_cond) if self.kind == "inter" else content_bajante(self.n_cond)


def build_expected(rows: list, strings_pm: int, bajante_side: str) -> list:
    """
    Para cada fila de mesas, calcula las posiciones esperadas de los arrows.
    bajante_side='R': la mesa más a la derecha es el bajante.
    """
    positions = []
    for row in rows:
        ordered = sorted(row, key=lambda m: m["x_left"])   # izq → der
        n_mesas  = len(ordered)
        y_row    = sum((m["y_bottom"] + m["y_top"]) / 2.0 for m in ordered) / n_mesas

        if bajante_side.upper() == "R":
            # bajante en la derecha; los intermedios van de izq a der
            for i in range(n_mesas - 1):
                x_gap = (ordered[i]["x_right"] + ordered[i + 1]["x_left"]) / 2.0
                n_cond = (i + 1) * strings_pm
                positions.append(ExpPos(x_gap, y_row, n_cond, "inter"))
            x_baj  = ordered[-1]["x_right"]
        else:
            # bajante en la izquierda
            for i in range(n_mesas - 1, 0, -1):
                x_gap = (ordered[i]["x_left"] + ordered[i - 1]["x_right"]) / 2.0
                n_cond = (n_mesas - i) * strings_pm
                positions.append(ExpPos(x_gap, y_row, n_cond, "inter"))
            x_baj = ordered[0]["x_left"]

        n_tot = n_mesas * strings_pm
        positions.append(ExpPos(x_baj, y_row, n_tot, "bajante"))

    return positions


# ─── Lectura del arrow point ──────────────────────────────────────────────────

def get_arrow_xy(ml):
    """Coordenadas (x, y) del punto de flecha del primer leader."""
    try:
        v = ml.context.leaders[0].lines[0].vertices[0]
        return float(v.x), float(v.y)
    except Exception:
        return None


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print(f"\n=== FIX MLEADER CONTENT ===")
    print(f"  Fuente : {SOURCE}")
    print(f"  Salida : {OUTPUT}\n")

    doc = ezdxf.readfile(SOURCE)
    msp = doc.modelspace()

    # 1. Detectar layout
    info = detect_layout(doc)
    block_name    = PANEL_BLOCK   # siempre usar bloque de panel individual
    mode          = info["mode"]
    strings_pm    = info["strings_per_mesa"]
    print(f"  Bloque       : {block_name}  (modo: {mode})")
    print(f"  Strings/mesa : {strings_pm}")

    # BBox del bloque de panel
    bbox = get_block_bbox(doc, block_name)
    if bbox is None:
        sys.exit(f"ERROR: no se pudo medir '{block_name}'")
    bx0, by0, bx1, by1 = bbox
    panel_w = bx1 - bx0
    print(f"  Panel width  : {panel_w:.4f} m")

    # 2. Recolectar mesas correctamente (agrupa N paneles por mesa)
    mesas = collect_mesas(
        doc, block_name,
        mode            = "individual_panels",
        panel_rows_per_mesa = strings_pm,
        skip_layers     = {"0"},
    )
    if not mesas:
        sys.exit("ERROR: no se encontraron mesas.")
    print(f"  Mesas reales : {len(mesas)}")

    # 3. Agrupar en filas
    rows = group_by_row(mesas)
    print(f"  Filas        : {len(rows)}")
    for i, row in enumerate(rows):
        yc = sum((m["y_bottom"] + m["y_top"]) / 2.0 for m in row) / len(row)
        print(f"    Fila {i+1:2d}: {len(row):3d} mesas  "
              f"y_c={yc:.1f}  "
              f"x=[{row[0]['x_left']:.1f} .. {row[-1]['x_right']:.1f}]")

    # 4. Construir posiciones esperadas
    expected = build_expected(rows, strings_pm, BAJANTE_SIDE)
    n_inter = sum(1 for p in expected if p.kind == "inter")
    n_baj   = sum(1 for p in expected if p.kind == "bajante")
    print(f"\n  Posiciones esperadas: {len(expected)} "
          f"({n_inter} inter + {n_baj} bajante)")

    # Tolerancia: mitad del ancho promedio de una mesa real
    avg_mesa_w = sum(m["x_right"] - m["x_left"] for m in mesas) / len(mesas)
    tol = avg_mesa_w * 1.5
    print(f"  Tolerancia match    : {tol:.1f} m")

    # 5. Actualizar MULTILEADER
    updated  = 0
    warnings = []
    total_ml = 0

    for e in msp:
        if e.dxftype() != "MULTILEADER":
            continue
        try:
            layer = e.dxf.layer
        except Exception:
            layer = ""
        if layer != LAYER_LABELS:
            continue

        total_ml += 1
        pt = get_arrow_xy(e)
        if pt is None:
            warnings.append(f"  WARN: MULTILEADER handle={e.dxf.handle} sin arrow legible")
            continue

        x_arrow, y_arrow = pt

        # Posicion esperada mas cercana
        best      = min(expected, key=lambda p: math.hypot(x_arrow - p.x, y_arrow - p.y))
        dist      = math.hypot(x_arrow - best.x, y_arrow - best.y)

        if dist > tol:
            warnings.append(
                f"  WARN: arrow=({x_arrow:.1f},{y_arrow:.1f}) "
                f"no coincide (dist={dist:.1f} > tol={tol:.1f})"
            )
            continue

        new_content = best.content()

        try:
            old_content = e.context.mtext.default_content
            e.context.mtext.default_content = new_content
            changed = "==" if old_content == new_content else "actualizado"
            print(f"  [{best.kind:7s}] n_cond={best.n_cond:3d}  "
                  f"arrow=({x_arrow:.1f},{y_arrow:.1f})  dist={dist:.1f}  {changed}")
            updated += 1
        except AttributeError as err:
            warnings.append(f"  ERROR handle={e.dxf.handle}: {err}")

    print(f"\n  MULTILEADER en '{LAYER_LABELS}': {total_ml}")
    print(f"  Actualizados          : {updated}")
    if warnings:
        print(f"\n  Avisos ({len(warnings)}):")
        for w in warnings:
            print(w)

    # 6. Guardar en nuevo archivo
    Path(OUTPUT).parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(OUTPUT)
    size_mb = Path(OUTPUT).stat().st_size / 1_048_576
    print(f"\n  Guardado: {OUTPUT} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
