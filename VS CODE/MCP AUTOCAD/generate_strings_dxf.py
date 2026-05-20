"""
generate_strings_dxf.py — Generador automático de strings DC
Dibuja conductores positivos (+) y negativos (-) como LWPOLYLINE conectadas.

Diseño global (todas las mesas):
  - Cada string = LWPOLYLINE de 3 puntos: (x_start, y) → (x_bajante_k, y) → (x_bajante_k, y_end)
  - x_start: borde del 2° panel desde el lado bajante (local a cada mesa)
  - x_bajante_k: DENTRO de la última mesa, a bajante_offset del borde + global_k*SEP
  - Las líneas se extienden en longitud completa desde su mesa hasta el bajante

Uso CLI:
  python generate_strings_dxf.py <source_dxf> [opciones]

Opciones:
  --bajante-side R|L      Lado del bajante (default: R)
  --bajante-dir  down|up  Dirección vertical del bajante (default: down)
  --bajante-depth <m>     Longitud vertical del bajante (default: 3.0)
  --bajante-offset <m>    Separación del 1er string al borde interior (default: 0.5)
  --strings-per-mesa <n>  Strings por mesa (0=auto, default: 0)
  --block-name <name>     Nombre del bloque de mesa (auto si se omite)
  --panel-block <name>    Bloque de panel individual (default: PANEL_615)
  --output -o <path>      Ruta de salida (default: <fuente>_strings.dxf)
"""
import math
import sys
from pathlib import Path
from collections import defaultdict

try:
    import ezdxf
except ImportError:
    print("ERROR: ezdxf no instalado. Ejecuta: pip install ezdxf")
    sys.exit(1)

# ─── Constantes ───────────────────────────────────────────────────────────────
MODULE_GAP    = 0.04   # separación entre módulos dentro de una mesa
SEP           = 0.01   # separación entre conductores adyacentes (m)
COLOR_RED     = 1      # rojo  — conductor + (positivo)
COLOR_CYAN    = 5      # cian  — conductor - (negativo)
LAYER_STRINGS  = "STRINGS_AUTO"
LAYER_LABELS   = "TEXTO"
LAYER_IXS      = "CONEXION"
TEXT_HEIGHT    = 0.3   # altura de texto MULTILEADER (m) — ISO-25
TEXT_HEIGHT_IXS = 0.4  # altura etiquetas IxSy
MLEADER_STYLE  = "ISO-25_AUTO"  # estilo MULTILEADER creado por este script


# ─── Utilidades de bloque ─────────────────────────────────────────────────────

def get_block_bbox(doc, block_name: str):
    """BBox del bloque relativo a su insert point. Devuelve (x0,y0,x1,y1) o None."""
    block = doc.blocks.get(block_name)
    if block is None:
        return None
    xs, ys = [], []
    for e in block:
        try:
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
        except Exception:
            pass
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def parse_mesa_block_name(name: str):
    """'NxM' → (N, M) enteros. Devuelve None si no coincide."""
    parts = name.lower().split("x")
    if len(parts) == 2:
        try:
            n, m = int(parts[0]), int(parts[1])
            if n >= 2 and m >= 1:
                return n, m
        except ValueError:
            pass
    return None


# ─── Detección de layout ──────────────────────────────────────────────────────

def detect_layout(doc):
    """
    Devuelve dict: {mode, block_name, strings_per_mesa, panel_block, panel_w, panel_h}
    mode = 'mesa_blocks' | 'individual_panels' | 'anon_array'

    'anon_array': el modelspace contiene bloques anonimos *U; cada uno es una
    mesa (array de paneles). La capa del INSERT define la agrupacion por string.
    """
    from collections import Counter
    msp = doc.modelspace()
    counter = Counter()
    for e in msp:
        if e.dxftype() == "INSERT" and not e.dxf.name.startswith("*"):
            counter[e.dxf.name] += 1

    # Modo 1: bloques de mesa nombrados (ej. "26x2")
    for name, cnt in counter.most_common():
        parsed = parse_mesa_block_name(name)
        if parsed and parsed[0] >= 4:
            print(f"  Bloque de mesa detectado: '{name}' ({cnt} insertos, {parsed[1]} strings/mesa)")
            return {"mode": "mesa_blocks", "block_name": name,
                    "strings_per_mesa": parsed[1],
                    "panel_block": None, "panel_w": None, "panel_h": None}

    # Modo 2: paneles individuales nombrados
    for name, cnt in counter.most_common():
        if name.startswith("*"):
            continue
        if cnt >= 2:
            print(f"  Layout de paneles individuales: '{name}' ({cnt} insertos)")
            return {"mode": "individual_panels", "block_name": name,
                    "strings_per_mesa": 2,
                    "panel_block": name, "panel_w": None, "panel_h": None}

    # Modo 3: array anonimo (*U en modelspace, cada uno = 1 mesa)
    u_inserts = [e for e in msp
                 if e.dxftype() == "INSERT" and e.dxf.name.startswith("*")]
    if len(u_inserts) >= 2:
        mesa_candidates = []
        panel_block     = None
        ref_positions   = None

        for e in u_inserts:
            blk = doc.blocks.get(e.dxf.name)
            if blk is None:
                continue
            sub_pos = [(s.dxf.insert.x, s.dxf.insert.y)
                       for s in blk if s.dxftype() == "INSERT"]
            if len(sub_pos) < 4:
                continue
            mesa_candidates.append(e)
            if panel_block is None:
                ref_positions = sub_pos
                sub_cnt  = Counter(s.dxf.name for s in blk if s.dxftype() == "INSERT")
                top_sub  = sub_cnt.most_common(1)[0][0]
                sub_blk  = doc.blocks.get(top_sub)
                if sub_blk:
                    inner = Counter(s.dxf.name for s in sub_blk if s.dxftype() == "INSERT")
                    panel_block = (inner.most_common(1)[0][0] if inner
                                   else (top_sub if not top_sub.startswith("*") else None))
                elif not top_sub.startswith("*"):
                    panel_block = top_sub

        if mesa_candidates and ref_positions:
            xs_s   = sorted({round(p[0], 3) for p in ref_positions})
            ys_s   = sorted({round(p[1], 3) for p in ref_positions})
            col_sp = (min(xs_s[i+1] - xs_s[i] for i in range(len(xs_s)-1))
                      if len(xs_s) > 1 else 1.3)
            row_sp = (ys_s[1] - ys_s[0] if len(ys_s) > 1 else col_sp * 2)
            n_str  = len(ys_s)
            print(
                f"  Array anonimo detectado: {len(mesa_candidates)} mesas, "
                f"panel='{panel_block}', {len(xs_s)} col x {n_str} fil, "
                f"col_sep={col_sp:.3f}m row_sep={row_sp:.3f}m"
            )
            return {"mode": "anon_array", "block_name": None,
                    "strings_per_mesa": n_str,
                    "panel_block": panel_block,
                    "panel_w": col_sp, "panel_h": row_sp}

    raise ValueError("No se detecto ningun bloque valido en el DXF.")


