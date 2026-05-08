"""
Lectura de geometría desde archivos DXF exportados por AutoCAD LT.
Usa ezdxf — no requiere AutoCAD instalado.
"""
from pathlib import Path
from typing import Any
from .geometry import Point, Polygon, parse_polygon_from_points

try:
    import ezdxf
    from ezdxf.entities import LWPolyline, Polyline, Circle, Insert
    HAS_EZDXF = True
except ImportError:
    HAS_EZDXF = False


def _require_ezdxf():
    if not HAS_EZDXF:
        raise ImportError("ezdxf no está instalado. Ejecuta: pip install ezdxf")


def read_boundary_polygons(dxf_path: str, layer: str | None = None) -> list[Polygon]:
    """
    Lee todas las LWPOLYLINE/POLYLINE del DXF y las devuelve como Polygon.
    Si se especifica layer, filtra solo esa capa.
    """
    _require_ezdxf()
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    polygons = []

    for entity in msp:
        if layer and entity.dxf.layer != layer:
            continue
        if entity.dxftype() == "LWPOLYLINE":
            pts = [Point(x, y) for x, y, *_ in entity.get_points()]
            if len(pts) >= 3:
                polygons.append(pts)
        elif entity.dxftype() == "POLYLINE":
            pts = [Point(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
            if len(pts) >= 3:
                polygons.append(pts)

    return polygons


def read_circles(dxf_path: str, layer: str | None = None) -> list[tuple[float, float, float]]:
    """
    Lee todos los CIRCLE del DXF.
    Devuelve lista de (cx, cy, r).
    """
    _require_ezdxf()
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    circles = []

    for entity in msp:
        if layer and entity.dxf.layer != layer:
            continue
        if entity.dxftype() == "CIRCLE":
            cx = entity.dxf.center.x
            cy = entity.dxf.center.y
            r = entity.dxf.radius
            circles.append((cx, cy, r))

    return circles


def read_block_insertions(dxf_path: str, block_name: str) -> list[dict]:
    """
    Lee todas las inserciones de un bloque específico en el modelo.
    Devuelve lista de {x, y, scale_x, scale_y, rotation}.
    """
    _require_ezdxf()
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    insertions = []

    for entity in msp:
        if entity.dxftype() == "INSERT" and entity.dxf.name == block_name:
            insertions.append({
                "x": entity.dxf.insert.x,
                "y": entity.dxf.insert.y,
                "scale_x": entity.dxf.xscale if entity.dxf.hasattr("xscale") else 1.0,
                "scale_y": entity.dxf.yscale if entity.dxf.hasattr("yscale") else 1.0,
                "rotation": entity.dxf.rotation if entity.dxf.hasattr("rotation") else 0.0,
                "layer": entity.dxf.layer,
            })

    return insertions


def list_layers(dxf_path: str) -> list[str]:
    """Lista todos los layers del DXF."""
    _require_ezdxf()
    doc = ezdxf.readfile(dxf_path)
    return [layer.dxf.name for layer in doc.layers]


def list_blocks(dxf_path: str) -> list[str]:
    """Lista todos los bloques definidos en el DXF."""
    _require_ezdxf()
    doc = ezdxf.readfile(dxf_path)
    return [b.name for b in doc.blocks if not b.name.startswith("*")]


def get_dxf_summary(dxf_path: str) -> dict[str, Any]:
    """Resumen completo del DXF para diagnóstico."""
    _require_ezdxf()
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()

    entity_counts: dict[str, int] = {}
    for entity in msp:
        t = entity.dxftype()
        entity_counts[t] = entity_counts.get(t, 0) + 1

    return {
        "dxf_version": doc.dxfversion,
        "layers": list_layers(dxf_path),
        "blocks": list_blocks(dxf_path),
        "entity_counts": entity_counts,
        "total_entities": sum(entity_counts.values()),
    }
