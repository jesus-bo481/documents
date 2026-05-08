import sys, math
sys.path.insert(0, "server")
import ezdxf

DXF = r"c:\Users\JESSAN~1\DOCUME~1\VSCODE~1\MCPAUT~1\ENTREN~1.DXF"
doc = ezdxf.readfile(DXF)
msp = doc.modelspace()

# ── 1. Geometria del bloque arbol (A$Ca8aa47d0) ──────────────────────────────
print("=== BLOQUE ARBOL (A$Ca8aa47d0) ===")
tree_block = None
for name in ["A$Ca8aa47d0", "A$CA8AA47D0"]:
    if name in doc.blocks:
        tree_block = doc.blocks[name]
        print(f"  Bloque encontrado: {name}")
        break

if tree_block:
    all_pts = []
    all_radii = []
    print(f"  Entidades ({len(list(tree_block))}):")
    for e in tree_block:
        t = e.dxftype()
        lay = e.dxf.layer if e.dxf.hasattr("layer") else "?"
        if t == "CIRCLE":
            cx, cy, r = e.dxf.center.x, e.dxf.center.y, e.dxf.radius
            print(f"    CIRCLE cen=({cx:.3f},{cy:.3f}) r={r:.3f} [{lay}]")
            all_radii.append(r + math.sqrt(cx**2 + cy**2))
            all_pts += [(cx-r, cy-r), (cx+r, cy+r)]
        elif t == "LWPOLYLINE":
            pts = [(p[0], p[1]) for p in e.get_points()]
            if pts:
                xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
                all_pts += [(min(xs),min(ys)),(max(xs),max(ys))]
                print(f"    LWPOLY {len(pts)}pts  X[{min(xs):.2f}..{max(xs):.2f}] Y[{min(ys):.2f}..{max(ys):.2f}] [{lay}]")
        elif t == "LINE":
            all_pts += [(e.dxf.start.x, e.dxf.start.y),(e.dxf.end.x, e.dxf.end.y)]
        elif t == "INSERT":
            print(f"    INSERT {e.dxf.name} en ({e.dxf.insert.x:.3f},{e.dxf.insert.y:.3f}) [{lay}]")
        elif t in ("ARC", "ELLIPSE", "SPLINE"):
            print(f"    {t} [{lay}]")
        else:
            print(f"    {t} [{lay}]")

    if all_pts:
        xs = [p[0] for p in all_pts]; ys = [p[1] for p in all_pts]
        print(f"\n  BBOX del bloque arbol:")
        print(f"    X: {min(xs):.3f} a {max(xs):.3f}  -> ancho={max(xs)-min(xs):.3f}")
        print(f"    Y: {min(ys):.3f} a {max(ys):.3f}  -> alto={max(ys)-min(ys):.3f}")
        radio_visual = max(max(xs)-min(xs), max(ys)-min(ys)) / 2
        print(f"  Radio visual estimado: {radio_visual:.3f}m")
else:
    print("  Bloque no encontrado, buscando similar...")
    for b in doc.blocks:
        if not b.name.startswith("*") and "A$C" in b.name.upper():
            print(f"  Candidato: {b.name}")

# ── 2. Todos los poligonos _004 ───────────────────────────────────────────────
print("\n=== POLIGONOS _004_Cerramiento_Proyectado ===")
cer_polys = []
for e in msp:
    if e.dxftype() == "LWPOLYLINE" and "_004" in e.dxf.layer:
        pts = [(p[0], p[1]) for p in e.get_points()]
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        area = 0
        for i in range(len(pts)-1):
            area += pts[i][0]*pts[i+1][1] - pts[i+1][0]*pts[i][1]
        area = abs(area)/2
        cer_polys.append({"pts": pts, "area": area, "xs": xs, "ys": ys})
        print(f"  Poligono {len(cer_polys)}: {len(pts)} vertices  area={area:.0f}m2")
        print(f"    X: {min(xs):.2f}..{max(xs):.2f}  Y: {min(ys):.2f}..{max(ys):.2f}")
        for i,p in enumerate(pts):
            print(f"    [{i}] ({p[0]:.2f}, {p[1]:.2f})")

if cer_polys:
    inner = min(cer_polys, key=lambda p: p["area"])
    print(f"\n  -> INTERIOR (menor area {inner['area']:.0f}m2):")
    for i,p in enumerate(inner["pts"]):
        print(f"     [{i}] ({p[0]:.2f}, {p[1]:.2f})")

# ── 3. TODOS los 12 arboles con sus posiciones exactas ───────────────────────
print("\n=== ARBOLES COMPLETOS EN Topo Pauxi ===")
if "Topo Pauxi" in doc.blocks:
    topo = doc.blocks["Topo Pauxi"]
    arboles = []
    for e in topo:
        lay = e.dxf.layer if e.dxf.hasattr("layer") else "?"
        if "ARBOL" in lay.upper() and e.dxftype() == "INSERT":
            arboles.append({
                "x": e.dxf.insert.x,
                "y": e.dxf.insert.y,
                "name": e.dxf.name
            })
    print(f"  Total arboles: {len(arboles)}")
    for i,a in enumerate(arboles):
        print(f"  [{i+1:2d}] INSERT {a['name']} en ({a['x']:.2f}, {a['y']:.2f})")

# ── 4. Verificar capa del _001 limite ─────────────────────────────────────────
print("\n=== LIMITE PREDIO (_001) ===")
for e in msp:
    if e.dxftype() == "LWPOLYLINE" and "_001" in e.dxf.layer:
        pts = [(p[0],p[1]) for p in e.get_points()]
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        area = 0
        for i in range(len(pts)-1):
            area += pts[i][0]*pts[i+1][1] - pts[i+1][0]*pts[i][1]
        area = abs(area)/2
        print(f"  {e.dxf.layer}  area={area:.0f}m2  X:{min(xs):.2f}..{max(xs):.2f}  Y:{min(ys):.2f}..{max(ys):.2f}")
