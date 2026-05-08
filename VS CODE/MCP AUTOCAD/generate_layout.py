"""
Layout Generator v3 - ENTRENAMIENTO PAUXI
Fixes:
  1. Poligono interior del cerramiento (el rojo)
  2. Centro correcto del bloque arbol (insert = esquina inf-izq)
  3. Elimina mesas con GAP horizontal (>1 columna de separacion del grupo mayor)
  4. 36 + 36 mesas en 2 GDs con separacion de grupo
"""
import sys, math
sys.path.insert(0, "server")
import ezdxf
from ezdxf import colors

DXF_IN  = r"c:\Users\JESSAN~1\DOCUME~1\VSCODE~1\MCPAUT~1\ENTREN~1.DXF"
DXF_OUT = r"c:\Users\JESSAN~1\DOCUME~1\VSCODE~1\MCPAUT~1\output\PAUXI_LAYOUT.DXF"

# ── Dimensiones ───────────────────────────────────────────────────────────────
PANEL_INS_OFF_X = -0.567; PANEL_INS_OFF_Y = -1.1515
PANELS_H = 26; PANELS_V = 2
STEP_X = 1.343; STEP_Y = 2.430; PANEL_W = 1.303; PANEL_H = 2.384
MESA_W = (PANELS_H - 1) * STEP_X + PANEL_W   # 34.878m
MESA_H = (PANELS_V - 1) * STEP_Y + PANEL_H   # 4.814m
COL_STEP = MESA_W + 0.5  # 35.378m entre columnas
ROW_STEP = MESA_H + 2.5  # 7.314m entre filas

# ── Arboles: bloque tiene insert en esquina INF-IZQ, no en el centro ──────────
TREE_BLK_W = 9.740; TREE_BLK_H = 9.414
TREE_OFF_X = TREE_BLK_W / 2.0   # 4.870m → para llegar al centro
TREE_OFF_Y = TREE_BLK_H / 2.0   # 4.707m
TREE_RADIUS = max(TREE_BLK_W, TREE_BLK_H) / 2.0 + 1.5   # 6.37m con buffer

MARGIN_LEFT = 8.0
NUM_GDS = 2; MESAS_POR_GD = 36; GROUP_SEP = 2.5
MIN_SEG_ALONE = 0   # 0 = incluir todo; el poligono tiene justo 73 posiciones para 72 mesas

print(f"Mesa: {MESA_W:.3f}m x {MESA_H:.3f}m  ({PANELS_H}x{PANELS_V} paneles)")
print(f"Arboles: radio {TREE_RADIUS:.2f}m, centro +({TREE_OFF_X:.2f},{TREE_OFF_Y:.2f}) del insert")

# ── Leer DXF ─────────────────────────────────────────────────────────────────
doc = ezdxf.readfile(DXF_IN)
msp = doc.modelspace()

# ── Poligono interior (_004 menor area) ──────────────────────────────────────
cer_polys = []
for e in msp:
    if e.dxftype() == "LWPOLYLINE" and "_004" in e.dxf.layer:
        pts = [(p[0], p[1]) for p in e.get_points()]
        area = abs(sum(pts[i][0]*pts[(i+1)%len(pts)][1]
                      - pts[(i+1)%len(pts)][0]*pts[i][1]
                      for i in range(len(pts)))) / 2
        cer_polys.append((area, pts))

inner_pts = min(cer_polys, key=lambda x: x[0])[1]
min_x_poly = min(p[0] for p in inner_pts)
# Aplicar margen izquierdo de 8m a los vertices del lado izq
effective = [(p[0] + MARGIN_LEFT, p[1]) if p[0] < min_x_poly + 30 else (p[0], p[1])
             for p in inner_pts]
print(f"\nPoligono interior con margen {MARGIN_LEFT}m izq -> {len(effective)} vertices")

# ── Arboles con centros corregidos ────────────────────────────────────────────
tree_circles = []
for e in doc.blocks["Topo Pauxi"]:
    if "ARBOL" in (e.dxf.layer if e.dxf.hasattr("layer") else "") and e.dxftype() == "INSERT":
        cx = e.dxf.insert.x + TREE_OFF_X
        cy = e.dxf.insert.y + TREE_OFF_Y
        tree_circles.append((cx, cy, TREE_RADIUS))
