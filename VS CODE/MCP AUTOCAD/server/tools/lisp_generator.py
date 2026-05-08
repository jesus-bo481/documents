"""
Genera código AutoLISP dinámico desde Python.
Python calcula las posiciones → LISP solo dibuja (entmake).
Compatible con AutoCAD LT (sin vlax, sin COM).

Dos modos de inserción:
  Bloque-mesa  : cada placement = 1 INSERT del bloque (bloque ya es la mesa completa).
  Bloque-panel : cada placement = N×M INSERTs individuales del módulo.
                 panels_wide/high > 0 activa este modo.
                 El insert point del bloque se calcula con blk_offset_x/y.
"""
from pathlib import Path
from datetime import datetime


GENERATED_DIR = Path(__file__).parent.parent.parent / "lisp" / "generated"


def _header(title: str) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    return (
        f";; ============================================================\n"
        f";; GENERADO AUTOMATICAMENTE -- {title}\n"
        f";; {ts} -- NO EDITAR MANUALMENTE\n"
        f";; ============================================================\n"
    )


def _entmake_insert(layer: str, block: str, ix: float, iy: float) -> str:
    return (
        f"  (entmake (list\n"
        f'    (cons 0  "INSERT")\n'
        f'    (cons 8  "{layer}")\n'
        f'    (cons 2  "{block}")\n'
        f"    (cons 10 (list {ix:.4f} {iy:.4f} 0.0))\n"
        f"    (cons 41 1.0)(cons 42 1.0)(cons 43 1.0)))\n"
    )


