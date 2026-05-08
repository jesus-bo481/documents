"""
Motor geométrico Python — migración directa desde solar_array_layout_v1.15.lsp
Funciones: sa-pip, sa-bbox, bloque-ok-v15, circle-to-poly, get-poly-pts
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
    Valida si un panel puede colocarse en (bx, by).
    bx, by = esquina inferior izquierda del panel.
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
            # esquinas del panel dentro del obstáculo
            if any(point_in_polygon(px, py, obs) for px, py in corners):
                return False
            # vértices del obstáculo dentro del panel
            if any(x1 < v.x < x2 and y1 < v.y < y2 for v in obs):
                return False

    # 3) Colisión con obstáculos circulares (verificación exacta)
    if circle_obstacles:
        for ccx, ccy, cr in circle_obstacles:
            if rect_intersects_circle(x1, y1, x2, y2, ccx, ccy, cr):
                return False

    return True


# ── Equivalente a: (defun solar-run-v15 ...) — motor de layout ───────────────
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
) -> list[dict]:
    """
    Calcula las posiciones de paneles dentro de un polígono límite.
    Devuelve lista de dicts con {group, x, y} — no dibuja en AutoCAD.
    panels_per_group=0 → llenar todo.
    """
    bbox = get_bbox(boundary)
    placements = []
    last_top_y = bbox.min_y

    for gd_idx in range(num_groups):
        y_base = (bbox.min_y + gap_v) if gd_idx == 0 else (last_top_y + group_sep)
        count_gd = 0
        y = y_base
        done = False

        while not done and (y + panel_h) <= (bbox.max_y - gap_v):
            x = bbox.min_x + gap_h
            while not done and (x + panel_w) <= (bbox.max_x - gap_h):
                if panels_per_group > 0 and count_gd >= panels_per_group:
                    done = True
                    break
                if can_place_panel(x, y, panel_w, panel_h, boundary,
                                   poly_obstacles, circle_obstacles):
                    placements.append({"group": gd_idx + 1, "x": x, "y": y})
                    count_gd += 1
                    if y + panel_h > last_top_y:
                        last_top_y = y + panel_h
                x += panel_w + gap_h
            y += panel_h + gap_v

    return placements


def parse_polygon_from_points(raw: list[tuple]) -> Polygon:
    """Convierte lista de tuplas (x, y) o (x, y, z) a Polygon."""
    return [Point(float(p[0]), float(p[1])) for p in raw]