# ─── Recolección de mesas ─────────────────────────────────────────────────────

SKIP_LAYERS = {"0"}


def collect_mesas(doc, block_name: str, mode: str,
                  panel_rows_per_mesa: int = 2,
                  skip_layers: set = None,
                  panel_w: float = None,
                  panel_h: float = None) -> list:
    """
    Recolecta bboxes de todas las mesas.
    Devuelve lista de dicts: {x_left, y_bottom, x_right, y_top, layer}
    Modos: 'mesa_blocks' | 'individual_panels' | 'anon_array'
    """
    if skip_layers is None:
        skip_layers = SKIP_LAYERS

    msp = doc.modelspace()

    # anon_array: cada *U INSERT = 1 mesa; bbox desde posiciones sub-inserts
    if mode == "anon_array":
        _pw = panel_w or 1.3
        _ph = panel_h or (_pw * 2)
        mesas = []
        for e in msp:
            if e.dxftype() != "INSERT" or not e.dxf.name.startswith("*"):
                continue
            if e.dxf.layer in skip_layers:
                continue
            blk = doc.blocks.get(e.dxf.name)
            if blk is None:
                continue
            sub_pos = [(s.dxf.insert.x, s.dxf.insert.y)
                       for s in blk if s.dxftype() == "INSERT"]
            if len(sub_pos) < 4:
                continue
            rel_xs = [p[0] for p in sub_pos]
            rel_ys = [p[1] for p in sub_pos]
            ix, iy = e.dxf.insert.x, e.dxf.insert.y
            mesas.append({
                "x_left":   ix + min(rel_xs),
                "y_bottom": iy + min(rel_ys),
                "x_right":  ix + max(rel_xs) + _pw,
                "y_top":    iy + max(rel_ys) + _ph,
                "layer":    e.dxf.layer,
            })
        return mesas

    # Modos con bloque nombrado: Si TODOS los paneles están en capas filtradas
    # (ej. DXF manual con layer '0'), no filtrar — evita perder todos los paneles.
    _panel_layers = {e.dxf.layer for e in msp
                     if e.dxftype() == "INSERT" and e.dxf.name == block_name}
    if _panel_layers and _panel_layers.issubset(skip_layers):
        skip_layers = set()

    bbox = get_block_bbox(doc, block_name)
    if bbox is None:
        raise ValueError(f"No se pudo medir el bloque '{block_name}'")
    bx0, by0, bx1, by1 = bbox
    pw = bx1 - bx0
    ph = by1 - by0

    if mode == "mesa_blocks":
        mesas = []
        for e in msp:
            if e.dxftype() != "INSERT" or e.dxf.name != block_name:
                continue
            if e.dxf.layer in skip_layers:
                continue
            ix, iy = e.dxf.insert.x, e.dxf.insert.y
            mesas.append({
                "x_left":   ix + bx0,
                "y_bottom": iy + by0,
                "x_right":  ix + bx1,
                "y_top":    iy + by1,
                "layer":    e.dxf.layer,
            })
        return mesas

    else:
        panels = []
        for e in msp:
            if e.dxftype() != "INSERT" or e.dxf.name != block_name:
                continue
            if e.dxf.layer in skip_layers:
                continue
            panels.append({
                "x": e.dxf.insert.x + bx0,
                "y": e.dxf.insert.y + by0,
                "layer": e.dxf.layer,
            })

        if not panels:
            return []

        panels.sort(key=lambda p: p["y"])
        y_tol = 0.02
        y_rows = []
        cur = [panels[0]]
        for p in panels[1:]:
            if abs(p["y"] - cur[0]["y"]) <= y_tol:
                cur.append(p)
            else:
                y_rows.append(cur)
                cur = [p]
        y_rows.append(cur)

        mesas = []
        for i in range(0, len(y_rows), panel_rows_per_mesa):
            batch = y_rows[i: i + panel_rows_per_mesa]
            all_panels = [p for row in batch for p in row]
            _raw_layer = next(iter({p["layer"] for p in all_panels}), "GD1")
            mesa_layer = "GD1" if _raw_layer == "0" else _raw_layer

            gap_threshold = pw + 0.3
            all_panels.sort(key=lambda p: p["x"])
            x_groups = []
            cur_grp = [all_panels[0]]
            for p in all_panels[1:]:
                if p["x"] - cur_grp[-1]["x"] > gap_threshold:
                    x_groups.append(cur_grp)
                    cur_grp = [p]
                else:
                    cur_grp.append(p)
            x_groups.append(cur_grp)

            for grp in x_groups:
                xs = [p["x"] for p in grp]
                ys_in_batch = []
                for row in batch:
                    for p in row:
                        if any(abs(p["x"] - gx) <= gap_threshold for gx in xs):
                            ys_in_batch.append(p["y"])
                ys_for_bbox = [p["y"] for p in grp] + ys_in_batch

                mesas.append({
                    "x_left":   min(xs),
                    "y_bottom": min(ys_for_bbox),
                    "x_right":  max(xs) + pw,
                    "y_top":    max(ys_for_bbox) + ph,
                    "layer":    mesa_layer,
                })

        return mesas


