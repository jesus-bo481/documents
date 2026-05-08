"""
Lógica eléctrica para proyectos GD/PRGD en Colombia.
Strings, MPPT, inversores, nomenclaturas, sizing básico.
"""
from dataclasses import dataclass, field
from math import ceil


@dataclass
class PanelConfig:
    model: str
    width_m: float
    height_m: float
    voc: float        # V
    vmp: float        # V
    isc: float        # A
    imp: float        # A
    power_wp: float   # Wp


@dataclass
class InverterConfig:
    model: str
    power_ac_kw: float
    num_mppt: int
    max_strings_per_mppt: int
    v_mppt_min: float
    v_mppt_max: float
    v_max_input: float
    i_max_per_mppt: float


@dataclass
class StringConfig:
    inversor_id: int
    mppt_id: int
    string_id: int
    panels_in_series: int
    panel: PanelConfig

    @property
    def tag(self) -> str:
        return f"I{self.inversor_id}M{self.mppt_id}S{self.string_id}"

    @property
    def voc_string(self) -> float:
        return self.panels_in_series * self.panel.voc

    @property
    def vmp_string(self) -> float:
        return self.panels_in_series * self.panel.vmp

    @property
    def total_panels(self) -> int:
        return self.panels_in_series


@dataclass
class GDGroup:
    group_id: int
    inversor_id: int
    strings: list[StringConfig] = field(default_factory=list)

    @property
    def total_panels(self) -> int:
        return sum(s.total_panels for s in self.strings)

    @property
    def tag(self) -> str:
        return f"GD{self.group_id}"


def calculate_panels_per_string(
    panel: PanelConfig,
    inverter: InverterConfig,
    temp_min_c: float = 5.0,
    temp_coef_voc: float = -0.0029,
) -> int:
    """
    Calcula cantidad de paneles en serie por string.
    Limita por Vmax del inversor con temperatura mínima (máxima tensión).
    temp_coef_voc en V/°C (negativo).
    """
    delta_t = temp_min_c - 25.0
    voc_corrected = panel.voc * (1 + temp_coef_voc * delta_t)
    max_panels = int(inverter.v_max_input / voc_corrected)
    # También verificar que Vmp_string esté dentro del rango MPPT
    for n in range(max_panels, 0, -1):
        vmp_str = n * panel.vmp
        if inverter.v_mppt_min <= vmp_str <= inverter.v_mppt_max:
            return n
    return max_panels


def calculate_strings_per_mppt(
    panel: PanelConfig,
    inverter: InverterConfig,
    panels_in_series: int,
) -> int:
    """
    Strings en paralelo por MPPT limitado por corriente máxima.
    """
    return min(
        inverter.max_strings_per_mppt,
        int(inverter.i_max_per_mppt / panel.isc),
    )


def build_nomenclature(
    num_inversores: int,
    num_mppt_per_inv: int,
    num_strings_per_mppt: int,
) -> list[str]:
    """Genera lista completa de tags IxMyS z para un proyecto."""
    tags = []
    for inv in range(1, num_inversores + 1):
        for mppt in range(1, num_mppt_per_inv + 1):
            for s in range(1, num_strings_per_mppt + 1):
                tags.append(f"I{inv}M{mppt}S{s}")
    return tags


def estimate_dc_cable_length(
    panel_positions: list[dict],
    panels_per_string: int,
    corridor_y_offset: float = 3.0,
    add_slack_pct: float = 0.10,
) -> list[dict]:
    """
    Estimación de longitud de cable DC por string.
    Asume que el corredor está a corridor_y_offset metros bajo cada fila.
    """
    results = []
    total = len(panel_positions)
    n_strings = ceil(total / panels_per_string)

    for s_idx in range(n_strings):
        start = s_idx * panels_per_string
        end = min(start + panels_per_string, total)
        string_panels = panel_positions[start:end]

        if not string_panels:
            continue

        # Longitud positiva: del último panel al primero (recorre la mesa)
        x_vals = [p["x"] for p in string_panels]
        y_vals = [p["y"] for p in string_panels]
        span_x = max(x_vals) - min(x_vals)
        base_y = min(y_vals)
        drop_to_corridor = base_y - corridor_y_offset

        len_pos = span_x + abs(drop_to_corridor)
        len_neg = len_pos  # cable negativo simétrico

        total_len = (len_pos + len_neg) * (1 + add_slack_pct)

        results.append({
            "string_idx": s_idx + 1,
            "len_positive_m": round(len_pos, 2),
            "len_negative_m": round(len_neg, 2),
            "total_m": round(total_len, 2),
        })

    return results
