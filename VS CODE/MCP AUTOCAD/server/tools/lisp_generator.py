"""
Genera código AutoLISP dinámico desde Python.
Python calcula las posiciones → LISP solo dibuja (entmake).
Compatible con AutoCAD LT (sin vlax, sin COM).
"""
from pathlib import Path
from datetime import datetime


GENERATED_DIR = Path(__file__).parent.parent.parent / "lisp" / "generated"


def _header(title: str) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f""";; ============================================================
;; GENERADO AUTOMÁTICAMENTE — {title}
;; {ts} — NO EDITAR MANUALMENTE
;; ============================================================\n"""


def generate_panel_layout(
    placements: list[dict],
    block_name: str,
    offset_x: float,
    offset_y: float,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
    scale_z: float = 1.0,
    layer_prefix: str = "GD",
    output_filename: str = "layout_paneles.lsp",
) -> Path:
    """
    Genera .lsp que inserta bloques de mesas en las posiciones calculadas por Python.
    Cada GD va en un layer separado (GD1, GD2, ...).
    """
    lines = [_header("LAYOUT DE PANELES SOLARES")]
    lines.append("(defun c:InsertarPaneles ()")
    lines.append('  (setvar "CMDECHO" 0)')
    lines.append('  (setvar "OSMODE" 0)')
    lines.append(f'  (princ "\\n[INSERTANDO {len(placements)} PANELES...]")')

    current_group = None
    for p in placements:
        gd = p["group"]
        # Posición de inserción = posición calculada - offset del bloque
        ix = p["x"] - offset_x
        iy = p["y"] - offset_y

        if gd != current_group:
            layer_name = f"{layer_prefix}{gd}"
            lines.append(f'\n  ;; ── GD {gd} ──')
            lines.append(f'  (command "_LAYER" "_Make" "{layer_name}" "")')
            lines.append(f'  (setvar "CLAYER" "{layer_name}")')
            current_group = gd

        lines.append(f"  (entmake (list")
        lines.append(f'    (cons 0  "INSERT")')
        lines.append(f'    (cons 8  "{layer_prefix}{gd}")')
        lines.append(f'    (cons 2  "{block_name}")')
        lines.append(f"    (cons 10 (list {ix:.4f} {iy:.4f} 0.0))")
        lines.append(f"    (cons 41 {scale_x})")
        lines.append(f"    (cons 42 {scale_y})")
        lines.append(f"    (cons 43 {scale_z})))")

    lines.append(f'\n  (princ "\\n✓ {len(placements)} paneles insertados")')
    lines.append('  (setvar "CMDECHO" 1)')
    lines.append("  (princ)")
    lines.append(")\n")
    lines.append("(c:InsertarPaneles)")

    out_path = GENERATED_DIR / output_filename
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def generate_string_labels(
    panel_positions: list[dict],
    panels_per_string: int,
    inversores_config: list[dict],
    layer_name: str = "STRINGS_TEXTOS",
    text_height: float = 0.3,
    output_filename: str = "labels_strings.lsp",
) -> Path:
    """
    Genera .lsp que crea textos con nomenclatura I{n}S{n}
    posicionados automáticamente sobre cada grupo de paneles.
    inversores_config = [{"inversor": 1, "mppt": 1, "strings": 2}, ...]
    """
    lines = [_header("ETIQUETAS DE STRINGS")]
    lines.append("(defun c:EtiquetarStrings ()")
    lines.append('  (setvar "CMDECHO" 0)')
    lines.append(f'  (command "_LAYER" "_Make" "{layer_name}" "")')
    lines.append(f'  (setvar "CLAYER" "{layer_name}")')

    label_idx = 0
    for inv_cfg in inversores_config:
        inv = inv_cfg["inversor"]
        mppt = inv_cfg.get("mppt", None)
        n_strings = inv_cfg["strings"]
        for s in range(1, n_strings + 1):
            if label_idx >= len(panel_positions):
                break
            pos = panel_positions[label_idx * panels_per_string]
            tx = pos["x"]
            ty = pos["y"]
            tag = f"I{inv}S{s}" if mppt is None else f"I{inv}M{mppt}S{s}"
            lines.append(f"  (entmake (list")
            lines.append(f'    (cons 0  "TEXT")')
            lines.append(f'    (cons 8  "{layer_name}")')
            lines.append(f"    (cons 10 (list {tx:.4f} {ty:.4f} 0.0))")
            lines.append(f"    (cons 40 {text_height})")
            lines.append(f'    (cons 1  "{tag}")))')
            label_idx += 1

    lines.append('  (setvar "CMDECHO" 1)')
    lines.append("  (princ)")
    lines.append(")\n")
    lines.append("(c:EtiquetarStrings)")

    out_path = GENERATED_DIR / output_filename
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def generate_corridor_lines(
    groups: list[dict],
    corridor_offset_y: float = 3.0,
    layer_name: str = "CORREDORES_DC",
    output_filename: str = "corredores.lsp",
) -> Path:
    """
    Genera .lsp con líneas de corredor eléctrico bajo cada GD.
    groups = [{"group": 1, "min_x": ..., "max_x": ..., "base_y": ...}, ...]
    """
    lines = [_header("CORREDORES ELÉCTRICOS DC")]
    lines.append("(defun c:DibujarCorredores ()")
    lines.append('  (setvar "CMDECHO" 0)')
    lines.append(f'  (command "_LAYER" "_Make" "{layer_name}" "")')
    lines.append(f'  (setvar "CLAYER" "{layer_name}")')

    for g in groups:
        y_corr = g["base_y"] - corridor_offset_y
        lines.append(f"\n  ;; Corredor GD{g['group']}")
        lines.append(f"  (command \"_LINE\"")
        lines.append(f"    (list {g['min_x']:.4f} {y_corr:.4f})")
        lines.append(f"    (list {g['max_x']:.4f} {y_corr:.4f})")
        lines.append(f'    "")')

    lines.append('  (setvar "CMDECHO" 1)')
    lines.append("  (princ)")
    lines.append(")\n")
    lines.append("(c:DibujarCorredores)")

    out_path = GENERATED_DIR / output_filename
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path