# ─── Agrupación ───────────────────────────────────────────────────────────────

def group_by_gd(mesas: list) -> dict:
    groups = defaultdict(list)
    for m in mesas:
        groups[m["layer"]].append(m)
    return dict(groups)


def group_by_row(mesas: list) -> list:
    if not mesas:
        return []
    avg_h = sum(m["y_top"] - m["y_bottom"] for m in mesas) / len(mesas)
    tol = avg_h / 2.0

    def y_c(m):
        return (m["y_bottom"] + m["y_top"]) / 2.0

    sorted_m = sorted(mesas, key=y_c)
    rows, cur = [], [sorted_m[0]]
    cur_yc = y_c(sorted_m[0])
    for m in sorted_m[1:]:
        yc = y_c(m)
        if abs(yc - cur_yc) <= tol:
            cur.append(m)
        else:
            rows.append(sorted(cur, key=lambda m: m["x_left"]))
            cur = [m]
            cur_yc = yc
    rows.append(sorted(cur, key=lambda m: m["x_left"]))
    return rows


# ─── Dibujo ───────────────────────────────────────────────────────────────────

def ensure_layer(doc, name: str, color: int = 7):
    if name not in doc.layers:
        doc.layers.new(name, dxfattribs={"color": color})


def _get_mleader_style(doc) -> str:
    """
    Prefiere 'Standard' (no-anotativo). El DXF fuente trae Standard y Annotative;
    'Annotative' aplica escala anotativa que rompe el render de las MULTILEADER.
    """
    try:
        names = [n for n, _ in doc.mleader_styles]
        if "Standard" in names:
            return "Standard"
        return names[0] if names else "Standard"
    except Exception:
        return "Standard"


def ensure_mleader_style(doc) -> str:
    """
    Modifica EN SITIO el estilo MLEADER 'Standard' del DXF de salida para que
    tenga valores correctos en metros (arrow=0.3, dogleg=0.2, char=0.3, ROMANS)
    en lugar de los defaults heredados (arrow=4 m, dogleg=8 m, char=4 m) que
    hacen que las MULTILEADER salgan invisibles en AutoCAD.

    Tambien asegura que el bloque de flecha 'closed_filled' este definido en
    el DXF — sin esto, AutoCAD dibuja un patron extrano (tipo peine) en lugar
    de la punta de flecha triangular.

    Se modifica Standard (no Annotative) porque Standard es no-anotativo, y se
    modifica en sitio porque ezdxf no soporta crear MLEADER styles nuevos de
    forma confiable. El DXF fuente no contiene MULTILEADERs, asi que sobre-
    escribir Standard no afecta nada del input.
    """
    # 1) Asegurar bloque de flecha _CLOSEDFILLED en el doc. ARROWS.closed_filled
    # es "" (default) y ezdxf crea el bloque '_CLOSEDFILLED' al llamar create_block.
    arrow_handle = None
    arrow_block_name = "_CLOSEDFILLED"
    try:
        from ezdxf.render.arrows import ARROWS
        if arrow_block_name not in doc.blocks:
            ARROWS.create_block(doc.blocks, ARROWS.closed_filled)
        if arrow_block_name in doc.blocks:
            arrow_block = doc.blocks.get(arrow_block_name)
            arrow_handle = arrow_block.block_record_handle
    except Exception as _arr_err:
        print(f"  AVISO: no se pudo crear bloque de flecha: {_arr_err!r}")

    # 2) Modificar estilo MLEADER 'Standard'
    try:
        style = doc.mleader_styles.get("Standard")
    except Exception:
        try:
            for _n, _s in doc.mleader_styles:
                style = _s
                break
            else:
                return "Standard"
        except Exception:
            return "Standard"

    romans_handle = None
    if "ROMANS" in [s.dxf.name for s in doc.styles]:
        romans_handle = doc.styles.get("ROMANS").dxf.handle

    attribs = {
        "arrow_head_size":  TEXT_HEIGHT,   # 0.3 m
        "dogleg_length":    0.2,           # m
        "scale":            1.0,
        "char_height":      TEXT_HEIGHT,   # 0.3 m
        "has_landing":      1,
        "has_dogleg":       1,
        "is_annotative":    0,             # critico para render correcto
    }
    if romans_handle:
        attribs["text_style_handle"] = romans_handle
    if arrow_handle:
        attribs["arrow_head_handle"] = arrow_handle

    for k, v in attribs.items():
        try:
            setattr(style.dxf, k, v)
        except Exception:
            pass

    return "Standard"


