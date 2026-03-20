from __future__ import annotations

from typing import Optional

import aerosandbox as asb

from .aircraft import make_airplane
from .config import (
    ALPHA_BOUNDS_DEG,
    CG_FRACTION_BOUNDS,
    DIHEDRAL_BOUNDS_DEG,
    DROP_HEIGHT_M,
    MIN_STATIC_STABILITY_CMA,
    ROOT_CHORD_BOUNDS_M,
    SPAN_BOUNDS_M,
    SWEEP_BOUNDS_DEG,
    TAPER_BOUNDS,
    VELOCITY_BOUNDS_MPS,
    VERBOSE,
    WASHOUT_BOUNDS_DEG,
)
from .geometry import mean_aerodynamic_chord, total_mass, trapezoid_area
from .models import DesignResult


def solve_one_case(
    airfoil_name: str,
    airfoil: asb.Airfoil,
    reflex_deg: float,
) -> Optional[DesignResult]:
    """
    Optimize one continuous geometry/trim problem for a fixed airfoil and fixed reflex angle.
    """
    opti = asb.Opti()

    # Design variables
    span_m = opti.variable(init_guess=0.70, lower_bound=SPAN_BOUNDS_M[0], upper_bound=SPAN_BOUNDS_M[1])
    root_chord_m = opti.variable(init_guess=0.18, lower_bound=ROOT_CHORD_BOUNDS_M[0], upper_bound=ROOT_CHORD_BOUNDS_M[1])
    taper = opti.variable(init_guess=0.55, lower_bound=TAPER_BOUNDS[0], upper_bound=TAPER_BOUNDS[1])
    sweep_deg = opti.variable(init_guess=20.0, lower_bound=SWEEP_BOUNDS_DEG[0], upper_bound=SWEEP_BOUNDS_DEG[1])
    washout_deg = opti.variable(init_guess=3.0, lower_bound=WASHOUT_BOUNDS_DEG[0], upper_bound=WASHOUT_BOUNDS_DEG[1])
    dihedral_deg = opti.variable(init_guess=2.0, lower_bound=DIHEDRAL_BOUNDS_DEG[0], upper_bound=DIHEDRAL_BOUNDS_DEG[1])

    # Derived geometry
    area_m2 = trapezoid_area(span_m, root_chord_m, taper)
    mac_m = mean_aerodynamic_chord(root_chord_m, taper)
    tip_chord_m = root_chord_m * taper

    # CG variable as fraction of MAC
    cg_fraction_mac = opti.variable(
        init_guess=0.18,
        lower_bound=CG_FRACTION_BOUNDS[0],
        upper_bound=CG_FRACTION_BOUNDS[1],
    )
    cg_x_m = cg_fraction_mac * mac_m

    # Flight state variables
    V = opti.variable(init_guess=4.0, lower_bound=VELOCITY_BOUNDS_MPS[0], upper_bound=VELOCITY_BOUNDS_MPS[1])
    alpha_deg = opti.variable(init_guess=6.0, lower_bound=ALPHA_BOUNDS_DEG[0], upper_bound=ALPHA_BOUNDS_DEG[1])

    # Build aircraft
    airplane, _, _ = make_airplane(
        airfoil=airfoil,
        reflex_deg=reflex_deg,
        span_m=span_m,
        root_chord_m=root_chord_m,
        taper=taper,
        sweep_deg=sweep_deg,
        washout_deg=washout_deg,
        dihedral_deg=dihedral_deg,
        cg_x_m=cg_x_m,
    )

    mass_kg = total_mass(area_m2)
    weight_N = mass_kg * 9.81

    op_point = asb.OperatingPoint(
        velocity=V,
        alpha=alpha_deg,
        beta=0.0,
        p=0.0,
        q=0.0,
        r=0.0,
    )

    # LiftingLine is the best documented choice here:
    # nonlinear and includes viscous effects based on 2D data.
    analysis = asb.LiftingLine(
        airplane=airplane,
        op_point=op_point,
        xyz_ref=[cg_x_m, 0.0, 0.0],
        run_symmetric_if_possible=False,
        spanwise_resolution=10,
    )

    aero = analysis.run_with_stability_derivatives(alpha=True, beta=False, p=False, q=False, r=False)

    # Trim constraints
    opti.subject_to(aero["L"] == weight_N)     # shallow-glide approximation
    opti.subject_to(aero["m_b"] == 0.0)        # pitch trim about CG
    opti.subject_to(aero["Cma"] <= MIN_STATIC_STABILITY_CMA)

    # Geometry sanity constraints
    opti.subject_to(tip_chord_m >= 0.04)
    opti.subject_to(area_m2 >= 0.03)
    opti.subject_to(area_m2 <= 0.20)

    # Keep the wing reasonably slender but printable
    aspect_ratio = span_m**2 / area_m2
    opti.subject_to(aspect_ratio >= 3.0)
    opti.subject_to(aspect_ratio <= 14.0)

    # Objective: estimated sink rate for shallow steady glide
    # tan(gamma) ~= D/L ~= D/W, so sink ~= V * D / W
    sink_rate_mps = V * aero["D"] / weight_N

    # Small regularization terms keep ugly edge solutions away
    reg = 1e-3 * (
        (washout_deg - 3.0) ** 2
        + (dihedral_deg - 2.0) ** 2
        + (sweep_deg - 20.0) ** 2 / 100
    )

    opti.minimize(sink_rate_mps + reg)

    # Solver options
    p_opts = {}
    s_opts = {
        "max_iter": 500,
        "print_level": 0,
    }

    try:
        opti.solver("ipopt", {"ipopt": s_opts, **p_opts})
        sol = opti.solve(verbose=False)
    except Exception as e:
        if VERBOSE:
            print(f"[FAIL] {airfoil_name:10s} reflex={reflex_deg:+.1f} deg -> {e}")
        return None

    # Evaluate solved values
    result = DesignResult(
        airfoil_name=airfoil_name,
        reflex_deg=reflex_deg,
        span_m=float(sol(span_m)),
        root_chord_m=float(sol(root_chord_m)),
        taper=float(sol(taper)),
        tip_chord_m=float(sol(tip_chord_m)),
        sweep_deg=float(sol(sweep_deg)),
        washout_deg=float(sol(washout_deg)),
        dihedral_deg=float(sol(dihedral_deg)),
        area_m2=float(sol(area_m2)),
        mac_m=float(sol(mac_m)),
        cg_x_m=float(sol(cg_x_m)),
        cg_fraction_mac=float(sol(cg_fraction_mac)),
        speed_mps=float(sol(V)),
        alpha_deg=float(sol(alpha_deg)),
        total_mass_kg=float(sol(mass_kg)),
        lift_N=float(sol(aero["L"])),
        drag_N=float(sol(aero["D"])),
        moment_Nm=float(sol(aero["m_b"])),
        CL=float(sol(aero["CL"])),
        CD=float(sol(aero["CD"])),
        Cm=float(sol(aero["Cm"])),
        Cma=float(sol(aero["Cma"])),
        sink_rate_mps=float(sol(sink_rate_mps)),
        estimated_time_from_60ft_s=float(DROP_HEIGHT_M / sol(sink_rate_mps)),
    )

    if VERBOSE:
        print(
            f"[OK]   {airfoil_name:10s} reflex={reflex_deg:+.1f} deg | "
            f"sink={result.sink_rate_mps:.3f} m/s | "
            f"time60ft={result.estimated_time_from_60ft_s:.2f} s | "
            f"span={result.span_m:.3f} m area={result.area_m2:.4f} m^2 | "
            f"Cma={result.Cma:.4f}"
        )

    return result
