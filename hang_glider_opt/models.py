from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DesignResult:
    airfoil_name: str
    reflex_deg: float
    span_m: float
    root_chord_m: float
    taper: float
    tip_chord_m: float
    sweep_deg: float
    washout_deg: float
    dihedral_deg: float
    area_m2: float
    mac_m: float
    cg_x_m: float
    cg_fraction_mac: float
    speed_mps: float
    alpha_deg: float
    total_mass_kg: float
    lift_N: float
    drag_N: float
    moment_Nm: float
    CL: float
    CD: float
    Cm: float
    Cma: float
    sink_rate_mps: float
    estimated_time_from_60ft_s: float