def _draw_multileader(msp, doc, content: str,
                      x_arrow: float, y_arrow: float,
                      x_elbow: float, y_elbow: float,
                      char_height: float = TEXT_HEIGHT,
                      text_left: bool = False):
    """
    Dibuja MULTILEADER con leader en L (layer TEXTO).

    Leader path:
      flecha (x_arrow, y_arrow)  →  codo (x_elbow, y_elbow)  →  texto
    text_left=False → texto a la IZQUIERDA del codo  (bajante R, igual que referencia)
    text_left=True  → texto a la DERECHA del codo    (bajante L)

    Geometría fijada manualmente después de build() para evitar que el
    dogleg_length del estilo del documento (8 m en "Standard") desplace
    last_leader_point muy lejos y genere una línea horizontal gigante.
    Referencia:  dx(insert − llp) = −0.5806,  dy = +0.25
    """
    INSERT_DX  = 0.58   # distancia horizontal texto ↔ elbow
    INSERT_DY  = 0.25   # offset vertical mtext.insert ↔ last_leader_point
    style_name = _get_mleader_style(doc)

    try:
        from ezdxf.render.mleader import TextAlignment, ConnectionSide
        from ezdxf.render.arrows import ARROWS
        from ezdxf.math import Vec2, Vec3

        # ConnectionSide determina a qué borde del texto conecta el dogleg:
        #   .right → borde DERECHO del texto (texto queda a la IZQUIERDA del leader)
        #   .left  → borde IZQUIERDO del texto (texto queda a la DERECHA del leader)
        conn_side = ConnectionSide.left if text_left else ConnectionSide.right

        builder = msp.add_multileader_mtext(style_name)
        builder.set_content(content, char_height=char_height, alignment=TextAlignment.left)
        # Flecha rellena cerrada (closed_filled) — agrega bloque al doc si no existe
        try:
            builder.set_arrow_properties(name=ARROWS.closed_filled, size=char_height)
        except Exception:
            pass
        builder.add_leader_line(
            conn_side,
            [Vec2(x_arrow, y_arrow), Vec2(x_elbow, y_elbow)],
        )
        # dummy insert — la geometría real se sobreescribe justo después
        builder.build(insert=Vec2(x_elbow - 0.5, y_elbow))

        ml  = builder.multileader
        ml.dxf.layer = LAYER_LABELS
        ml.dxf.color = 0          # ByBlock — igual que referencia
        # Override defaults a nivel de entidad — necesarios porque heredamos
        # estilos del DXF fuente con arrow=4m, dogleg=8m, anotativos.
        ml.dxf.arrow_head_size = char_height  # 0.3 m
        ml.dxf.dogleg_length   = 0.2          # m
        ml.dxf.scale           = 1.0
        ml.dxf.is_annotative   = 0            # no anotativo (clave para render)
        romans = doc.styles.get("ROMANS")
        if romans:
            ml.dxf.text_style_handle = romans.dxf.handle
        # Bloque de flecha _CLOSEDFILLED — ensure_mleader_style ya lo creo
        if "_CLOSEDFILLED" in doc.blocks:
            _arrow_blk = doc.blocks.get("_CLOSEDFILLED")
            try:
                ml.dxf.arrow_head_handle = _arrow_blk.block_record_handle
            except Exception:
                pass
        ctx = ml.context

        # Fijar geometría exacta independientemente del dogleg_length del estilo.
        # Referencia:  last_leader_point == elbow  |  dx(insert-llp) = -0.5806  dy = +0.25
        # ctx.mtext.alignment (código 171 en contexto) controla QUÉ esquina del texto
        # es el punto de inserción:  3 = top-right → texto crece a la IZQUIERDA
        #                            1 = top-left  → texto crece a la DERECHA
        ctx.leaders[0].last_leader_point = Vec3(x_elbow, y_elbow, 0)
        # dogleg_length del contexto (por líder) controla el largo de la línea horizontal.
        # El builder hereda 8 m del estilo Standard; lo reducimos al valor de referencia:
        # INSERT_DX - landing_gap  =  0.58 - 0.01875  ≈  0.5618  (igual que ISO-25)
        LANDING_GAP = 0.01875
        ctx.leaders[0].dogleg_length = INSERT_DX - LANDING_GAP
        ctx.mtext.flow_direction = 5   # igual que referencia
        # Espaciado entre líneas más apretado — igual que referencia (0.7083)
        # Sin esto, las 4 líneas del texto ocupan ~2 m y se traslapan con IxSy.
        ctx.mtext.line_spacing_factor = 0.7083
        # Dimensiones de caja MText — la referencia las setea para que AutoCAD
        # renderice bien (con 0 puede quedar invisible o sin bounding box).
        ctx.mtext.width = 12.0
        ctx.mtext.defined_height = char_height * 4.1  # ≈ 1.23 m para 4 líneas
        # Estilo ROMANS (SHX) en el mtext del contexto — igual que referencia
        romans_style = doc.styles.get("ROMANS")
        if romans_style:
            ctx.mtext.style_handle = romans_style.dxf.handle
        if text_left:   # texto a la DERECHA (bajante L)
            ctx.mtext.insert    = Vec3(x_elbow + INSERT_DX, y_elbow + INSERT_DY, 0)
            ctx.mtext.alignment = 1   # top-left: el texto crece hacia la DERECHA desde insert
            try: ml.dxf.set("text_attachment_point", 1)
            except Exception: pass
        else:           # texto a la IZQUIERDA (bajante R, igual que referencia)
            ctx.mtext.insert    = Vec3(x_elbow - INSERT_DX, y_elbow + INSERT_DY, 0)
            ctx.mtext.alignment = 3   # top-right: el texto crece hacia la IZQUIERDA desde insert
            try: ml.dxf.set("text_attachment_point", 3)
            except Exception: pass

    except Exception as _ml_err:
        print(f"  WARN MULTILEADER: {_ml_err!r} — usando fallback MTEXT+LINE")
        text_x = x_elbow + (INSERT_DX if text_left else -INSERT_DX)
        fb = content.replace("\\A1;", "").replace("\\P", "\n")
        msp.add_mtext(fb, dxfattribs={
            "layer":            LAYER_LABELS,
            "style":            "ROMANS",
            "char_height":      char_height,
            "insert":           (text_x, y_elbow, 0),
            "attachment_point": 1 if text_left else 3,
        })
        msp.add_line(
            (x_arrow, y_arrow), (x_elbow, y_elbow),
            dxfattribs={"layer": LAYER_LABELS, "color": 3},
        )
        msp.add_line(
            (x_elbow, y_elbow), (text_x, y_elbow),
            dxfattribs={"layer": LAYER_LABELS, "color": 3},
        )


