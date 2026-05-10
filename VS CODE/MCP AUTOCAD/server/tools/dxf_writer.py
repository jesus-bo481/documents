"""
DXF writer — genera archivos DXF con paneles solares implantados directamente.
Alternativa a la generacion de LISP: el output es un .dxf abrible en AutoCAD LT.

Flujo:
  1. Abre el DXF fuente como base (hereda layers, bloques, entidades existentes)
  2. Importa el bloque de panel si no esta definido en el fuente
  3. Crea layers GD1, GD2, ... con colores ACI
  4. Inserta bloques (INSERT entities) en las posiciones calculadas
  5. Guarda como nuevo archivo .dxf
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional

try:
    import ezdxf
    HAS_EZDXF = True
except ImportError:
    HAS_EZDXF = False

# Paleta de colores ACI por grupo/GD
_GD_COLORS = {1: 2, 2: 4, 3: 3, 4: 6, 5: 5, 6: 1, 7: 7}  # yellow, cyan, green, magenta, blue, red, white


def _require_ezdxf():
    if not HAS_EZDXF:
        raise ImportError("ezdxf no instalado. Ejecuta: pip install ezdxf")


def get_block_dims(dxf_path: str, block_name: str) -> tuple[float, float, float, float]:
    """
    Calcula dimensiones del bloque y posicion del insert point relativo a su bbox.
    Retorna (panel_w, panel_h, blk_offset_x, blk_offset_y).

    blk_offset_x/y = distancia desde la esquina inferior-izquierda del bbox al punto (0,0) del bloque.
    Para PANEL_615: bbox (-0.567, -1.151) → (0.736, 1.233), offsets = (0.567, 1.151).
    """
    _require_ezdxf()
    doc = ezdxf.readfile(dxf_path)
    block = doc.blocks.get(block_name)
    if block is None:
        raise ValueError(f"Bloque '{block_name}' no encontrado en {dxf_path}")

    xs, ys = [], []
    for e in block:
        t = e.dxftype()
        if t == "LINE":
            xs += [e.dxf.start.x, e.dxf.end.x]
            ys += [e.dxf.start.y, e.dxf.end.y]
        elif t == "LWPOLYLINE":
            for pt in e.get_points():
                xs.append(pt[0]); ys.append(pt[1])
        elif t == "POLYLINE":
            for v in e.vertices:
                xs.append(v.dxf.location.x); ys.append(v.dxf.location.y)
        elif t == "SOLID":
            for attr in ("vtx0", "vtx1", "vtx2", "vtx3"):
                if e.dxf.hasattr(attr):
                    v = getattr(e.dxf, attr)
                    xs.append(v.x); ys.append(v.y)
        elif t == "HATCH":
            for path in e.paths:
                for edge in getattr(path, "edges", []):
                    if hasattr(edge, "start"):
                        xs += [edge.start.x, edge.end.x]
                        ys += [edge.start.y, edge.end.y]
        elif t == "INSERT":
            xs.append(e.dxf.insert.x); ys.append(e.dxf.insert.y)

    if not xs:
        raise ValueError(f"No se pudo calcular bbox del bloque '{block_name}' — sin geometria legible")

    bx0, bx1 = min(xs), max(xs)
    by0, by1 = min(ys), max(ys)
    return bx1 - bx0, by1 - by0, -bx0, -by0


def _import_block(source_dxf_path: str, target_doc, block_name: str) -> None:
    """Importa la definicion de un bloque desde otro DXF al documento destino."""
    from ezdxf.importer import Importer
    src = ezdxf.readfile(source_dxf_path)
    imp = Importer(src, target_doc)
    imp.import_block(block_name)
    imp.finalize()


def write_layout_dxf(
    source_dxf_path: str,
    output_dxf_path: str,
    placements: list[dict],
    block_name: str,
    panels_wide: int,
    panels_high: int,
    panel_w: float,
    panel_h: float,
    blk_offset_x: float,
    blk_offset_y: float,
    module_gap: float,
    layer_prefix: str = "GD",
    draw_mesa_outlines: bool = True,
    draw_labels: bool = True,
    label_height: float = 1.5,
    block_library_dxf: Optional[str] = None,
    fallback_placements: Optional[list[dict]] = None,
    fallback_wide: int = 0,
    fallback_high: int = 0,
) -> str:
    """
    Genera DXF con paneles implantados como bloques INSERT.

    Abre source_dxf_path como base (incluye contexto del predio y definicion del bloque),
    añade INSERT entities calculadas por el motor geometry.py y guarda en output_dxf_path.

    Si el bloque block_name no existe en el fuente, lo importa desde block_library_dxf.
    Para modo hibrido: proveer fallback_placements + fallback_wide/high.

    Retorna la ruta absoluta del archivo generado.
    """
    _require_ezdxf()

    doc = ezdxf.readfile(source_dxf_path)
    msp = doc.modelspace()

    # Importar bloque si no existe en el DXF fuente
    if block_name not in [b.name for b in doc.blocks]:
        if block_library_dxf:
            _import_block(block_library_dxf, doc, block_name)
        else:
            raise ValueError(
                f"Bloque '{block_name}' no encontrado en {source_dxf_path}. "
                "Especifica 'block_library_dxf' en el JSON del proyecto."
            )

    step_x = panel_w + module_gap
    step_y = panel_h + module_gap

    def ensure_layer(name: str, color: int):
        if name not in doc.layers:
            doc.layers.add(name, color=color)

    def _mesa_wh(pw: int, ph: int) -> tuple[float, float]:
        return (pw - 1) * step_x + panel_w, (ph - 1) * step_y + panel_h

    def insert_panels(pl: list[dict], pw: int, ph: int, layer_name: str):
        for mesa in pl:
            bx, by = mesa["x"], mesa["y"]
            for row in range(ph):
                for col in range(pw):
                    ix = bx + blk_offset_x + col * step_x
                    iy = by + blk_offset_y + row * step_y
                    msp.add_blockref(
                        block_name,
                        insert=(ix, iy, 0.0),
                        dxfattribs={
                            "layer": layer_name,
                            "xscale": 1.0, "yscale": 1.0, "zscale": 1.0,
                            "rotation": 0.0,
                        },
                    )

    def draw_outlines(pl: list[dict], pw: int, ph: int, layer_name: str):
        mw, mh = _mesa_wh(pw, ph)
        for mesa in pl:
            bx, by = mesa["x"], mesa["y"]
            msp.add_lwpolyline(
                [(bx, by), (bx + mw, by), (bx + mw, by + mh), (bx, by + mh)],
                dxfattribs={"layer": layer_name, "closed": True},
            )

    def draw_gd_labels(pl: list[dict], pw: int, ph: int, gd: int, layer_name: str):
        mw, mh = _mesa_wh(pw, ph)
        for mesa in pl:
            bx, by = mesa["x"], mesa["y"]
            msp.add_text(
                f"GD{gd}",
                dxfattribs={
                    "layer": layer_name,
                    "height": label_height,
                    "insert": (bx + mw / 2, by + mh / 2),
                },
            )

    # ── Paneles primarios ─────────────────────────────────────────────────────
    gd_groups = sorted(set(p["group"] for p in placements))
    for gd in gd_groups:
        layer_name = f"{layer_prefix}{gd}"
        color = _GD_COLORS.get(gd, 7)
        ensure_layer(layer_name, color)
        gd_pl = [p for p in placements if p["group"] == gd]
        insert_panels(gd_pl, panels_wide, panels_high, layer_name)
        if draw_mesa_outlines:
            draw_outlines(gd_pl, panels_wide, panels_high, layer_name)
        if draw_labels:
            draw_gd_labels(gd_pl, panels_wide, panels_high, gd, layer_name)

    # ── Paneles fallback (modo hibrido) ───────────────────────────────────────
    if fallback_placements and fallback_wide > 0 and fallback_high > 0:
        gd_groups_f = sorted(set(p["group"] for p in fallback_placements))
        for gd in gd_groups_f:
            layer_name = f"{layer_prefix}{gd}_{fallback_wide}x{fallback_high}"
            color = _GD_COLORS.get(gd, 7)
            ensure_layer(layer_name, color)
            gd_pl_f = [p for p in fallback_placements if p["group"] == gd]
            insert_panels(gd_pl_f, fallback_wide, fallback_high, layer_name)
            if draw_mesa_outlines:
                draw_outlines(gd_pl_f, fallback_wide, fallback_high, layer_name)

    Path(output_dxf_path).parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(output_dxf_path)
    return str(Path(output_dxf_path).resolve())