print(f"Arboles detectados: {len(tree_circles)}")

# ── Motor geometrico ──────────────────────────────────────────────────────────
from tools.geometry import can_place_panel, parse_polygon_from_points, circle_to_polygon, get_bbox
boundary_poly = parse_polygon_from_points(effective)
poly_obs = [circle_to_polygon(cx, cy, r, 24) for cx, cy, r in tree_circles]
bbox = get_bbox(boundary_poly)

# ── Escanear todas las posiciones validas ─────────────────────────────────────
print(f"\nEscaneando posiciones... BBox Y:{bbox.min_y:.2f}..{bbox.max_y:.2f}")
rows = {}   # y_idx → [(x_idx, x, y), ...]
y = bbox.min_y + 2.5
y_idx = 0
while (y + MESA_H) <= (bbox.max_y - 2.5):
    x = bbox.min_x + 0.5
    x_idx = 0
    row_positions = []
    while (x + MESA_W) <= (bbox.max_x - 0.5):
        if can_place_panel(x, y, MESA_W, MESA_H, boundary_poly, poly_obs, tree_circles):
            row_positions.append((x_idx, x, y))
        x += COL_STEP
        x_idx += 1
    rows[y_idx] = row_positions
    y += ROW_STEP
    y_idx += 1

# ── Detectar y eliminar mesas con GAP horizontal ─────────────────────────────
def find_segments(positions):
    """Agrupa por x_idx consecutivo."""
    if not positions:
        return []
    positions = sorted(positions, key=lambda p: p[0])
    segs = []; current = [positions[0]]
    for prev, curr in zip(positions, positions[1:]):
        if curr[0] - prev[0] == 1:
            current.append(curr)
        else:
            segs.append(current); current = [curr]
    segs.append(current)
    return segs

usable = {}   # y_idx → [(x, y), ...] solo posiciones validas
excluded_count = 0
for yi, row_pos in rows.items():
    segs = find_segments(row_pos)
    if not segs:
        usable[yi] = []
        continue
    # Segmento principal = el mas grande
    main_seg = max(segs, key=len)
    # Segmentos menores: excluir si tienen <= MIN_SEG_ALONE mesas (son aislados)
    kept = list(main_seg)
    for seg in segs:
        if seg is main_seg:
            continue
        if len(seg) > MIN_SEG_ALONE:
            kept.extend(seg)   # incluir segmentos grandes
            print(f"  Fila {yi} segmento adicional de {len(seg)} mesas -> INCLUIDO")
        else:
            excluded_count += len(seg)
            print(f"  Fila {yi} segmento de {len(seg)} mesas con GAP -> EXCLUIDO")
    usable[yi] = [(x, y) for (xi, x, y) in sorted(kept, key=lambda p: p[0])]

total_usable = sum(len(v) for v in usable.values())
print(f"\nResumen:")
print(f"  Total validas:    {sum(len(v) for v in rows.values())}")
print(f"  Excluidas (gap):  {excluded_count}")
print(f"  Usables finales:  {total_usable}")

# ── Asignar GDs ───────────────────────────────────────────────────────────────
# GD1 = filas inferiores hasta 36 mesas
# GD2 = filas superiores siguientes con separacion GROUP_SEP
gd1 = []; gd1_rows = set()
gd1_last_y_top = 0.0
for yi in sorted(usable.keys()):
    if len(gd1) >= MESAS_POR_GD:
        gd1_last_y_top = max(p["y"] + MESA_H for p in gd1)
        break
    for (x, y) in usable[yi]:
        if len(gd1) < MESAS_POR_GD:
            gd1.append({"group": 1, "x": x, "y": y, "y_idx": yi})
            gd1_rows.add(yi)

if not gd1_last_y_top and gd1:
    gd1_last_y_top = max(p["y"] + MESA_H for p in gd1)

