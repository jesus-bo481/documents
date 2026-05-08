"""
Diagnostico de capacidad real del poligono interior con arboles corregidos.
Muestra cuantas mesas caben por fila y por zona.
"""
import sys, math
sys.path.insert(0, "server")
import ezdxf
from tools.geometry import can_place_panel, parse_polygon_from_points, circle_to_polygon, get_bbox

DXF = r"c:\Users\JESSAN~1\DOCUME~1\VSCODE~1\MCPAUT~1\ENTREN~1.DXF"
doc = ezdxf.readfile(DXF)
msp = doc.modelspace()

MESA_W = 34.878; MESA_H = 4.814
GAP_H = 0.5;     GAP_V = 2.5
MARGIN_LEFT = 8.0
TREE_OFF_X = 4.870; TREE_OFF_Y = 4.707; TREE_RADIUS = 6.37

# Poligono interior
cer_polys = []
for e in msp:
    if e.dxftype() == "LWPOLYLINE" and "_004" in e.dxf.layer:
        pts = [(p[0],p[1]) for p in e.get_points()]
        area = abs(sum(pts[i][0]*pts[(i+1)%len(pts)][1]
                      -pts[(i+1)%len(pts)][0]*pts[i][1]
                      for i in range(len(pts))))/2
        cer_polys.append((area,pts))
inner_pts = min(cer_polys,key=lambda x:x[0])[1]

min_x_inner = min(p[0] for p in inner_pts)
effective = [(p[0]+MARGIN_LEFT,p[1]) if p[0]<min_x_inner+30
             else (p[0],p[1]) for p in inner_pts]

poly = parse_polygon_from_points(effective)
bbox = get_bbox(poly)

# Arboles corregidos
raw_trees = [(e.dxf.insert.x, e.dxf.insert.y)
             for e in doc.blocks["Topo Pauxi"]
             if "ARBOL" in (e.dxf.layer if e.dxf.hasattr("layer") else "")
             and e.dxftype()=="INSERT"]
tree_circles = [(ix+TREE_OFF_X, iy+TREE_OFF_Y, TREE_RADIUS) for ix,iy in raw_trees]
poly_obs = [circle_to_polygon(cx,cy,r,24) for cx,cy,r in tree_circles]

# Escanear fila por fila
print(f"{'Fila':>4} {'Y_base':>12} {'Mesas':>6}  Columnas X")
print("-"*70)

total = 0
rows_detail = []
y = bbox.min_y + GAP_V
y_idx = 0
while (y + MESA_H) <= (bbox.max_y - GAP_V):
    row_xs = []
    x = bbox.min_x + GAP_H
    while (x + MESA_W) <= (bbox.max_x - GAP_H):
        if can_place_panel(x, y, MESA_W, MESA_H, poly, poly_obs, tree_circles):
            row_xs.append(x)
        x += MESA_W + GAP_H
    n = len(row_xs)
    total += n
    rows_detail.append({"y_idx":y_idx,"y":y,"count":n,"xs":row_xs})
    x_str = " ".join(f"{x:.0f}" for x in row_xs) if n else "(ninguna)"
    flag = " <-- ARBOLES" if 0 < n < 3 else (" BLOQUEADA" if n==0 else "")
    print(f"{y_idx:>4} {y:>12.2f} {n:>6}  {x_str}{flag}")
    y += MESA_H + GAP_V
    y_idx += 1

print(f"\nTOTAL POSICIONES VALIDAS: {total}")
print(f"Max posible (2 GDs x 36): 72")
print(f"Deficit: {max(0, 72-total)}")

# Capacidad por zona
print("\n=== ZONAS ===")
zona_baja  = [r for r in rows_detail if r["y"] < 2467600]
zona_media = [r for r in rows_detail if 2467600 <= r["y"] < 2467645]
zona_alta  = [r for r in rows_detail if r["y"] >= 2467645]
print(f"Zona BAJA  (Y < 2467600):   {sum(r['count'] for r in zona_baja):>3} mesas en {len(zona_baja)} filas")
print(f"Zona MEDIA (2467600-2467645):{sum(r['count'] for r in zona_media):>3} mesas en {len(zona_media)} filas")
print(f"Zona ALTA  (Y > 2467645):   {sum(r['count'] for r in zona_alta):>3} mesas en {len(zona_alta)} filas")
