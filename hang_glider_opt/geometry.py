from __future__ import annotations

from .config import (
    ELECTRONICS_MASS_KG,
    FIXED_NON_ELECTRONICS_MASS_KG,
    WING_AREAL_DENSITY_KG_PER_M2,
)


def trapezoid_area(span_m: float, root_chord_m: float, taper: float) -> float:
    tip_chord_m = root_chord_m * taper
    return span_m * 0.5 * (root_chord_m + tip_chord_m)


def mean_aerodynamic_chord(root_chord_m: float, taper: float) -> float:
    # Standard trapezoidal wing MAC
    return (2 / 3) * root_chord_m * (1 + taper + taper**2) / (1 + taper)


def wing_structure_mass(area_m2: float) -> float:
    return area_m2 * WING_AREAL_DENSITY_KG_PER_M2


def total_mass(area_m2: float) -> float:
    return ELECTRONICS_MASS_KG + FIXED_NON_ELECTRONICS_MASS_KG + wing_structure_mass(area_m2)