def generate_panel_layout(
    placements: list[dict],
    block_name: str,
    offset_x: float = 0.0,
    offset_y: float = 0.0,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
    layer_prefix: str = "GD",
    output_filename: str = "layout_paneles.lsp",
    # Parámetros para modo bloque-panel (paneles individuales por mesa)
    panels_wide: int = 0,
    panels_high: int = 0,
    panel_w: float = 0.0,
    panel_h: float = 0.0,
    module_gap: float = 0.04,
    blk_offset_x: float = 0.0,
    blk_offset_y: float = 0.0,
) -> Path:
    """
    Genera .lsp que inserta bloques en las posiciones calculadas.

    Modo bloque-mesa (panels_wide=0):
      Cada placement → 1 INSERT del bloque.
      offset_x/y = offset del punto de inserción respecto a la esquina del bloque.

    Modo bloque-panel (panels_wide > 0):
      Cada placement → panels_wide * panels_high INSERT del módulo.
      blk_offset_x/y = distancia del insert point del bloque a la esquina izq-inf del panel.
      panel_w/h = dimensiones del panel en metros.
      module_gap = separación entre módulos dentro de la mesa (0.04 m).
    """
    multi_panel = panels_wide > 0 and panels_high > 0 and panel_w > 0 and panel_h > 0

    # Contar por grupo para el header
    by_group: dict[int, int] = {}
    for p in placements:
        g = p["group"]
        by_group[g] = by_group.get(g, 0) + 1

    total_mesas = len(placements)
    total_inserts = total_mesas * (panels_wide * panels_high if multi_panel else 1)

    lines: list[str] = [_header("LAYOUT DE PANELES SOLARES")]
    lines.append(f";; Mesas: {total_mesas}  |  Inserts: {total_inserts}  |  Bloque: {block_name}")
    if multi_panel:
        lines.append(f";; Mesa: {panels_wide}x{panels_high} modulos  "
                     f"module_gap={module_gap} m")
    lines.append("")

    # Agrupar placements por GD para generar un defun limpio por cada uno
    groups_sorted = sorted(by_group.keys())
    placements_by_group: dict[int, list[dict]] = {g: [] for g in groups_sorted}
    for p in placements:
        placements_by_group[p["group"]].append(p)

    for gd in groups_sorted:
        layer = f"{layer_prefix}{gd}"
        gd_placements = placements_by_group[gd]
        n_mesas = len(gd_placements)
        n_inserts = n_mesas * (panels_wide * panels_high if multi_panel else 1)

        lines.append(f"\n;; ── GD {gd}: {n_mesas} mesas, {n_inserts} inserts ──────────")
        lines.append(f"(defun c:Insertar{layer_prefix}{gd} ()")
        lines.append('  (setvar "CMDECHO" 0)')
        lines.append(f'  (command "_LAYER" "_Make" "{layer}" "")')
        lines.append(f'  (setvar "CLAYER" "{layer}")')
        lines.append(f'  (princ "\\n[{layer}] insertando {n_inserts} bloques...")')

        for m_idx, p in enumerate(gd_placements):
            mx, my = p["x"], p["y"]
            lines.append(f"\n  ;; Mesa {m_idx + 1}/{n_mesas}  ({mx:.2f}, {my:.2f})")

            if multi_panel:
                for row in range(panels_high):
                    for col in range(panels_wide):
                        px = mx + col * (panel_w + module_gap)
                        py = my + row * (panel_h + module_gap)
                        ix = px + blk_offset_x
                        iy = py + blk_offset_y
                        lines.append(_entmake_insert(layer, block_name, ix, iy))
            else:
                ix = mx - offset_x
                iy = my - offset_y
                lines.append(
                    f"  (entmake (list\n"
                    f'    (cons 0  "INSERT")\n'
                    f'    (cons 8  "{layer}")\n'
                    f'    (cons 2  "{block_name}")\n'
                    f"    (cons 10 (list {ix:.4f} {iy:.4f} 0.0))\n"
                    f"    (cons 41 {scale_x})(cons 42 {scale_y})(cons 43 1.0)))\n"
                )

        lines.append(f'\n  (princ "\\n[{layer}] OK {n_inserts} bloques insertados")')
        lines.append('  (setvar "CMDECHO" 1)')
        lines.append("  (princ)")
        lines.append(")\n")

    # Función maestra que llama a todas
    lines.append("(defun c:InsertarTodo ()")
    for g in groups_sorted:
        lines.append(f"  (c:Insertar{layer_prefix}{g})")
    lines.append('  (princ "\\n=== Layout completo ===")')
    lines.append("  (princ)")
    lines.append(")\n")
    lines.append("(c:InsertarTodo)")

    out_path = GENERATED_DIR / output_filename
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def _write_group_defun(
    lines: list[str],
    placements: list[dict],
    layer: str,
    defun_name: str,
    block_name: str,
    panels_wide: int,
    panels_high: int,
    panel_w: float,
    panel_h: float,
    module_gap: float,
    blk_offset_x: float,
    blk_offset_y: float,
) -> None:
    """Escribe un defun LISP completo que inserta un grupo de mesas en 'layer'."""
    n_mesas = len(placements)
    n_inserts = n_mesas * panels_wide * panels_high

    lines.append(f"(defun c:{defun_name} ()")
    lines.append('  (setvar "CMDECHO" 0)')
    lines.append(f'  (command "_LAYER" "_Make" "{layer}" "")')
    lines.append(f'  (setvar "CLAYER" "{layer}")')
    lines.append(f'  (princ "\\n[{layer}] insertando {n_inserts} bloques...")')

    for m_idx, p in enumerate(placements):
        mx, my = p["x"], p["y"]
        lines.append(f"\n  ;; Mesa {m_idx + 1}/{n_mesas}  ({mx:.2f}, {my:.2f})")
        for row in range(panels_high):
            for col in range(panels_wide):
                ix = mx + col * (panel_w + module_gap) + blk_offset_x
                iy = my + row * (panel_h + module_gap) + blk_offset_y
                lines.append(_entmake_insert(layer, block_name, ix, iy))

    lines.append(f'\n  (princ "\\n[{layer}] OK {n_inserts} bloques insertados")')
    lines.append('  (setvar "CMDECHO" 1)')
    lines.append("  (princ)")
    lines.append(")\n")