def draw_strings_row(msp, row: list, bajante_side: str, bajante_dir: str,
                     bajante_depth: float, bajante_offset: float,
                     strings_per_mesa: int,
                     pw: float, module_gap: float,
                     doc=None):
    """
    Dibuja strings DC para una fila de mesas.

    Diseño global:
    - Cada string = LWPOLYLINE de 3 puntos: x_start(mesa) → x_bajante_k → y_end
    - Todas las mesas usan el mismo diseño; las líneas se extienden hasta el bajante
    - x_bajante_k está DENTRO de la última mesa (bajante_offset desde el borde)
    - global_k asigna a cada string una x única en la columna del bajante
    - y_line varía con global_k → el haz de conductores se escalona verticalmente

    Etiquetas MULTILEADER en cada espacio inter-mesa (indicador de sección).
    """
    n_mesas        = len(row)
    lines_per_mesa = strings_per_mesa * 2   # conductor + y - por string

    y_bottom_all = min(m["y_bottom"] for m in row)
    y_top_all    = max(m["y_top"]    for m in row)
    y_center     = (y_bottom_all + y_top_all) / 2.0

    # Y de las líneas: distribuidas alrededor del centro, total = n_mesas * lines_per_mesa
    total_lines = n_mesas * lines_per_mesa
    alt_total   = (total_lines - 1) * SEP
    y_inicio    = y_center + alt_total / 2.0

    if bajante_dir == "down":
        y_end = y_bottom_all - bajante_depth
    else:
        y_end = y_top_all + bajante_depth

    # Ordenar de más lejana a más cercana al bajante
    if bajante_side == "R":
        ordered = row                  # [0]=izquierda (lejana), [-1]=derecha (bajante)
        x_edge  = row[-1]["x_right"]   # borde derecho de la última mesa
    else:
        ordered = list(reversed(row))  # [0]=derecha (lejana), [-1]=izquierda (bajante)
        x_edge  = row[0]["x_left"]     # borde izquierdo de la última mesa

    # Altura de las etiquetas: subido para que el texto MULTILEADER no se traslape
    # con las etiquetas IxSy que viven dentro de los paneles. La línea indicativa
    # se estira automáticamente desde el arrow (en el conductor) hasta este elbow.
    y_label = y_top_all + TEXT_HEIGHT * 5  # ≈ 1.5 m por encima del borde superior

    global_k = 0
    for mesa_idx, mesa in enumerate(ordered):
        for local_k in range(lines_per_mesa):
            y_line = y_inicio - global_k * SEP
            color  = COLOR_RED if (local_k % 2 == 0) else COLOR_CYAN

            # x_start: borde exterior del 2° panel desde el lado bajante (en esta mesa)
            if bajante_side == "R":
                x_start = mesa["x_right"] - 2 * pw - module_gap
            else:
                x_start = mesa["x_left"] + 2 * pw + module_gap

            # x_bajante: posición única DENTRO de la última mesa
            # global_k=0 → más cercano al borde exterior; crece hacia el interior
            if bajante_side == "R":
                x_bajante_k = x_edge - bajante_offset - global_k * SEP
            else:
                x_bajante_k = x_edge + bajante_offset + global_k * SEP

            pts = [
                (x_start,     y_line),
                (x_bajante_k, y_line),
                (x_bajante_k, y_end),
            ]
            msp.add_lwpolyline(pts, dxfattribs={
                "layer": LAYER_STRINGS,
                "color": color,
            })
            global_k += 1

        # ── Etiqueta MULTILEADER en el espacio entre mesas ─────────────────
        if mesa_idx < n_mesas - 1:
            n_cond  = (mesa_idx + 1) * strings_per_mesa   # conductores por polaridad
            n_tubes = math.ceil(n_cond / 6)

            next_mesa = ordered[mesa_idx + 1]

            # X del gap entre esta mesa y la siguiente
            if bajante_side == "R":
                x_jct = (mesa["x_right"] + next_mesa["x_left"]) / 2.0
            else:
                x_jct = (mesa["x_left"] + next_mesa["x_right"]) / 2.0

            # Y del arrow: centro del haz total de conductores
            y_jct = y_inicio - (total_lines - 1) / 2.0 * SEP

            # Formato idéntico al DXF de referencia (espacio antes de (-))
            content = (
                f"\\A1;Tubo Interflex\\P"
                f"{n_tubes} x %%C2\"\\P"
                f"{n_cond}x6mm2(+) + {n_cond}x6mm2 (-)\\P "
            )

            # Leader en L: flecha en el gap → codo a y_label → texto a la izquierda
            _draw_multileader(
                msp, doc,
                content,
                x_arrow=x_jct, y_arrow=y_jct,
                x_elbow=x_jct, y_elbow=y_label,
            )

    # ── Nota de bajante al extremo del bajante ─────────────────────────────
    n_cond_total  = n_mesas * strings_per_mesa
    n_tubes_total = math.ceil(n_cond_total / 6)
    bajante_content = (
        f"\\A1;Bajante en \\P"
        f"Tubo Interflex {n_tubes_total} x %%C2\" \\P"
        f"{n_cond_total}x6mm2(+) + {n_cond_total}x6mm2 (-)"
    )
    # Flecha apunta al inicio de las líneas verticales (el extremo bajante)
    y_arrow_baj = y_inicio - (total_lines - 1) / 2.0 * SEP
    if bajante_side == "R":
        x_arrow_baj = x_edge
        x_elbow_baj = x_edge
    else:
        x_arrow_baj = x_edge
        x_elbow_baj = x_edge
    _draw_multileader(
        msp, doc,
        bajante_content,
        x_arrow=x_arrow_baj, y_arrow=y_arrow_baj,
        x_elbow=x_elbow_baj, y_elbow=y_label,
    )


