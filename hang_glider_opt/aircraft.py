from __future__ import annotations

import aerosandbox as asb
import aerosandbox.numpy as np

from .config import ELEVON_HINGE_POINT_FRACTION, ELEVON_START_SPAN_FRACTION
from .geometry import mean_aerodynamic_chord, trapezoid_area


def make_airplane(
    airfoil: asb.Airfoil,
    reflex_deg: float,
    span_m,
    root_chord_m,
    taper,
    sweep_deg,
    washout_deg,
    dihedral_deg,
    cg_x_m,
) -> tuple[asb.Airplane, float, float]:
    """
    Build a symmetric tailless wing with a fixed reflexed elevon over the outer panel.
    Returns (airplane, area_m2, mac_m)
    """
    tip_chord_m = root_chord_m * taper
    area_m2 = trapezoid_area(span_m, root_chord_m, taper)
    mac_m = mean_aerodynamic_chord(root_chord_m, taper)

    half_span = span_m / 2
    elevon_start_y = half_span * ELEVON_START_SPAN_FRACTION

    mid_chord_m = root_chord_m + (tip_chord_m - root_chord_m) * ELEVON_START_SPAN_FRACTION
    mid_twist_deg = -washout_deg * ELEVON_START_SPAN_FRACTION

    mid_sweep_dx = elevon_start_y * np.tan(np.radians(sweep_deg))
    mid_z = elevon_start_y * np.tan(np.radians(dihedral_deg))

    sweep_dx = half_span * np.tan(np.radians(sweep_deg))
    tip_z = half_span * np.tan(np.radians(dihedral_deg))

    # ControlSurface is attached to WingXSec via control_surfaces=[].
    # Deflection is documented as down-positive, so negative is reflex/up.
    elevon = asb.ControlSurface(
        name="elevon",
        symmetric=True,
        deflection=reflex_deg,
        hinge_point=ELEVON_HINGE_POINT_FRACTION,
        trailing_edge=True,
    )

    wing = asb.Wing(
        name="Main Wing",
        symmetric=True,
        xsecs=[
            asb.WingXSec(
                xyz_le=[0.0, 0.0, 0.0],
                chord=root_chord_m,
                twist=0.0,
                airfoil=airfoil,
                control_surfaces=[],
            ),
            asb.WingXSec(
                xyz_le=[mid_sweep_dx, elevon_start_y, mid_z],
                chord=mid_chord_m,
                twist=mid_twist_deg,
                airfoil=airfoil,
                control_surfaces=[elevon],
            ),
            asb.WingXSec(
                xyz_le=[sweep_dx, half_span, tip_z],
                chord=tip_chord_m,
                twist=-washout_deg,
                airfoil=airfoil,
                control_surfaces=[elevon],
            ),
        ],
    )

    airplane = asb.Airplane(
        name="DropWing",
        xyz_ref=[cg_x_m, 0.0, 0.0],  # moments evaluated about CG
        wings=[wing],
        s_ref=area_m2,
        c_ref=mac_m,
        b_ref=span_m,
    )

    return airplane, area_m2, mac_m
