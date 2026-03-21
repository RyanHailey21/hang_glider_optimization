from __future__ import annotations

from typing import List

from .config import OBJECTIVE_MODE
from .models import DesignResult


def print_result(r: DesignResult) -> None:
    print("\nBest design")
    print("-----------")
    print(f"Airfoil:              {r.airfoil_name}")
    print(f"Fixed reflex:         {r.reflex_deg:+.1f} deg")
    print(f"Span:                 {r.span_m:.3f} m")
    print(f"Root chord:           {r.root_chord_m:.3f} m")
    print(f"Tip chord:            {r.tip_chord_m:.3f} m")
    print(f"Taper ratio:          {r.taper:.3f}")
    print(f"Sweep:                {r.sweep_deg:.2f} deg")
    print(f"Washout:              {r.washout_deg:.2f} deg")
    print(f"Dihedral:             {r.dihedral_deg:.2f} deg")
    print(f"Wing area:            {r.area_m2:.4f} m^2")
    print(f"MAC:                  {r.mac_m:.4f} m")
    print(f"CG location:          {r.cg_x_m:.4f} m ({100 * r.cg_fraction_mac:.1f}% MAC)")
    print(f"Total mass:           {1000 * r.total_mass_kg:.1f} g")
    print(f"Trim speed:           {r.speed_mps:.3f} m/s")
    print(f"Trim alpha:           {r.alpha_deg:.2f} deg")
    print(f"Lift:                 {r.lift_N:.3f} N")
    print(f"Drag:                 {r.drag_N:.3f} N")
    print(f"Pitch moment:         {r.moment_Nm:.6f} Nm")
    print(f"CL / CD / Cm:         {r.CL:.4f} / {r.CD:.4f} / {r.Cm:.4f}")
    print(f"Cma:                  {r.Cma:.4f}")
    print(f"Estimated sink rate:  {r.sink_rate_mps:.3f} m/s")
    print(f"Steady time from 60ft:{r.estimated_time_from_60ft_s:.2f} s")
    print(f"Accel height loss:    {r.accel_height_loss_m:.2f} m")
    print(f"Total time proxy:     {r.estimated_total_time_from_60ft_s:.2f} s")


def print_top_results(results: List[DesignResult], n: int = 5) -> None:
    if OBJECTIVE_MODE == "drop_time_with_accel":
        ranked = sorted(results, key=lambda rr: rr.estimated_total_time_from_60ft_s, reverse=True)
    else:
        ranked = sorted(results, key=lambda rr: rr.sink_rate_mps)

    print("\nTop 5 designs")
    print("-------------")
    for i, r in enumerate(ranked[:n], start=1):
        print(
            f"{i:>2d}. {r.airfoil_name:10s} reflex={r.reflex_deg:+.1f} deg | "
            f"sink={r.sink_rate_mps:.3f} m/s | steady60ft={r.estimated_time_from_60ft_s:.2f} s | "
            f"totalProxy60ft={r.estimated_total_time_from_60ft_s:.2f} s | "
            f"span={r.span_m:.3f} m | area={r.area_m2:.4f} m^2 | "
            f"CG={100 * r.cg_fraction_mac:.1f}% MAC"
        )