def generate_hybrid_layout(
    primary_placements: list[dict],
    fallback_placements: list[dict],
    block_name: str,
    panel_w: float,
    panel_h: float,
    primary_wide: int,
    primary_high: int,
    fallback_wide: int,
    fallback_high: int,
    module_gap: float = 0.04,
    blk_offset_x: float = 0.0,
    blk_offset_y: float = 0.0,
    layer_prefix: str = "GD",
    output_filename: str = "layout_hibrido.lsp",
) -> Path:
    """
    Genera un .lsp combinado con dos configuraciones de mesa.
    Mesas primarias   -> layer {prefix}{gd}
    Mesas secundarias -> layer {prefix}{gd}_{fallback_wide}x{fallback_high}

    Cada GD obtiene sus propios defun separados.
    c:InsertarTodo ejecuta todo en secuencia.
    """
    fallback_tag = f"{fallback_wide}x{fallback_high}"

    # Agrupar por GD
    def by_group(placements: list[dict]) -> dict[int, list[dict]]:
        groups: dict[int, list[dict]] = {}
        for p in placements:
            groups.setdefault(p["group"], []).append(p)
        return groups

    p_groups = by_group(primary_placements)
    f_groups = by_group(fallback_placements)
    all_gd = sorted(set(list(p_groups.keys()) + list(f_groups.keys())))

    n_p = len(primary_placements)
    n_f = len(fallback_placements)
    panels_p = n_p * primary_wide * primary_high
    panels_f = n_f * fallback_wide * fallback_high

    lines: list[str] = [_header("LAYOUT HIBRIDO")]
    lines.append(f";; Primaria  {primary_wide}x{primary_high}: {n_p} mesas = {panels_p} paneles")
    lines.append(f";; Secundaria {fallback_tag}: {n_f} mesas = {panels_f} paneles")
    lines.append(f";; TOTAL: {n_p + n_f} mesas, {panels_p + panels_f} paneles")
    lines.append("")

    defun_names: list[str] = []

    for gd in all_gd:
        # Mesas primarias de este GD
        if gd in p_groups and p_groups[gd]:
            layer = f"{layer_prefix}{gd}"
            dname = f"Insertar{layer_prefix}{gd}"
            lines.append(f"\n;; -- GD{gd} primaria {primary_wide}x{primary_high} --")
            _write_group_defun(
                lines, p_groups[gd], layer, dname, block_name,
                primary_wide, primary_high, panel_w, panel_h,
                module_gap, blk_offset_x, blk_offset_y,
            )
            defun_names.append(dname)

        # Mesas secundarias de este GD
        if gd in f_groups and f_groups[gd]:
            layer_f = f"{layer_prefix}{gd}_{fallback_tag}"
            dname_f = f"Insertar{layer_prefix}{gd}_{fallback_tag}"
            lines.append(f"\n;; -- GD{gd} secundaria {fallback_tag} --")
            _write_group_defun(
                lines, f_groups[gd], layer_f, dname_f, block_name,
                fallback_wide, fallback_high, panel_w, panel_h,
                module_gap, blk_offset_x, blk_offset_y,
            )
            defun_names.append(dname_f)

    # Funcion maestra
    lines.append("(defun c:InsertarTodo ()")
    for dname in defun_names:
        lines.append(f"  (c:{dname})")
    lines.append(f'  (princ "\\n=== Layout hibrido: {panels_p + panels_f} paneles ===")')
    lines.append("  (princ)")
    lines.append(")\n")
    lines.append("(c:InsertarTodo)")

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
    Genera .lsp que crea textos con nomenclatura I{n}M{n}S{n}
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
    lines = [_header("CORREDORES ELECTRICOS DC")]
    lines.append("(defun c:DibujarCorredores ()")
    lines.append('  (setvar "CMDECHO" 0)')
    lines.append(f'  (command "_LAYER" "_Make" "{layer_name}" "")')
    lines.append(f'  (setvar "CLAYER" "{layer_name}")')

    for g in groups:
        y_corr = g["base_y"] - corridor_offset_y
        lines.append(f"\n  ;; Corredor GD{g['group']}")
        lines.append(f'  (command "_LINE"')
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
