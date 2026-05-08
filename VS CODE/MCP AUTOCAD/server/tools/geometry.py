"""
Motor geométrico Python — migración directa desde solar_array_layout_v1.15.lsp
Funciones: sa-pip, sa-bbox, bloque-ok-v15, circle-to-poly, get-poly-pts

Modos de layout:
  rows    — GDs apilados verticalmente, relleno de abajo hacia arriba (original LISP)
  columns — GDs en columnas horizontales, relleno configurable (top-to-bottom por defecto)

Separaciones estándar (del LISP original):
  Entre mesas:   gap_h=0.5 m horizontal,  gap_v=2.5 m vertical
  Entre módulos: module_gap=0.04 m (dentro de una misma mesa)
  Entre GDs:     group_sep=6.0 m (rows) / 8.0 m (columns — según proyecto)
"""
import math
from typing import NamedTuple


class Point(NamedTuple):
    x: float
    y: float


class BBox(NamedTuple):
    min_x: float
    min_y: float
    max_x: float
    max_y: float


Polygon = list[Point]


# ── Equivalente a: (defun sa-pip ...) ────────────────────────────────────────
def point_in_polygon(px: float, py: float, polygon: Polygon) -> bool:
    """Ray casting algorithm. Fiel traducción de sa-pip."""
    n = len(polygon)
    count = 0
    for i in range(n):
        j = (i + 1) % n
        xi, yi = polygon[i].x, polygon[i].y
        xj, yj = polygon[j].x, polygon[j].y
        if abs(yi - yj) < 1e-10:
            continue
        if (yi > py) != (yj > py):
            x_intersect = xi + (py - yi) / (yj - yi) * (xj - xi)
            if px < x_intersect:
                count += 1
    return (count % 2) == 1


# ── Equivalente a: (defun sa-bbox ...) ───────────────────────────────────────
def get_bbox(polygon: Polygon) -> BBox:
    xs = [p.x for p in polygon]
    ys = [p.y for p in polygon]
    return BBox(min(xs), min(ys), max(xs), max(ys))


# ── Equivalente a: (defun circle-to-poly ...) ────────────────────────────────
def circle_to_polygon(cx: float, cy: float, r: float, n: int = 24) -> Polygon:
    """Discretiza un círculo en un polígono de n lados."""
    step = (2.0 * math.pi) / n
    return [
        Point(cx + r * math.cos(k * step), cy + r * math.sin(k * step))
        for k in range(n)
    ]


# ── Colisión rectángulo-círculo (equivalente al check exacto en bloque-ok-v15)
def rect_intersects_circle(
    x1: float, y1: float, x2: float, y2: float,
    cx: float, cy: float, r: float
) -> bool:
    """Punto más cercano del rectángulo al centro del círculo."""
    near_x = max(x1, min(cx, x2))
    near_y = max(y1, min(cy, y2))
    dist = math.sqrt((cx - near_x) ** 2 + (cy - near_y) ** 2)
    return dist < r


# ── Equivalente a: (defun bloque-ok-v15 ...) ─────────────────────────────────
def can_place_panel(
    bx: float, by: float,
    bw: float, bh: float,
    boundary: Polygon,
    poly_obstacles: list[Polygon] | None = None,
    circle_obstacles: list[tuple[float, float, float]] | None = None,
) -> bool:
    """
    Valida si un bloque/mesa puede colocarse en (bx, by).
    bx, by = esquina inferior izquierda del bloque.
    Migración completa de bloque-ok-v15.
    """
    x1, y1 = bx, by
    x2, y2 = bx + bw, by + bh
    cx, cy = bx + bw / 2.0, by + bh / 2.0

    # 1) Las 4 esquinas + centro dentro del polígono límite
    corners = [(x1, y1), (x2, y1), (x2, y2), (x1, y2), (cx, cy)]
    if not all(point_in_polygon(px, py, boundary) for px, py in corners):
        return False

    # 2) Colisión con obstáculos poligonales
    if poly_obstacles:
        for obs in poly_obstacles:
            if any(point_in_polygon(px, py, obs) for px, py in corners):
                return False
            if any(x1 < v.x < x2 and y1 < v.y < y2 for v in obs):
                return False

    # 3) Colisión con obstáculos circulares (verificación exacta)
    if circle_obstacles:
        for ccx, ccy, cr in circle_obstacles:
            if rect_intersects_circle(x1, y1, x2, y2, ccx, ccy, cr):
                return False

    return True


