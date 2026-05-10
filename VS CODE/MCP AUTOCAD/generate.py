"""
Generador unico de layouts solares — reemplaza gen_colibri.py, generate_tigana.py, generate_layout.py.
Lee un JSON de proyecto y genera un DXF con los paneles implantados directamente.

Uso:
  python generate.py projects/colibri.json
  python generate.py projects/tigana.json --dry-run
  python generate.py projects/pauxi.json
"""
import sys
import json
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "server"))

import ezdxf
from tools.geometry import (
    Point, Polygon, get_bbox,
    run_panel_layout, run_hybrid_layout,
    parse_polygon_from_points,
)
from tools.dxf_writer import get_block_dims, write_layout_dxf


# ── Config ────────────────────────────────────────────────────────────────────

def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── Lectura de limite predial ─────────────────────────────────────────────────

def _polygon_area(pts: list[Point]) -> float:
    n = len(pts)
    return abs(sum(
        pts[i].x * pts[(i + 1) % n].y - pts[(i + 1) % n].x * pts[i].y
        for i in range(n)
    )) / 2.0


def _apply_margin_left(poly: list[Point], margin: float) -> list[Point]:
    """Desplaza hacia la derecha los vertices del borde izquierdo (x < min_x + 30)."""
    min_x = min(p.x for p in poly)
    return [Point(p.x + margin, p.y) if p.x < min_x + 30 else p for p in poly]


