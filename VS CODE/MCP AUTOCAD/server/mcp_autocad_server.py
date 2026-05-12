"""
MCP AutoCAD Server — Claude Code <-> AutoCAD LT
Protocolo: MCP sobre stdio (compatible con Claude Code CLI y VS Code extension)

Tools expuestos:
  - analyze_dxf          : Lee y resume un archivo DXF
  - calculate_layout     : Calcula posiciones de mesas (motor Python)
  - generate_dxf         : Genera DXF con paneles implantados (desde JSON de proyecto o params)
  - generate_layout_lisp : Genera .lsp listo para cargar en AutoCAD LT (legado)
  - generate_labels_lisp : Genera .lsp con etiquetas IxMyS z
  - calculate_metrado    : Estima longitudes de cable DC por string
  - build_nomenclature   : Genera lista de tags para el proyecto

Separaciones estándar (del LISP solar_array_layout_v1.15):
  Entre mesas:   gap_horizontal_m=0.5, gap_vertical_m=2.5
  Entre módulos: module_gap_m=0.04
  Entre GDs:     gd_gap_m=6.0 (rows) / 8.0 (columns — según proyecto)
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from tools.geometry import (
    run_panel_layout,
    run_hybrid_layout,
    parse_polygon_from_points,
    circle_to_polygon,
    get_bbox,
)
from tools.lisp_generator import (
    generate_panel_layout,
    generate_hybrid_layout,
    generate_string_labels,
    generate_corridor_lines,
)
from tools.electrical import (
    build_nomenclature,
    estimate_dc_cable_length,
)

try:
    from tools.dxf_reader import get_dxf_summary, read_boundary_polygons, read_circles
    from tools.dxf_writer import get_block_dims, write_layout_dxf
    HAS_EZDXF = True
except ImportError:
    HAS_EZDXF = False

try:
    import mcp.server.stdio
    import mcp.types as types
    from mcp.server import Server
    HAS_MCP = True
except ImportError:
    HAS_MCP = False


# ── Definición de Tools ───────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "analyze_dxf",
        "description": (
            "Lee un archivo DXF exportado desde AutoCAD LT y devuelve un resumen: "
            "layers, bloques, tipos de entidades, colores y coordenadas de polígonos. "
            "Usalo primero para entender la estructura del dibujo."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "dxf_path": {
                    "type": "string",
                    "description": "Ruta absoluta al archivo .dxf"
                }
            },
            "required": ["dxf_path"]
        }
    },
    {
        "name": "calculate_layout",
        "description": (
            "Calcula las posiciones de mesas solares dentro de un polígono límite. "
            "Equivalente a solar_array_layout_v1.15.lsp pero en Python con soporte "
            "para modo columnas (GDs lado a lado) y filas (GDs apilados), "
            "relleno top-to-bottom, y expansión de panel individual a mesa. "
            "Retorna posiciones de mesas {group, x, y} donde (x,y) = esquina inferior-izquierda. "
            "Separaciones por defecto: entre módulos 0.04m, entre mesas 0.5m H / 2.5m V."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "boundary_points": {
                    "type": "array",
                    "description": "Lista de [x, y] que forman el polígono límite",
                    "items": {"type": "array", "items": {"type": "number"}}
                },
                "panel_width_m": {
                    "type": "number",
                    "description": "Ancho del bloque en metros (panel individual o mesa completa)"
                },
                "panel_height_m": {
                    "type": "number",
                    "description": "Alto del bloque en metros (panel individual o mesa completa)"
                },
                "panels_wide": {
                    "type": "integer",
                    "default": 0,
                    "description": "Módulos por mesa en X. 0 = el bloque ya es la mesa completa."
                },
                "panels_high": {
                    "type": "integer",
                    "default": 0,
                    "description": "Módulos por mesa en Y. 0 = el bloque ya es la mesa completa."
                },
                "module_gap_m": {
                    "type": "number",
                    "default": 0.04,
                    "description": "Separación entre módulos dentro de la misma mesa (m)."
                },
                "gap_horizontal_m": {
                    "type": "number",
                    "default": 0.5,
                    "description": "Separación horizontal ENTRE MESAS (m). Default LISP: 0.5 m."
                },
                "gap_vertical_m": {
                    "type": "number",
                    "default": 2.5,
                    "description": "Separación vertical ENTRE MESAS (m). Default LISP: 2.5 m."
                },
                "num_groups": {
                    "type": "integer",
                    "default": 1,
                    "description": "Número de GDs"
                },
                "panels_per_group": {
                    "type": "integer",
                    "default": 0,
                    "description": "Mesas máximas por GD. 0 = llenar todo el polígono."
                },
                "layout_mode": {
                    "type": "string",
                    "enum": ["rows", "columns"],
                    "default": "rows",
                    "description": (
                        "rows    = GDs apilados verticalmente (original LISP, relleno abajo-arriba). "
                        "columns = GDs en bandas horizontales separadas, ideal cuando las vías de "
                        "acceso van por la parte inferior (usar con fill_top_to_bottom=true)."
                    )
                },
                "fill_top_to_bottom": {
                    "type": "boolean",
                    "default": False,
                    "description": (
                        "Solo en modo columns. True = rellena de arriba hacia abajo "
                        "(paneles en zona alta, vías/transmisión en zona baja)."
                    )
                },
                "gd_gap_m": {
                    "type": "number",
                    "default": 6.0,
                    "description": (
                        "Separación entre GDs en metros. "
                        "Modo rows: separación vertical entre grupos. "
                        "Modo columns: separación horizontal entre columnas de GDs. "
                        "Típico: 6 m (rows) / 8 m (columns)."
                    )
                },
                "circle_obstacles": {
                    "type": "array",
                    "description": "Obstáculos circulares [[cx, cy, radio], ...]",
                    "items": {"type": "array"}
                },
                "poly_obstacles": {
                    "type": "array",
                    "description": "Obstáculos poligonales [[[x,y], ...], ...]",
                    "items": {"type": "array"}
                },
                "fallback_wide": {
                    "type": "integer",
                    "default": 0,
                    "description": (
                        "Modo hibrido: modulos en X de la mesa secundaria. "
                        "0 = sin complemento. Tipico: 13 cuando primary es 26."
                    )
                },
                "fallback_high": {
                    "type": "integer",
                    "default": 0,
                    "description": "Modulos en Y de la mesa secundaria. Tipico: 2."
                },
                "target_panels": {
                    "type": "integer",
                    "default": 0,
                    "description": (
                        "Total de paneles objetivo (modo hibrido). "
                        "El sistema calcula cuantas mesas secundarias se necesitan. "
                        "0 = llenar todo el espacio disponible con secundarias tambien."
                    )
                }
            },
            "required": ["boundary_points", "panel_width_m", "panel_height_m"]
        }
    },
    {
        "name": "generate_dxf",
        "description": (
            "Genera un archivo DXF con los paneles solares implantados directamente como bloques INSERT. "
            "Output abrible en AutoCAD LT sin necesidad de cargar LISP. "
            "Modo 1 (recomendado): proveer config_path apuntando a un JSON en projects/. "
            "Modo 2: proveer todos los parametros individualmente (igual que calculate_layout "
            "mas source_dxf, output_dxf, block_name, blk_offset_x/y)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "config_path": {
                    "type": "string",
                    "description": (
                        "Ruta al JSON del proyecto (ej: projects/colibri.json). "
                        "Si se especifica, los demas parametros son ignorados."
                    )
                },
                "source_dxf": {
                    "type": "string",
                    "description": "Ruta al DXF fuente (contiene el poligono limite y la definicion del bloque de panel)."
                },
                "output_dxf": {
                    "type": "string",
                    "description": "Ruta del DXF de salida. Por defecto: output/<project_name>.dxf"
                },
                "block_name": {
                    "type": "string",
                    "default": "PANEL_615",
                    "description": "Nombre del bloque de panel en el DXF."
                },
                "block_library_dxf": {
                    "type": "string",
                    "description": "DXF alternativo para importar el bloque si no existe en source_dxf."
                },
                "boundary_points": {
                    "type": "array",
                    "description": "Poligono limite [[x,y],...] (alternativa a leer del DXF).",
                    "items": {"type": "array", "items": {"type": "number"}}
                },
                "placements": {
                    "type": "array",
                    "description": "Posiciones calculadas por calculate_layout [{group,x,y},...]."
                },
                "panel_width_m":  {"type": "number"},
                "panel_height_m": {"type": "number"},
                "blk_offset_x":   {"type": "number", "default": 0.0,
                                   "description": "Offset X insert point desde esquina izq del panel. PANEL_615: 0.567"},
                "blk_offset_y":   {"type": "number", "default": 0.0,
                                   "description": "Offset Y insert point desde esquina inf del panel. PANEL_615: 1.151"},
                "panels_wide":    {"type": "integer", "default": 26},
                "panels_high":    {"type": "integer", "default": 2},
                "module_gap_m":   {"type": "number", "default": 0.04},
                "layer_prefix":   {"type": "string", "default": "GD"},
                "fallback_placements": {
                    "type": "array",
                    "description": "Mesas fallback del modo hibrido (campo 'fallback' de calculate_layout)."
                },
                "fallback_wide":  {"type": "integer", "default": 0},
                "fallback_high":  {"type": "integer", "default": 0}
            }
        }
    },
    {
        "name": "generate_layout_lisp",
        "description": (
            "Genera un archivo .lsp con los comandos entmake para insertar los bloques "
            "en AutoCAD LT. El usuario solo carga el .lsp con (load ...) y los paneles aparecen. "
            "Cada GD va en su propio layer (GD1, GD2, ...). "
            "Si panels_wide/high > 0, expande cada placement en la grilla de paneles individuales."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "placements": {
                    "type": "array",
                    "description": "Lista de posiciones del tool calculate_layout [{group,x,y},...]"
                },
                "block_name": {
                    "type": "string",
                    "description": "Nombre exacto del bloque en AutoCAD (ej: PANEL_615)"
                },
                "panels_wide": {
                    "type": "integer",
                    "default": 0,
                    "description": "Módulos por mesa en X. 0 = un INSERT por mesa."
                },
                "panels_high": {
                    "type": "integer",
                    "default": 0,
                    "description": "Módulos por mesa en Y. 0 = un INSERT por mesa."
                },
                "panel_w": {
                    "type": "number",
                    "default": 0.0,
                    "description": "Ancho del panel individual en metros (requerido si panels_wide>0)."
                },
                "panel_h": {
                    "type": "number",
                    "default": 0.0,
                    "description": "Alto del panel individual en metros (requerido si panels_wide>0)."
                },
                "module_gap": {
                    "type": "number",
                    "default": 0.04,
                    "description": "Separación entre módulos dentro de la mesa (m)."
                },
                "blk_offset_x": {
                    "type": "number",
                    "default": 0.0,
                    "description": (
                        "Distancia en X desde la esquina izquierda del panel hasta el insert point "
                        "del bloque. Para PANEL_615: 0.567 m."
                    )
                },
                "blk_offset_y": {
                    "type": "number",
                    "default": 0.0,
                    "description": (
                        "Distancia en Y desde la esquina inferior del panel hasta el insert point "
                        "del bloque. Para PANEL_615: 1.151 m."
                    )
                },
                "offset_x": {
                    "type": "number",
                    "default": 0.0,
                    "description": "Offset X del insert point (modo bloque-mesa)."
                },
                "offset_y": {
                    "type": "number",
                    "default": 0.0,
                    "description": "Offset Y del insert point (modo bloque-mesa)."
                },
                "scale_x": {"type": "number", "default": 1.0},
                "scale_y": {"type": "number", "default": 1.0},
                "layer_prefix": {
                    "type": "string",
                    "default": "GD",
                    "description": "Prefijo de layer (GD1, GD2, ...). Puede ser nombre de proyecto."
                },
                "output_filename": {
                    "type": "string",
                    "default": "layout_paneles.lsp",
                    "description": "Nombre del archivo .lsp generado."
                },
                "fallback_placements": {
                    "type": "array",
                    "description": (
                        "Mesas secundarias del modo hibrido (campo 'fallback' de calculate_layout). "
                        "Si se provee, genera un LISP combinado con ambas configuraciones."
                    )
                },
                "fallback_wide": {
                    "type": "integer",
                    "default": 0,
                    "description": "Modulos en X de la mesa secundaria (requerido si fallback_placements presente)."
                },
                "fallback_high": {
                    "type": "integer",
                    "default": 0,
                    "description": "Modulos en Y de la mesa secundaria."
                }
            },
            "required": ["placements", "block_name"]
        }
    },
    {
        "name": "generate_labels_lisp",
        "description": (
            "Genera .lsp con etiquetas de strings en formato I{n}M{n}S{n} "
            "posicionadas automáticamente sobre los paneles."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "panel_positions": {"type": "array"},
                "panels_per_string": {"type": "integer"},
                "inversores_config": {
                    "type": "array",
                    "description": "[{inversor: 1, mppt: 1, strings: 4}, ...]"
                },
                "text_height": {"type": "number", "default": 0.3},
                "output_filename": {"type": "string", "default": "labels_strings.lsp"}
            },
            "required": ["panel_positions", "panels_per_string", "inversores_config"]
        }
    },
    {
        "name": "calculate_metrado",
        "description": (
            "Estima longitudes de cable DC (positivo + negativo) por string. "
            "Basado en posiciones de paneles y offset al corredor eléctrico."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "panel_positions": {"type": "array"},
                "panels_per_string": {"type": "integer"},
                "corridor_y_offset_m": {"type": "number", "default": 3.0},
                "add_slack_pct": {"type": "number", "default": 0.10}
            },
            "required": ["panel_positions", "panels_per_string"]
        }
    },
    {
        "name": "build_nomenclature",
        "description": "Genera la lista completa de tags IxMyS z para un proyecto.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "num_inversores": {"type": "integer"},
                "num_mppt_per_inv": {"type": "integer"},
                "num_strings_per_mppt": {"type": "integer"}
            },
            "required": ["num_inversores", "num_mppt_per_inv", "num_strings_per_mppt"]
        }
    },
    {
        "name": "generate_strings_dxf",
        "description": (
            "Dibuja automáticamente los strings DC (conductores positivos y negativos) "
            "sobre un layout solar DXF. Detecta la cantidad de mesas por fila, dibuja "
            "LWPOLYLINE conectadas (horizontal + bajante vertical) en colores rojo(+) y "
            "cian(-), y agrega etiquetas 'Tubo Interflex / Nx6mm2(+) + Nx6mm2(-)' en "
            "cada cruce entre mesas con el recuento correcto de conductores y tuberías. "
            "Genera un DXF nuevo sin modificar el layout original."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_dxf": {
                    "type": "string",
                    "description": "Ruta absoluta al DXF con el layout (salida de generate_dxf)."
                },
                "output_dxf": {
                    "type": "string",
                    "description": "Ruta del DXF de salida (default: <fuente>_strings.dxf)."
                },
                "bajante_side": {
                    "type": "string",
                    "enum": ["L", "R"],
                    "default": "R",
                    "description": "Lado del bajante/conduit: R=derecha, L=izquierda."
                },
                "bajante_dir": {
                    "type": "string",
                    "enum": ["down", "up"],
                    "default": "down",
                    "description": "Dirección vertical del bajante: down=abajo, up=arriba."
                },
                "bajante_depth": {
                    "type": "number",
                    "default": 3.0,
                    "description": "Longitud vertical del bajante en metros (default: 3.0)."
                },
                "bajante_offset": {
                    "type": "number",
                    "default": 0.05,
                    "description": "Separacion del primer string al borde interior de la mesa (m, default: 0.05). Strings siguientes a +0.05m cada uno."
                },
                "strings_per_mesa": {
                    "type": "integer",
                    "default": 0,
                    "description": "Strings por mesa (0=auto-detectar del nombre del bloque, ej: '24x2'→2)."
                },
                "block_name": {
                    "type": "string",
                    "description": "Nombre del bloque de mesa (auto si se omite, ej: '24x2')."
                },
                "panel_block": {
                    "type": "string",
                    "default": "PANEL_615",
                    "description": "Bloque de panel individual para layouts sin bloque de mesa."
                },
                "num_inversores": {
                    "type": "integer",
                    "default": 0,
                    "description": (
                        "Cantidad total de inversores. Si > 0 (junto con strings_per_inv), "
                        "se generan etiquetas IxSy en cada mesa. 0 = sin etiquetas."
                    )
                },
                "strings_per_inv": {
                    "type": "integer",
                    "default": 0,
                    "description": "Strings por inversor para el etiquetado IxSy."
                },
                "start_from": {
                    "type": "string",
                    "enum": ["top", "bottom"],
                    "default": "top",
                    "description": (
                        "Inicio del etiquetado IxSy: "
                        "'top' = inversor 1 empieza en la fila MAS ALTA; "
                        "'bottom' = inversor 1 empieza en la fila MAS BAJA."
                    )
                }
            },
            "required": ["source_dxf"]
        }
    }
]


# ── Dispatch de cada tool ─────────────────────────────────────────────────────

def handle_analyze_dxf(args: dict) -> str:
    if not HAS_EZDXF:
        return "ERROR: ezdxf no instalado. Ejecuta: pip install ezdxf"
    try:
        summary = get_dxf_summary(args["dxf_path"])
        return json.dumps(summary, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"ERROR al leer DXF: {e}"


def handle_calculate_layout(args: dict) -> str:
    boundary = parse_polygon_from_points(args["boundary_points"])
    poly_obs = None
    circle_obs = None

    if args.get("poly_obstacles"):
        poly_obs = [parse_polygon_from_points(p) for p in args["poly_obstacles"]]
    if args.get("circle_obstacles"):
        circle_obs = [(c[0], c[1], c[2]) for c in args["circle_obstacles"]]

    panels_wide    = int(args.get("panels_wide", 0))
    panels_high    = int(args.get("panels_high", 0))
    module_gap     = float(args.get("module_gap_m", 0.04))
    layout_mode    = args.get("layout_mode", "rows")
    fill_tb        = bool(args.get("fill_top_to_bottom", False))
    gd_gap         = float(args.get("gd_gap_m", 6.0))
    panel_w        = float(args["panel_width_m"])
    panel_h        = float(args["panel_height_m"])
    fallback_wide  = int(args.get("fallback_wide", 0))
    fallback_high  = int(args.get("fallback_high", 0))
    target_panels  = int(args.get("target_panels", 0))

    common = dict(
        boundary=boundary,
        panel_w=panel_w, panel_h=panel_h,
        gap_h=float(args.get("gap_horizontal_m", 0.5)),
        gap_v=float(args.get("gap_vertical_m", 2.5)),
        num_groups=int(args.get("num_groups", 1)),
        panels_per_group=int(args.get("panels_per_group", 0)),
        poly_obstacles=poly_obs,
        circle_obstacles=circle_obs,
        group_sep=gd_gap,
        panels_wide=panels_wide,
        panels_high=panels_high,
        module_gap=module_gap,
        layout_mode=layout_mode,
        fill_top_to_bottom=fill_tb,
    )

    if fallback_wide > 0 and fallback_high > 0:
        # ── Modo hibrido ──────────────────────────────────────────────────────
        hybrid = run_hybrid_layout(
            **common,
            fallback_wide=fallback_wide,
            fallback_high=fallback_high,
            target_panels=target_panels,
        )

        def count_by_group(plist):
            bg: dict[int, int] = {}
            for p in plist: bg[p["group"]] = bg.get(p["group"], 0) + 1
            return {str(k): v for k, v in sorted(bg.items())}

        result = {
            "hybrid": True,
            "total_mesas": len(hybrid["primary"]) + len(hybrid["fallback"]),
            "primary": {
                "mesas": len(hybrid["primary"]),
                "by_group": count_by_group(hybrid["primary"]),
                "panels": hybrid["panels_primary"],
                "mesa_w_m": hybrid["mesa_w_primary"],
                "mesa_h_m": hybrid["mesa_h_primary"],
                "config": f"{panels_wide}x{panels_high}",
                "placements": hybrid["primary"],
            },
            "fallback": {
                "mesas": len(hybrid["fallback"]),
                "by_group": count_by_group(hybrid["fallback"]),
                "panels": hybrid["panels_fallback"],
                "mesa_w_m": hybrid["mesa_w_fallback"],
                "mesa_h_m": hybrid["mesa_h_fallback"],
                "config": f"{fallback_wide}x{fallback_high}",
                "placements": hybrid["fallback"],
            },
            "total_panels": hybrid["total_panels"],
            "layout_mode": layout_mode,
            "fill_top_to_bottom": fill_tb,
        }
    else:
        # ── Modo normal ───────────────────────────────────────────────────────
        placements = run_panel_layout(**common)

        if panels_wide > 0 and panels_high > 0:
            mesa_w = panels_wide * panel_w + (panels_wide - 1) * module_gap
            mesa_h = panels_high * panel_h + (panels_high - 1) * module_gap
        else:
            mesa_w = panel_w
            mesa_h = panel_h

        by_group: dict[int, int] = {}
        for p in placements:
            by_group[p["group"]] = by_group.get(p["group"], 0) + 1

        result = {
            "hybrid": False,
            "total_mesas": len(placements),
            "by_group": {str(k): v for k, v in sorted(by_group.items())},
            "mesa_w_m": round(mesa_w, 3),
            "mesa_h_m": round(mesa_h, 3),
            "layout_mode": layout_mode,
            "fill_top_to_bottom": fill_tb,
            "placements": placements,
        }
    return json.dumps(result, indent=2)


def handle_generate_dxf(args: dict) -> str:
    if not HAS_EZDXF:
        return "ERROR: ezdxf no instalado. Ejecuta: pip install ezdxf"

    config_path = args.get("config_path")

    if config_path:
        # Modo 1: delega en generate.py con JSON de proyecto
        import sys as _sys
        _root = Path(__file__).parent.parent
        if str(_root) not in _sys.path:
            _sys.path.insert(0, str(_root))
        from generate import run_project
        try:
            out = run_project(config_path)
            return f"DXF generado: {out}\nAbrir en AutoCAD LT: File → Open → {out}"
        except Exception as e:
            return f"ERROR al generar DXF: {e}"

    # Modo 2: parametros individuales (placements ya calculados)
    if not args.get("source_dxf"):
        return "ERROR: se requiere 'config_path' o al menos 'source_dxf' + 'placements'."
    if not args.get("placements"):
        return "ERROR: se requiere 'placements' (salida de calculate_layout) o 'config_path'."

    source_dxf   = args["source_dxf"]
    output_dxf   = args.get("output_dxf", "output/layout.dxf")
    block_name   = args.get("block_name", "PANEL_615")
    block_lib    = args.get("block_library_dxf")
    panels_wide  = int(args.get("panels_wide", 26))
    panels_high  = int(args.get("panels_high", 2))
    module_gap   = float(args.get("module_gap_m", 0.04))
    layer_prefix = args.get("layer_prefix", "GD")

    # Dimensiones del panel
    if args.get("panel_width_m") and args.get("panel_height_m"):
        panel_w      = float(args["panel_width_m"])
        panel_h      = float(args["panel_height_m"])
        blk_offset_x = float(args.get("blk_offset_x", 0.0))
        blk_offset_y = float(args.get("blk_offset_y", 0.0))
    else:
        try:
            panel_w, panel_h, blk_offset_x, blk_offset_y = get_block_dims(source_dxf, block_name)
        except Exception as e:
            return f"ERROR al leer dimensiones del bloque: {e}"

    fallback_pl = args.get("fallback_placements") or []
    fw = int(args.get("fallback_wide", 0))
    fh = int(args.get("fallback_high", 0))

    try:
        out = write_layout_dxf(
            source_dxf_path=source_dxf,
            output_dxf_path=output_dxf,
            placements=args["placements"],
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
        from pathlib import Path as _Path
        size_mb = _Path(out).stat().st_size / 1024 / 1024
        return (
            f"DXF generado: {out} ({size_mb:.1f} MB)\n"
            f"Abrir en AutoCAD LT: File → Open → {out}"
        )
    except Exception as e:
        return f"ERROR al escribir DXF: {e}"


def handle_generate_layout_lisp(args: dict) -> str:
    fallback_pl = args.get("fallback_placements") or []
    fallback_w  = int(args.get("fallback_wide", 0))
    fallback_h  = int(args.get("fallback_high", 0))

    if fallback_pl and fallback_w > 0 and fallback_h > 0:
        # ── Modo hibrido ──────────────────────────────────────────────────────
        out_path = generate_hybrid_layout(
            primary_placements=args["placements"],
            fallback_placements=fallback_pl,
            block_name=args["block_name"],
            panel_w=float(args.get("panel_w", 0.0)),
            panel_h=float(args.get("panel_h", 0.0)),
            primary_wide=int(args.get("panels_wide", 0)),
            primary_high=int(args.get("panels_high", 0)),
            fallback_wide=fallback_w,
            fallback_high=fallback_h,
            module_gap=float(args.get("module_gap", 0.04)),
            blk_offset_x=float(args.get("blk_offset_x", 0.0)),
            blk_offset_y=float(args.get("blk_offset_y", 0.0)),
            layer_prefix=args.get("layer_prefix", "GD"),
            output_filename=args.get("output_filename", "layout_hibrido.lsp"),
        )
    else:
        # ── Modo normal ───────────────────────────────────────────────────────
        out_path = generate_panel_layout(
            placements=args["placements"],
            block_name=args["block_name"],
            offset_x=float(args.get("offset_x", 0.0)),
            offset_y=float(args.get("offset_y", 0.0)),
            scale_x=float(args.get("scale_x", 1.0)),
            scale_y=float(args.get("scale_y", 1.0)),
            layer_prefix=args.get("layer_prefix", "GD"),
            output_filename=args.get("output_filename", "layout_paneles.lsp"),
            panels_wide=int(args.get("panels_wide", 0)),
            panels_high=int(args.get("panels_high", 0)),
            panel_w=float(args.get("panel_w", 0.0)),
            panel_h=float(args.get("panel_h", 0.0)),
            module_gap=float(args.get("module_gap", 0.04)),
            blk_offset_x=float(args.get("blk_offset_x", 0.0)),
            blk_offset_y=float(args.get("blk_offset_y", 0.0)),
        )
    return (
        f"LISP generado: {out_path}\n"
        f'Carga en AutoCAD LT con: (load "{out_path}")'
    )


def handle_generate_labels_lisp(args: dict) -> str:
    out_path = generate_string_labels(
        panel_positions=args["panel_positions"],
        panels_per_string=args["panels_per_string"],
        inversores_config=args["inversores_config"],
        text_height=float(args.get("text_height", 0.3)),
        output_filename=args.get("output_filename", "labels_strings.lsp"),
    )
    return f"LISP de etiquetas generado: {out_path}"


def handle_calculate_metrado(args: dict) -> str:
    results = estimate_dc_cable_length(
        panel_positions=args["panel_positions"],
        panels_per_string=args["panels_per_string"],
        corridor_y_offset=float(args.get("corridor_y_offset_m", 3.0)),
        add_slack_pct=float(args.get("add_slack_pct", 0.10)),
    )
    total = sum(r["total_m"] for r in results)
    return json.dumps({
        "strings": results,
        "total_cable_m": round(total, 2),
    }, indent=2)


def handle_build_nomenclature(args: dict) -> str:
    tags = build_nomenclature(
        num_inversores=args["num_inversores"],
        num_mppt_per_inv=args["num_mppt_per_inv"],
        num_strings_per_mppt=args["num_strings_per_mppt"],
    )
    return json.dumps({"tags": tags, "total": len(tags)}, indent=2)


def handle_generate_strings_dxf(args: dict) -> str:
    if not HAS_EZDXF:
        return "ERROR: ezdxf no instalado. Ejecuta: pip install ezdxf"
    try:
        import sys as _sys
        _root = Path(__file__).parent.parent
        if str(_root) not in _sys.path:
            _sys.path.insert(0, str(_root))
        from generate_strings_dxf import run_generate_strings
        out = run_generate_strings(
            source_dxf       = args["source_dxf"],
            output_dxf       = args.get("output_dxf"),
            bajante_side     = args.get("bajante_side", "R"),
            bajante_dir      = args.get("bajante_dir", "down"),
            bajante_depth    = float(args.get("bajante_depth", 3.0)),
            bajante_offset   = float(args.get("bajante_offset", 0.05)),
            strings_per_mesa = int(args.get("strings_per_mesa", 0)),
            block_name       = args.get("block_name"),
            panel_block      = args.get("panel_block", "PANEL_615"),
            num_inversores   = int(args.get("num_inversores", 0)),
            strings_per_inv  = int(args.get("strings_per_inv", 0)),
            start_from       = args.get("start_from", "top"),
        )
        return f"DXF de strings generado: {out}\nAbrir en AutoCAD LT: File → Open → {out}"
    except Exception as e:
        return f"ERROR al generar strings: {e}"


HANDLERS = {
    "analyze_dxf": handle_analyze_dxf,
    "calculate_layout": handle_calculate_layout,
    "generate_dxf": handle_generate_dxf,
    "generate_layout_lisp": handle_generate_layout_lisp,
    "generate_labels_lisp": handle_generate_labels_lisp,
    "calculate_metrado": handle_calculate_metrado,
    "build_nomenclature": handle_build_nomenclature,
    "generate_strings_dxf": handle_generate_strings_dxf,
}


# ── Modo MCP (Claude Code) ───────────────────────────────────────────────────

async def run_mcp_server():
    if not HAS_MCP:
        print("ERROR: mcp no instalado. Ejecuta: pip install mcp", file=sys.stderr)
        sys.exit(1)

    server = Server("mcp-autocad")

    @server.list_tools()
    async def list_tools():
        return [
            types.Tool(
                name=t["name"],
                description=t["description"],
                inputSchema=t["inputSchema"],
            )
            for t in TOOLS
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        handler = HANDLERS.get(name)
        if not handler:
            raise ValueError(f"Tool desconocido: {name}")
        result = handler(arguments)
        return [types.TextContent(type="text", text=result)]

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


# ── Modo CLI (prueba sin Claude) ─────────────────────────────────────────────

def run_cli():
    print("MCP AutoCAD Server -- modo prueba CLI")
    print("Tools disponibles:")
    for t in TOOLS:
        print(f"  - {t['name']}: {t['description'][:70]}...")

    print("\nEjemplo 1: calculate_layout normal (rectangulo 200x150, 3 GDs en columnas, 26x2)")
    boundary = [[0, 0], [200, 0], [200, 150], [0, 150]]
    result = handle_calculate_layout({
        "boundary_points": boundary,
        "panel_width_m": 1.303,
        "panel_height_m": 2.384,
        "panels_wide": 26,
        "panels_high": 2,
        "module_gap_m": 0.04,
        "gap_horizontal_m": 0.5,
        "gap_vertical_m": 2.5,
        "num_groups": 3,
        "panels_per_group": 36,
        "layout_mode": "columns",
        "fill_top_to_bottom": True,
        "gd_gap_m": 8.0,
    })
    data = json.loads(result)
    print(f"  total_mesas={data['total_mesas']}  by_group={data['by_group']}")
    print(f"  mesa_w={data['mesa_w_m']} m  mesa_h={data['mesa_h_m']} m")

    print("\nEjemplo 2: calculate_layout hibrido (26x2 primaria + 13x2 complemento, target=1872)")
    result2 = handle_calculate_layout({
        "boundary_points": boundary,
        "panel_width_m": 1.303,
        "panel_height_m": 2.384,
        "panels_wide": 26,
        "panels_high": 2,
        "module_gap_m": 0.04,
        "gap_horizontal_m": 0.5,
        "gap_vertical_m": 2.5,
        "num_groups": 1,
        "layout_mode": "rows",
        "fill_top_to_bottom": True,
        "fallback_wide": 13,
        "fallback_high": 2,
        "target_panels": 1872,
    })
    d2 = json.loads(result2)
    p = d2["primary"]; f = d2["fallback"]
    print(f"  Primaria  {p['config']}: {p['mesas']} mesas = {p['panels']} paneles")
    print(f"  Secundaria {f['config']}: {f['mesas']} mesas = {f['panels']} paneles")
    print(f"  TOTAL: {d2['total_panels']} paneles")


if __name__ == "__main__":
    if "--cli" in sys.argv:
        run_cli()
    else:
        import asyncio
        asyncio.run(run_mcp_server())