# ─── Etiquetas IxSy ──────────────────────────────────────────────────────────

def draw_string_labels(
    msp,
    all_rows:          list,
    bajante_side:      str,
    start_from:        str,
    num_inversores:    int,
    strings_per_inv:   int,
    strings_per_mesa:  int,
    panel_ph:          float = 2.384,
):
    """
    Coloca MTEXT etiquetas IxSy (layer CONEXION, style ROMANS, h=0.4) en el
    borde bajante de cada mesa.

    Orden de asignación:
      start_from='top'    → filas de arriba hacia abajo
      start_from='bottom' → filas de abajo hacia arriba
      bajante_side='R'    → dentro de cada fila, mesas de derecha a izquierda
      bajante_side='L'    → dentro de cada fila, mesas de izquierda a derecha
      Dentro de cada mesa: string 0 (extremo más cercano al borde de inicio)
      hasta strings_per_mesa-1.
    """
    # Ordenar filas
    rows_sorted = sorted(all_rows, key=lambda r: sum(m["y_top"] for m in r) / len(r),
                         reverse=(start_from == "top"))

    global_str = 0
    total_strings = num_inversores * strings_per_inv

    for row in rows_sorted:
        # Ordenar mesas dentro de la fila: más cercana al bajante primero
        if bajante_side == "R":
            mesas_ordered = sorted(row, key=lambda m: m["x_left"], reverse=True)
        else:
            mesas_ordered = sorted(row, key=lambda m: m["x_left"])

        for mesa in mesas_ordered:
            mesa_h = mesa["y_top"] - mesa["y_bottom"]
            for k in range(strings_per_mesa):
                if global_str >= total_strings:
                    break

                inv_num = global_str // strings_per_inv + 1
                str_num = global_str % strings_per_inv + 1
                tag = f"I{inv_num}S{str_num}"

                # Y: texto (attachment_point=1, top-left) con text_top a 0.346 m bajo
                # el borde superior de cada panel — coincide con referencia v6_final2.
                # Dentro de la mesa: k=0 → panel SUPERIOR; k=strings_per_mesa-1 → INFERIOR.
                # start_from solo afecta el orden global de asignación de mesas, no la
                # posición dentro de la mesa.
                TEXT_VOFFSET = 0.346
                if strings_per_mesa == 1:
                    y_lbl = (mesa["y_top"] + mesa["y_bottom"]) / 2.0
                else:
                    row_spacing = (mesa_h - panel_ph) / (strings_per_mesa - 1)
                    y_lbl = mesa["y_top"] - TEXT_VOFFSET - k * row_spacing

                # X: borde bajante de la mesa, ligeramente dentro
                LABEL_INSET = 1.0  # m desde el borde
                if bajante_side == "R":
                    x_lbl = mesa["x_right"] - LABEL_INSET
                else:
                    x_lbl = mesa["x_left"] + LABEL_INSET

                msp.add_mtext(
                    f"\\pxt10;{tag}",
                    dxfattribs={
                        "layer":              LAYER_IXS,
                        "color":              7,
                        "char_height":        TEXT_HEIGHT_IXS,
                        "style":              "ROMANS",
                        "insert":             (x_lbl, y_lbl, 0),
                        "attachment_point":   1,
                        "width":              0.49,
                        "bg_fill":            1,
                        "bg_fill_color":      7,
                        "box_fill_scale":     1.5,
                        "bg_fill_true_color": 16772607,  # 0xFFEFFF — igual que referencia
                    },
                )
                global_str += 1

            if global_str >= total_strings:
                break
        if global_str >= total_strings:
            break