gd2 = []
for yi in sorted(usable.keys()):
    if yi in gd1_rows:
        continue
    if len(gd2) >= MESAS_POR_GD:
        break
    # Respetar separacion GROUP_SEP
    if usable[yi] and usable[yi][0][1] < gd1_last_y_top + GROUP_SEP:
        continue
    for (x, y) in usable[yi]:
        if len(gd2) < MESAS_POR_GD:
            gd2.append({"group": 2, "x": x, "y": y, "y_idx": yi})

placements = gd1 + gd2

by_gd = {}
for p in placements:
    by_gd[p["group"]] = by_gd.get(p["group"], 0) + 1

print(f"\nLayout:")
for g, c in sorted(by_gd.items()):
    print(f"  GD{g}: {c} mesas ({PANELS_H*PANELS_V*c} paneles, {PANELS_H*PANELS_V*c*0.615:.1f} kWp)")
print(f"  Total: {len(placements)} mesas")

if by_gd.get(1, 0) < MESAS_POR_GD:
    print(f"  AVISO: GD1 tiene solo {by_gd.get(1,0)} mesas (pedidas {MESAS_POR_GD})")
if by_gd.get(2, 0) < MESAS_POR_GD:
    print(f"  AVISO: GD2 tiene solo {by_gd.get(2,0)} mesas (pedidas {MESAS_POR_GD})")

# ── Crear layers ──────────────────────────────────────────────────────────────
for name, col in [("GD1_MESAS", colors.YELLOW), ("GD2_MESAS", colors.CYAN), ("GD_LABELS", colors.WHITE)]:
    if name not in doc.layers:
        doc.layers.add(name, color=col)

# ── Insertar paneles ──────────────────────────────────────────────────────────
GD_LAYERS = {1: "GD1_MESAS", 2: "GD2_MESAS"}
total_panels = 0
print("\nInsertando bloques...")
for mesa in placements:
    gd = mesa["group"]
    layer = GD_LAYERS[gd]
    bx, by = mesa["x"], mesa["y"]
    for row in range(PANELS_V):
        for col in range(PANELS_H):
            ins_x = bx + (-PANEL_INS_OFF_X) + col * STEP_X
            ins_y = by + (-PANEL_INS_OFF_Y) + row * STEP_Y
            msp.add_blockref("PANEL_615", insert=(ins_x, ins_y, 0),
                             dxfattribs={"layer": layer,
                                         "xscale": 1.0, "yscale": 1.0, "zscale": 1.0,
                                         "rotation": 0.0})
            total_panels += 1

# Contornos de mesas (rectangulo exterior)
for mesa in placements:
    bx, by = mesa["x"], mesa["y"]
    msp.add_lwpolyline(
        [(bx,by),(bx+MESA_W,by),(bx+MESA_W,by+MESA_H),(bx,by+MESA_H),(bx,by)],
        dxfattribs={"layer": GD_LAYERS[mesa["group"]], "closed": True})

# Etiquetas
for mesa in placements:
    msp.add_text(f"GD{mesa['group']}",
                 dxfattribs={"layer": "GD_LABELS", "height": 1.5,
                             "insert": (mesa["x"]+MESA_W/2, mesa["y"]+MESA_H/2)})

# ── Guardar ───────────────────────────────────────────────────────────────────
import os; os.makedirs(os.path.dirname(DXF_OUT), exist_ok=True)
doc.saveas(DXF_OUT)
print(f"OK - DXF guardado: {DXF_OUT}")

# ── Resumen final ─────────────────────────────────────────────────────────────
print(f"\n{'='*54}")
print(f"RESUMEN PAUXI LAYOUT v3")
print(f"{'='*54}")
print(f"Poligono:  interior cerramiento proyectado (rojo)")
print(f"Margen izq: {MARGIN_LEFT}m")
print(f"Arboles:   {len(tree_circles)} con radio {TREE_RADIUS:.1f}m (centros corregidos)")
print(f"Mesa:      {MESA_W:.2f}m x {MESA_H:.2f}m | GapH:{0.5}m GapV:{2.5}m")
for g, c in sorted(by_gd.items()):
    kWp = c * PANELS_H * PANELS_V * 0.615
    print(f"GD{g}: {c} mesas  ->  {kWp:.0f} kWp")
print(f"Total: {total_panels} paneles  ->  {total_panels*0.615:.0f} kWp")