# ── Helper de dimensiones de mesa ────────────────────────────────────────────
def _mesa_dims(
    panels_wide: int, panels_high: int,
    panel_w: float, panel_h: float,
    module_gap: float,
) -> tuple[float, float]:
    w = panels_wide * panel_w + (panels_wide - 1) * module_gap
    h = panels_high * panel_h + (panels_high - 1) * module_gap
    return w, h


# ── Motor de layout principal ─────────────────────────────────────────────────
def run_panel_layout(
    boundary: Polygon,
    panel_w: float,
    panel_h: float,
    gap_h: float = 0.5,
    gap_v: float = 2.5,
    num_groups: int = 1,
    panels_per_group: int = 0,
    poly_obstacles: list[Polygon] | None = None,
    circle_obstacles: list[tuple[float, float, float]] | None = None,
    group_sep: float = 6.0,
    panels_wide: int = 0,
    panels_high: int = 0,
    module_gap: float = 0.04,
    layout_mode: str = "rows",
    fill_top_to_bottom: bool = False,
) -> list[dict]:
    """
    Calcula las posiciones de mesas dentro de un polígono límite.
    Devuelve lista de {group, x, y} donde (x,y) = esquina inferior-izquierda de la MESA.

    panel_w / panel_h    : dimensiones del bloque. Si panels_wide/high=0, el bloque ES la mesa.
    panels_wide/high     : si >0, el bloque es un módulo individual y la mesa es la agrupación.
    module_gap           : separación entre módulos dentro de la mesa (0.04 m recomendado).
    gap_h / gap_v        : separación ENTRE MESAS (0.5 m H, 2.5 m V según LISP original).
    group_sep            : separación entre GDs (6 m en rows, 8 m en columns típicamente).
    layout_mode          : "rows"    = GDs apilados en Y, relleno de abajo hacia arriba.
                           "columns" = GDs en bandas verticales de X, relleno configurable.
    fill_top_to_bottom   : solo en modo columns — True = llena de arriba abajo (acceso inferior).
    """
    # Calcular dimensiones reales de la mesa
    if panels_wide > 0 and panels_high > 0:
        mesa_w, mesa_h = _mesa_dims(panels_wide, panels_high, panel_w, panel_h, module_gap)
    else:
        mesa_w = panel_w
        mesa_h = panel_h

    bbox = get_bbox(boundary)
    placements: list[dict] = []

    if layout_mode == "columns":
        # ── Modo columnas: cada GD ocupa una banda vertical del bbox ─────────
        total_w = bbox.max_x - bbox.min_x
        col_w = (total_w - (num_groups - 1) * group_sep) / max(num_groups, 1)

        for gd_idx in range(num_groups):
            col_x_left  = bbox.min_x + gd_idx * (col_w + group_sep)
            col_x_right = col_x_left + col_w
            count_gd = 0
            done_gd  = False

            # Posición inicial y dirección de relleno en Y
            if fill_top_to_bottom:
                y = bbox.max_y - gap_v - mesa_h
                y_step = -(mesa_h + gap_v)
            else:
                y = bbox.min_y + gap_v
                y_step =  (mesa_h + gap_v)

            while not done_gd:
                # Condición de parada en Y
                if fill_top_to_bottom:
                    if y < bbox.min_y + gap_v:
                        break
                else:
                    if y + mesa_h > bbox.max_y - gap_v:
                        break

                x = col_x_left + gap_h
                while x + mesa_w <= col_x_right - gap_h:
                    if panels_per_group > 0 and count_gd >= panels_per_group:
                        done_gd = True
                        break
                    if can_place_panel(x, y, mesa_w, mesa_h, boundary,
                                       poly_obstacles, circle_obstacles):
                        placements.append({"group": gd_idx + 1, "x": x, "y": y})
                        count_gd += 1
                    x += mesa_w + gap_h

                y += y_step

    else:
        # ── Modo filas: GDs apilados en Y, relleno de abajo hacia arriba ─────
        # Comportamiento original del LISP solar_array_layout_v1.15
        last_top_y = bbox.min_y

        for gd_idx in range(num_groups):
            y_base = (bbox.min_y + gap_v) if gd_idx == 0 else (last_top_y + group_sep)
            count_gd = 0
            y = y_base
            done = False

            while not done and (y + mesa_h) <= (bbox.max_y - gap_v):
                x = bbox.min_x + gap_h
                while not done and (x + mesa_w) <= (bbox.max_x - gap_h):
                    if panels_per_group > 0 and count_gd >= panels_per_group:
                        done = True
                        break
                    if can_place_panel(x, y, mesa_w, mesa_h, boundary,
                                       poly_obstacles, circle_obstacles):
                        placements.append({"group": gd_idx + 1, "x": x, "y": y})
                        count_gd += 1
                        if y + mesa_h > last_top_y:
                            last_top_y = y + mesa_h
                    x += mesa_w + gap_h
                y += mesa_h + gap_v

    return placements