# ─── Función principal ────────────────────────────────────────────────────────

def run_generate_strings(
    source_dxf:        str,
    output_dxf:        str   = None,
    bajante_side:      str   = "R",
    bajante_dir:       str   = "down",
    bajante_depth:     float = 3.0,
    bajante_offset:    float = 0.05,
    strings_per_mesa:  int   = 0,
    block_name:        str   = None,
    panel_block:       str   = "PANEL_615",
    num_inversores:    int   = 0,
    strings_per_inv:   int   = 0,
    start_from:        str   = "top",
) -> str:
    """
    Lee el DXF fuente, dibuja los strings DC y guarda el resultado.
    Devuelve la ruta del DXF generado.
    """
    print(f"\n=== STRINGS DC — {Path(source_dxf).name} ===")
    print(f"  Bajante: lado={bajante_side}, dir={bajante_dir}, "
          f"depth={bajante_depth}m, offset_1er_string={bajante_offset}m")

    doc = ezdxf.readfile(source_dxf)
    msp = doc.modelspace()

    # Garantizar estilo ROMANS (SHX) para que AutoCAD no muestre cuadros
    if "ROMANS" not in [s.dxf.name for s in doc.styles]:
        doc.styles.new("ROMANS", dxfattribs={"font": "romans.shx"})

    # Garantizar estilo MLEADER no-anotativo con valores en metros
    ensure_mleader_style(doc)

    # 1. Detectar layout
    if block_name:
        parsed = parse_mesa_block_name(block_name)
        info = {
            "mode": "mesa_blocks",
            "block_name": block_name,
            "strings_per_mesa": parsed[1] if parsed else 2,
        }
    else:
        info = detect_layout(doc)
        if info["mode"] == "individual_panels" and panel_block:
            info["block_name"] = panel_block

    n_str = strings_per_mesa if strings_per_mesa > 0 else info["strings_per_mesa"]
    print(f"  Modo: {info['mode']}  |  Bloque: {info['block_name']}  |  Strings/mesa: {n_str}")

    # 2. Ancho del panel individual (para cálculo de x_start en draw_strings_row)
    if info["mode"] == "anon_array":
        panel_w  = info["panel_w"] or 1.3
        _mod_gap = 0.0    # col_spacing ya incluye el hueco entre paneles
        print(f"  Ancho panel (col_spacing): {panel_w:.4f} m | SEP conductores: {SEP} m")
    else:
        bbox_data = get_block_bbox(doc, info["block_name"])
        if bbox_data is None:
            raise ValueError(f"No se encontro la definicion del bloque '{info['block_name']}'")
        bx0, by0, bx1, by1 = bbox_data
        block_w = bx1 - bx0
        if info["mode"] == "mesa_blocks":
            parsed = parse_mesa_block_name(info["block_name"])
            panel_w = ((block_w - (parsed[0] - 1) * MODULE_GAP) / parsed[0]
                       if parsed else block_w)
        else:
            panel_w = block_w
        _mod_gap = MODULE_GAP
        print(f"  Ancho panel individual: {panel_w:.4f} m | SEP conductores: {SEP} m")

    # 3. Recolectar mesas
    mesas = collect_mesas(
        doc, info["block_name"], info["mode"],
        panel_rows_per_mesa=n_str,
        skip_layers={"0"},
        panel_w=info.get("panel_w"),
        panel_h=info.get("panel_h"),
    )
    print(f"  Mesas detectadas: {len(mesas)}")
    if not mesas:
        raise ValueError("No se encontraron mesas en el DXF.")

    # 3b. Dibujar contorno (LWPOLYLINE) y etiqueta (TEXT) de cada mesa
    for m in mesas:
        ml = m["layer"]
        ensure_layer(doc, ml, color=7)
        xl, xr = m["x_left"], m["x_right"]
        yb, yt = m["y_bottom"], m["y_top"]
        msp.add_lwpolyline(
            [(xl, yb), (xr, yb), (xr, yt), (xl, yt), (xl, yb)],
            dxfattribs={"layer": ml, "closed": True},
        )
        cx = (xl + xr) / 2.0
        cy = (yb + yt) / 2.0
        msp.add_text(
            ml,
            dxfattribs={
                "layer":       ml,
                "height":      1.5,
                "insert":      (cx, cy, 0),
                "halign":      1,  # CENTER horizontal
                "valign":      2,  # MIDDLE vertical
                "align_point": (cx, cy, 0),
            },
        )

    # 4. Agrupar por GD y fila
    gd_groups = group_by_gd(mesas)
    print(f"  GDs: {list(gd_groups.keys())}")

    # 5. Layers de salida
    ensure_layer(doc, LAYER_STRINGS, color=7)
    ensure_layer(doc, LAYER_LABELS,  color=3)
    ensure_layer(doc, LAYER_IXS,     color=7)

    # 6. Dibujar strings y notas
    total_rows = 0
    all_rows_global: list = []   # colectar todas las filas para etiquetas
    for gd_layer, gd_mesas in sorted(gd_groups.items()):
        rows = group_by_row(gd_mesas)
        print(f"  GD '{gd_layer}': {len(rows)} fila(s)")
        for ri, row in enumerate(rows):
            nm = len(row)
            print(f"    Fila {ri+1}: {nm} mesa(s), {nm * n_str} strings")
            draw_strings_row(
                msp, row,
                bajante_side     = bajante_side.upper(),
                bajante_dir      = bajante_dir.lower(),
                bajante_depth    = bajante_depth,
                bajante_offset   = bajante_offset,
                strings_per_mesa = n_str,
                pw               = panel_w,
                module_gap       = _mod_gap,
                doc              = doc,
            )
            all_rows_global.append(row)
            total_rows += 1

    # 6b. Etiquetas IxSy (solo si se indicaron inversores y strings)
    _n_inv = int(num_inversores)
    _n_spi = int(strings_per_inv)
    if _n_inv > 0 and _n_spi > 0:
        print(f"  Generando etiquetas: {_n_inv} inversores x {_n_spi} strings/inv "
              f"(start_from={start_from}, bajante={bajante_side.upper()})")
        draw_string_labels(
            msp,
            all_rows        = all_rows_global,
            bajante_side    = bajante_side.upper(),
            start_from      = start_from.lower(),
            num_inversores  = _n_inv,
            strings_per_inv = _n_spi,
            strings_per_mesa = n_str,
            panel_ph        = by1 - by0,
        )
        print(f"  Etiquetas colocadas: {_n_inv * _n_spi}")

    # 7. Guardar — reintenta con sufijo si el archivo está bloqueado (ej. abierto en AutoCAD)
    if output_dxf is None:
        p = Path(source_dxf)
        output_dxf = str(p.parent / f"{p.stem}_strings.dxf")

    base = Path(output_dxf)
    saved_path = None
    for attempt in range(10):
        candidate = base if attempt == 0 else \
            base.parent / f"{base.stem}_{attempt}{base.suffix}"
        try:
            doc.saveas(str(candidate))
            saved_path = str(candidate)
            break
        except PermissionError:
            print(f"  AVISO: '{candidate.name}' bloqueado (abierto en AutoCAD), reintentando...")
    if saved_path is None:
        raise PermissionError(
            f"No se pudo guardar el DXF. Cierra '{base.name}' en AutoCAD e intenta de nuevo."
        )

    size_mb = Path(saved_path).stat().st_size / 1024 / 1024
    print(f"\n  DXF guardado: {saved_path} ({size_mb:.1f} MB)")
    print(f"  Filas procesadas: {total_rows}")
    print(f"  Abrir en AutoCAD LT: File > Open > {saved_path}")
    return saved_path


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(
        description="Genera strings DC (+/-) sobre un layout solar DXF"
    )
    ap.add_argument("source_dxf")
    ap.add_argument("--output", "-o")
    ap.add_argument("--bajante-side", "-s", default="R", choices=["L", "R"])
    ap.add_argument("--bajante-dir", "-d", default="down", choices=["down", "up"])
    ap.add_argument("--bajante-depth", type=float, default=3.0)
    ap.add_argument("--bajante-offset", type=float, default=0.05,
                    help="Separacion del 1er string al borde interior de la mesa (default: 0.05)")
    ap.add_argument("--strings-per-mesa", type=int, default=0)
    ap.add_argument("--block-name")
    ap.add_argument("--panel-block", default="PANEL_615")
    ap.add_argument("--num-inversores", type=int, default=0,
                    help="Cantidad de inversores (para etiquetas IxSy). 0=sin etiquetas.")
    ap.add_argument("--strings-per-inv", type=int, default=0,
                    help="Strings por inversor (para etiquetas IxSy).")
    ap.add_argument("--start-from", default="top", choices=["top", "bottom"],
                    help="Inicio del etiquetado: top=arriba, bottom=abajo (default: top).")

    args = ap.parse_args()

    out = run_generate_strings(
        source_dxf       = args.source_dxf,
        output_dxf       = args.output,
        bajante_side     = args.bajante_side,
        bajante_dir      = args.bajante_dir,
        bajante_depth    = args.bajante_depth,
        bajante_offset   = args.bajante_offset,
        strings_per_mesa = args.strings_per_mesa,
        block_name       = args.block_name,
        panel_block      = args.panel_block,
        num_inversores   = args.num_inversores,
        strings_per_inv  = args.strings_per_inv,
        start_from       = args.start_from,
    )
    print(f"\nListo: File > Open > {out}")
