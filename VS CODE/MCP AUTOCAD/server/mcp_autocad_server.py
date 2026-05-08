"""
MCP AutoCAD Server — Claude Code ↔ AutoCAD LT
Protocolo: MCP sobre stdio (compatible con Claude Code CLI y VS Code extension)

Tools expuestos:
  - analyze_dxf          : Lee y resume un archivo DXF
  - calculate_layout     : Calcula posiciones de paneles (motor Python)
  - generate_layout_lisp : Genera .lsp listo para cargar en AutoCAD LT
  - generate_labels_lisp : Genera .lsp con etiquetas IxMyS z
  - calculate_metrado    : Estima longitudes de cable DC por string
  - build_nomenclature   : Genera lista de tags para el proyecto
"""
import json
import sys
from pathlib import Path

# Agregar el directorio tools al path
sys.path.insert(0, str(Path(__file__).parent))

from tools.geometry import (
    run_panel_layout,
    parse_polygon_from_points,
    circle_to_polygon,
    get_bbox,
)
from tools.lisp_generator import (
    generate_panel_layout,
    generate_string_labels,
    generate_corridor_lines,
)
from tools.electrical import (
    build_nomenclature,
    estimate_dc_cable_length,
)

try:
    from tools.dxf_reader import get_dxf_summary, read_boundary_polygons, read_circles
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
            "layers, bloques, tipos de entidades y conteos. "
            "Úsalo para entender la estructura del dibujo antes de procesar."
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
            "Calcula las posiciones óptimas de paneles solares dentro de un polígono límite. "
            "Usa el mismo algoritmo que solar_array_layout_v1.15.lsp pero en Python. "
            "Devuelve lista de posiciones {group, x, y} listas para dibujar."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "boundary_points": {
                    "type": "array",
                    "description": "Lista de [x, y] que forman el polígono límite",
                    "items": {"type": "array", "items": {"type": "number"}}
                },
                "panel_width_m": {"type": "number", "description": "Ancho del panel/mesa en metros"},
                "panel_height_m": {"type": "number", "description": "Alto del panel/mesa en metros"},
                "gap_horizontal_m": {"type": "number", "default": 0.5},
                "gap_vertical_m": {"type": "number", "default": 2.5},
                "num_groups": {"type": "integer", "default": 1, "description": "Número de GDs"},
                "panels_per_group": {"type": "integer", "default": 0, "description": "0 = llenar todo"},
                "circle_obstacles": {
                    "type": "array",
                    "description": "Lista de obstáculos circulares [[cx, cy, r], ...]",
                    "items": {"type": "array"}
                },
                "poly_obstacles": {
                    "type": "array",
                    "description": "Lista de polígonos obstáculo [[[x,y], ...], ...]",
                    "items": {"type": "array"}
                }
            },
            "required": ["boundary_points", "panel_width_m", "panel_height_m"]
        }
    },
    {
        "name": "generate_layout_lisp",
        "description": (
            "Genera un archivo .lsp que inserta los bloques de mesas en AutoCAD LT. "
            "El usuario solo carga el .lsp en AutoCAD y los paneles aparecen. "
            "Cada GD va en un layer separado (GD1, GD2, ...)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "placements": {
                    "type": "array",
                    "description": "Lista de posiciones del tool calculate_layout"
                },
                "block_name": {"type": "string", "description": "Nombre del bloque mesa en AutoCAD"},
                "offset_x": {"type": "number", "default": 0.0},
                "offset_y": {"type": "number", "default": 0.0},
                "scale_x": {"type": "number", "default": 1.0},
                "scale_y": {"type": "number", "default": 1.0},
                "layer_prefix": {"type": "string", "default": "GD"},
                "output_filename": {"type": "string", "default": "layout_paneles.lsp"}
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

    placements = run_panel_layout(
        boundary=boundary,
        panel_w=args["panel_width_m"],
        panel_h=args["panel_height_m"],
        gap_h=args.get("gap_horizontal_m", 0.5),
        gap_v=args.get("gap_vertical_m", 2.5),
        num_groups=args.get("num_groups", 1),
        panels_per_group=args.get("panels_per_group", 0),
        poly_obstacles=poly_obs,
        circle_obstacles=circle_obs,
    )

    by_group: dict[int, int] = {}
    for p in placements:
        by_group[p["group"]] = by_group.get(p["group"], 0) + 1

    result = {
        "total_panels": len(placements),
        "by_group": by_group,
        "placements": placements,
    }
    return json.dumps(result, indent=2)


def handle_generate_layout_lisp(args: dict) -> str:
    out_path = generate_panel_layout(
        placements=args["placements"],
        block_name=args["block_name"],
        offset_x=args.get("offset_x", 0.0),
        offset_y=args.get("offset_y", 0.0),
        scale_x=args.get("scale_x", 1.0),
        scale_y=args.get("scale_y", 1.0),
        layer_prefix=args.get("layer_prefix", "GD"),
        output_filename=args.get("output_filename", "layout_paneles.lsp"),
    )
    return f"✓ LISP generado en: {out_path}\nCarga en AutoCAD LT con: (load \"{out_path}\")"


def handle_generate_labels_lisp(args: dict) -> str:
    out_path = generate_string_labels(
        panel_positions=args["panel_positions"],
        panels_per_string=args["panels_per_string"],
        inversores_config=args["inversores_config"],
        text_height=args.get("text_height", 0.3),
        output_filename=args.get("output_filename", "labels_strings.lsp"),
    )
    return f"✓ LISP de etiquetas generado en: {out_path}"


def handle_calculate_metrado(args: dict) -> str:
    results = estimate_dc_cable_length(
        panel_positions=args["panel_positions"],
        panels_per_string=args["panels_per_string"],
        corridor_y_offset=args.get("corridor_y_offset_m", 3.0),
        add_slack_pct=args.get("add_slack_pct", 0.10),
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


HANDLERS = {
    "analyze_dxf": handle_analyze_dxf,
    "calculate_layout": handle_calculate_layout,
    "generate_layout_lisp": handle_generate_layout_lisp,
    "generate_labels_lisp": handle_generate_labels_lisp,
    "calculate_metrado": handle_calculate_metrado,
    "build_nomenclature": handle_build_nomenclature,
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
    print("MCP AutoCAD Server — modo prueba CLI")
    print("Tools disponibles:")
    for t in TOOLS:
        print(f"  - {t['name']}: {t['description'][:60]}...")

    print("\nEjemplo: calculate_layout")
    boundary = [[0,0],[10,0],[10,10],[0,10]]
    result = handle_calculate_layout({
        "boundary_points": boundary,
        "panel_width_m": 1.134,
        "panel_height_m": 2.278,
        "gap_horizontal_m": 0.5,
        "gap_vertical_m": 2.5,
        "num_groups": 1,
    })
    print(result)


if __name__ == "__main__":
    if "--cli" in sys.argv:
        run_cli()
    else:
        import asyncio
        asyncio.run(run_mcp_server())