def read_boundary(doc, config: dict) -> Polygon:
    by = config.get("boundary_by", "layer")
    margin = float(config.get("boundary_margin_left_m", 0.0))

    if by == "points":
        poly = parse_polygon_from_points(config["boundary_points"])
        if margin:
            poly = _apply_margin_left(poly, margin)
        return poly

    elif by == "layer":
        layer_name = config["boundary_layer"]
        select = config.get("boundary_select", "largest")
        msp = doc.modelspace()
        polys: list[tuple[float, list[Point]]] = []

        for e in msp:
            if e.dxf.layer != layer_name:
                continue
            pts: list[Point] = []
            if e.dxftype() == "LWPOLYLINE":
                pts = [Point(float(x), float(y)) for x, y, *_ in e.get_points()]
            elif e.dxftype() == "POLYLINE":
                pts = [Point(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
            if len(pts) >= 3:
                polys.append((_polygon_area(pts), pts))

        if not polys:
            raise ValueError(f"No se encontraron polígonos en layer '{layer_name}'")

        if select == "largest":
            _, poly = max(polys, key=lambda x: x[0])
        elif select == "smallest":
            _, poly = min(polys, key=lambda x: x[0])
        elif isinstance(select, int):
            _, poly = polys[select]
        else:
            _, poly = max(polys, key=lambda x: x[0])

        if margin:
            poly = _apply_margin_left(poly, margin)
        return poly

    else:
        raise ValueError(f"boundary_by desconocido: '{by}'. Usa 'layer' o 'points'.")


# ── Lectura de obstaculos ─────────────────────────────────────────────────────

def read_obstacles(doc, config: dict) -> tuple[list[Polygon], list[tuple]]:
    """Retorna (poly_obstacles, circle_obstacles)."""
    from tools.geometry import circle_to_polygon
    poly_obs: list[Polygon] = []
    circle_obs: list[tuple[float, float, float]] = []

    # Circulos hardcodeados en JSON
    for c in config.get("circle_obstacles", []):
        circle_obs.append((float(c[0]), float(c[1]), float(c[2])))

    # Circulos desde capa del DXF
    circles_layer = config.get("obstacles_circles_layer")
    if circles_layer and doc:
        for e in doc.modelspace():
            if e.dxftype() == "CIRCLE" and e.dxf.layer == circles_layer:
                circle_obs.append((e.dxf.center.x, e.dxf.center.y, e.dxf.radius))

    # Poligonos de obstaculos desde capa del DXF
    poly_layer = config.get("obstacles_poly_layer")
    if poly_layer and doc:
        for e in doc.modelspace():
            if e.dxf.layer != poly_layer:
                continue
            pts: list[Point] = []
            if e.dxftype() == "LWPOLYLINE":
                pts = [Point(float(x), float(y)) for x, y, *_ in e.get_points()]
            elif e.dxftype() == "POLYLINE":
                pts = [Point(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
            if len(pts) >= 3:
                poly_obs.append(pts)

    # Arboles desde bloque anidado (ej: Topo Pauxi)
    tree_cfg = config.get("obstacle_tree_block")
    if tree_cfg and doc:
        container = tree_cfg["container_block"]
        filter_layer = tree_cfg.get("filter_layer_contains", "")
        off_x = float(tree_cfg.get("insert_offset_x", 0.0))
        off_y = float(tree_cfg.get("insert_offset_y", 0.0))
        radius = float(tree_cfg["radius"])

        if container in doc.blocks:
            for e in doc.blocks[container]:
                layer_attr = e.dxf.layer if e.dxf.hasattr("layer") else ""
                if filter_layer and filter_layer not in layer_attr:
                    continue
                if e.dxftype() == "INSERT":
                    cx = e.dxf.insert.x + off_x
                    cy = e.dxf.insert.y + off_y
                    circle_obs.append((cx, cy, radius))

    return poly_obs, circle_obs


# ── Pipeline principal ────────────────────────────────────────────────────────

def run_project(config_path: str, dry_run: bool = False) -> str:
    config = load_config(config_path)
    project_name = config["project_name"]
    source_dxf   = config["source_dxf"]
    output_dxf   = config.get("output_dxf", f"output/{project_name}.dxf")
    block_name   = config.get("block_name", "PANEL_615")
    block_lib    = config.get("block_library_dxf")

    print(f"\n=== PROYECTO: {project_name} ===")
    print(f"  Source : {source_dxf}")
    print(f"  Output : {output_dxf}")

    doc = ezdxf.readfile(source_dxf)

    # Dimensiones del panel
    if config.get("panel_width_m") and config.get("panel_height_m"):
        panel_w      = float(config["panel_width_m"])
        panel_h      = float(config["panel_height_m"])
        blk_offset_x = float(config.get("blk_offset_x", 0.0))
        blk_offset_y = float(config.get("blk_offset_y", 0.0))
        print(f"  Panel  : {panel_w:.4f} x {panel_h:.4f} m (config manual)")
    else:
        panel_w, panel_h, blk_offset_x, blk_offset_y = get_block_dims(source_dxf, block_name)
        print(f"  Panel  : {panel_w:.4f} x {panel_h:.4f} m (auto desde bloque)")
    print(f"  Offset : ({blk_offset_x:.4f}, {blk_offset_y:.4f})")

    # Limite predial
    print("\nLeyendo polígono límite...")
    boundary = read_boundary(doc, config)
    bbox = get_bbox(boundary)
    print(f"  {len(boundary)} vertices | {bbox.max_x - bbox.min_x:.1f} m x {bbox.max_y - bbox.min_y:.1f} m")

    # Obstaculos
    print("Leyendo obstáculos...")
    poly_obs, circle_obs = read_obstacles(doc, config)
    print(f"  {len(poly_obs)} poligonales, {len(circle_obs)} circulares")

    # Parametros de layout
    panels_wide     = int(config.get("panels_wide", 26))
    panels_high     = int(config.get("panels_high", 2))
    module_gap      = float(config.get("module_gap_m", 0.04))
    gap_h           = float(config.get("gap_horizontal_m", 0.5))
    gap_v           = float(config.get("gap_vertical_m", 2.5))
    num_groups      = int(config.get("num_groups", 1))
    panels_per_group= int(config.get("panels_per_group", 0))
    group_sep       = float(config.get("group_sep_m", 6.0))
    layout_mode     = config.get("layout_mode", "rows")
    fill_tb         = bool(config.get("fill_top_to_bottom", False))
    layer_prefix    = config.get("layer_prefix", "GD")

    hybrid_cfg     = config.get("hybrid", {})
    hybrid_enabled = hybrid_cfg.get("enabled", False)

    common = dict(
        boundary=boundary,
        panel_w=panel_w, panel_h=panel_h,
        gap_h=gap_h, gap_v=gap_v,
        num_groups=num_groups,
        panels_per_group=panels_per_group,
        poly_obstacles=poly_obs or None,
        circle_obstacles=circle_obs or None,
        group_sep=group_sep,
        panels_wide=panels_wide, panels_high=panels_high,
        module_gap=module_gap,
        layout_mode=layout_mode,
        fill_top_to_bottom=fill_tb,
    )

    fallback_pl: list[dict] = []
    fw = fh = 0

    if hybrid_enabled:
        fw = int(hybrid_cfg.get("fallback_wide", 13))
        fh = int(hybrid_cfg.get("fallback_high", 2))
        target = int(hybrid_cfg.get("target_panels", 0))
        print(f"\nCalculando layout hibrido {panels_wide}x{panels_high} + {fw}x{fh}...")
        result = run_hybrid_layout(**common, fallback_wide=fw, fallback_high=fh, target_panels=target)
        placements   = result["primary"]
        fallback_pl  = result["fallback"]
        panels_p     = result["panels_primary"]
        panels_f     = result["panels_fallback"]
        print(f"  Primaria  {panels_wide}x{panels_high}: {len(placements)} mesas = {panels_p} paneles")
        print(f"  Fallback  {fw}x{fh}        : {len(fallback_pl)} mesas = {panels_f} paneles")
        print(f"  TOTAL: {result['total_panels']} paneles")
    else:
        print(f"\nCalculando layout {panels_wide}x{panels_high}, {num_groups} GD(s)...")
        placements = run_panel_layout(**common)
        by_group: dict[int, int] = {}
        for p in placements:
            by_group[p["group"]] = by_group.get(p["group"], 0) + 1
        total_panels = sum(c * panels_wide * panels_high for c in by_group.values())
        for g, c in sorted(by_group.items()):
            print(f"  GD{g}: {c} mesas = {c * panels_wide * panels_high} paneles")
        print(f"  TOTAL: {len(placements)} mesas, {total_panels} paneles")

    if dry_run:
        print("\n[DRY RUN] No se escribe el DXF.")
        return ""

    print("\nEscribiendo DXF...")
    out = write_layout_dxf(
        source_dxf_path=source_dxf,
        output_dxf_path=output_dxf,
        placements=placements,
        block_name=block_name,
        panels_wide=panels_wide,
        panels_high=panels_high,
        panel_w=panel_w,
        panel_h=panel_h,
        blk_offset_x=blk_offset_x,
        blk_offset_y=blk_offset_y,
        module_gap=module_gap,
        layer_prefix=layer_prefix,
        block_library_dxf=block_lib,
        fallback_placements=fallback_pl if fallback_pl else None,
        fallback_wide=fw,
        fallback_high=fh,
    )
    size_mb = Path(out).stat().st_size / 1024 / 1024
    print(f"  DXF generado : {out}")
    print(f"  Tamaño       : {size_mb:.1f} MB")
    print(f"\nAbrir en AutoCAD LT: File → Open → {out}")
    return out


# ── Entrypoint ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso:  python generate.py projects/<proyecto>.json [--dry-run]")
        print("      python generate.py projects/colibri.json")
        print("      python generate.py projects/tigana.json --dry-run")
        sys.exit(1)

    run_project(sys.argv[1], dry_run="--dry-run" in sys.argv)