def run_hybrid_layout(
    boundary: Polygon,
    panel_w: float,
    panel_h: float,
    gap_h: float = 0.5,
    gap_v: float = 2.5,
    num_groups: int = 1,
    panels_per_group: int = 0,
    poly_obstacles: list[Polygon] | None = None,
    circle_obstacles: list[tuple[float, float, float]] | None = None,
    group_sep: float = 6.0,
    panels_wide: int = 26,
    panels_high: int = 2,
    module_gap: float = 0.04,
    layout_mode: str = "rows",
    fill_top_to_bottom: bool = False,
    fallback_wide: int = 13,
    fallback_high: int = 2,
    target_panels: int = 0,
) -> dict:
    """
    Layout hibrido: llena primero con mesas primarias (panels_wide x panels_high),
    luego complementa en el espacio restante con mesas secundarias
    (fallback_wide x fallback_high) respetando las mismas separaciones.

    target_panels > 0 : calcula cuantas mesas secundarias se necesitan exactamente.
    target_panels = 0 : llena todo el espacio disponible con secundarias tambien.

    Retorna dict con:
      primary / fallback    : listas de {group, x, y}
      mesa_w/h_primary/fallback : dimensiones de cada tipo de mesa
      panels_primary / panels_fallback / total_panels
    """
    mesa_w_p, mesa_h_p = _mesa_dims(panels_wide, panels_high, panel_w, panel_h, module_gap)
    mesa_w_f, mesa_h_f = _mesa_dims(fallback_wide, fallback_high, panel_w, panel_h, module_gap)
    panels_per_p = panels_wide * panels_high
    panels_per_f = fallback_wide * fallback_high

    # Paso 1: layout primario
    primary = run_panel_layout(
        boundary=boundary,
        panel_w=panel_w, panel_h=panel_h,
        gap_h=gap_h, gap_v=gap_v,
        num_groups=num_groups,
        panels_per_group=panels_per_group,
        poly_obstacles=poly_obstacles,
        circle_obstacles=circle_obstacles,
        group_sep=group_sep,
        panels_wide=panels_wide, panels_high=panels_high,
        module_gap=module_gap,
        layout_mode=layout_mode,
        fill_top_to_bottom=fill_top_to_bottom,
    )

    panels_from_primary = len(primary) * panels_per_p

    # Paso 2: obstaculos = mesas primarias colocadas + externos originales
    obs_primary: list[Polygon] = [
        [Point(p["x"], p["y"]),
         Point(p["x"] + mesa_w_p, p["y"]),
         Point(p["x"] + mesa_w_p, p["y"] + mesa_h_p),
         Point(p["x"], p["y"] + mesa_h_p)]
        for p in primary
    ]
    all_poly_obs = list(poly_obstacles or []) + obs_primary

    # Limite de mesas secundarias
    if target_panels > 0:
        panels_needed = target_panels - panels_from_primary
        mesas_f_max = max(0, panels_needed // panels_per_f)
    else:
        mesas_f_max = 0  # 0 = llenar todo

    # Paso 3: layout secundario en espacio restante
    fallback: list[dict] = []
    if target_panels == 0 or mesas_f_max > 0:
        fallback = run_panel_layout(
            boundary=boundary,
            panel_w=panel_w, panel_h=panel_h,
            gap_h=gap_h, gap_v=gap_v,
            num_groups=num_groups,
            panels_per_group=mesas_f_max,
            poly_obstacles=all_poly_obs,
            circle_obstacles=circle_obstacles,
            group_sep=group_sep,
            panels_wide=fallback_wide, panels_high=fallback_high,
            module_gap=module_gap,
            layout_mode=layout_mode,
            fill_top_to_bottom=fill_top_to_bottom,
        )

    panels_fallback = len(fallback) * panels_per_f

    return {
        "primary":          primary,
        "fallback":         fallback,
        "mesa_w_primary":   round(mesa_w_p, 4),
        "mesa_h_primary":   round(mesa_h_p, 4),
        "mesa_w_fallback":  round(mesa_w_f, 4),
        "mesa_h_fallback":  round(mesa_h_f, 4),
        "panels_primary":   panels_from_primary,
        "panels_fallback":  panels_fallback,
        "total_panels":     panels_from_primary + panels_fallback,
    }


def parse_polygon_from_points(raw: list[tuple]) -> Polygon:
    """Convierte lista de tuplas (x, y) o (x, y, z) a Polygon."""
    return [Point(float(p[0]), float(p[1])) for p in raw]
