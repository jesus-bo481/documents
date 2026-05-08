"""
Tests unitarios del motor geométrico Python.
Verifica que la migración desde LISP sea correcta.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "server"))

from tools.geometry import (
    point_in_polygon, get_bbox, circle_to_polygon,
    can_place_panel, run_panel_layout, parse_polygon_from_points, Point
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def square(x0, y0, x1, y1):
    return [Point(x0, y0), Point(x1, y0), Point(x1, y1), Point(x0, y1)]


# ── Tests pip ─────────────────────────────────────────────────────────────────

def test_pip_inside():
    poly = square(0, 0, 10, 10)
    assert point_in_polygon(5, 5, poly)

def test_pip_outside():
    poly = square(0, 0, 10, 10)
    assert not point_in_polygon(15, 5, poly)

def test_pip_on_edge_approx():
    poly = square(0, 0, 10, 10)
    # Punto justo en el borde — comportamiento borde es indefinido, no debe crashear
    result = point_in_polygon(0, 5, poly)
    assert isinstance(result, bool)

def test_pip_triangle():
    triangle = [Point(0, 0), Point(10, 0), Point(5, 10)]
    assert point_in_polygon(5, 3, triangle)
    assert not point_in_polygon(0, 8, triangle)

# ── Tests bbox ────────────────────────────────────────────────────────────────

def test_bbox_square():
    poly = square(2, 3, 8, 9)
    bb = get_bbox(poly)
    assert bb.min_x == 2 and bb.min_y == 3
    assert bb.max_x == 8 and bb.max_y == 9

# ── Tests circle_to_polygon ───────────────────────────────────────────────────

def test_circle_to_polygon_count():
    pts = circle_to_polygon(0, 0, 5.0, 24)
    assert len(pts) == 24

def test_circle_to_polygon_radius():
    import math
    pts = circle_to_polygon(0, 0, 5.0, 24)
    for p in pts:
        dist = math.sqrt(p.x**2 + p.y**2)
        assert abs(dist - 5.0) < 0.001

# ── Tests can_place_panel ─────────────────────────────────────────────────────

def test_can_place_inside():
    boundary = square(0, 0, 20, 20)
    assert can_place_panel(1, 1, 2, 3, boundary)

def test_cannot_place_outside():
    boundary = square(0, 0, 10, 10)
    assert not can_place_panel(9, 9, 2, 3, boundary)

def test_cannot_place_obstacle():
    boundary = square(0, 0, 20, 20)
    obs = [square(5, 5, 8, 8)]
    assert not can_place_panel(4, 4, 4, 4, boundary, poly_obstacles=obs)

def test_cannot_place_circle_obstacle():
    boundary = square(0, 0, 20, 20)
    # círculo centrado en (10, 10) radio 3
    assert not can_place_panel(8, 8, 4, 4, boundary, circle_obstacles=[(10, 10, 3)])

# ── Tests run_panel_layout ────────────────────────────────────────────────────

def test_layout_basic():
    boundary = parse_polygon_from_points([[0,0],[30,0],[30,30],[0,30]])
    placements = run_panel_layout(boundary, 2.0, 3.0, 0.5, 2.5, 1, 0)
    assert len(placements) > 0
    for p in placements:
        assert p["group"] == 1
        assert "x" in p and "y" in p

def test_layout_panel_limit():
    boundary = parse_polygon_from_points([[0,0],[50,0],[50,50],[0,50]])
    placements = run_panel_layout(boundary, 2.0, 3.0, 0.5, 2.5, 1, 5)
    assert len(placements) == 5

def test_layout_multi_group():
    # panels_per_group > 0 para que cada GD deje espacio al siguiente
    boundary = parse_polygon_from_points([[0,0],[50,0],[50,100],[0,100]])
    placements = run_panel_layout(boundary, 2.0, 3.0, 0.5, 2.5, 3, 10)
    groups = set(p["group"] for p in placements)
    assert len(groups) > 1


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"OK  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed} pasados, {failed} fallados")
