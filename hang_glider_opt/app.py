from __future__ import annotations

import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple

import aerosandbox as asb

from .airfoil_loader import load_and_prepare_airfoil
from .config import (
    AIRFOIL_FILES,
    ELEVON_HINGE_POINT_FRACTION,
    GENERATE_XFOIL_POLARS,
    OBJECTIVE_MODE,
    PLOT_WINNER_3D,
    PLOT_WINNER_AIRFOIL,
    PLOT_WINNER_FLIGHT_PATH,
    PLOT_WINNER_POLARS,
    PRECOMPUTE_POLARS_ONLY,
    REFLEX_CANDIDATES_DEG,
    VERBOSE,
    WINNER_3D_PLOT_PATH,
    WINNER_AIRFOIL_PLOT_PATH,
    WINNER_FLIGHT_PATH_PLOT_PATH,
    WINNER_POLARS_PLOT_PATH,
    XFOIL_COMMAND,
)
from .aircraft import make_airplane
from .models import DesignResult
from .plotting import (
    save_airfoil_geometry_plot,
    save_flight_path_plot,
    save_polar_plot,
    save_wing_3d_plot,
)
from .result_cache import case_cache_key, load_cached_result, save_cached_result
from .reporting import print_result, print_top_results
from .solver import solve_one_case


def main() -> None:
    if VERBOSE:
        print(f"[INFO] Objective mode: {OBJECTIVE_MODE}")

    if GENERATE_XFOIL_POLARS and shutil.which(XFOIL_COMMAND) is None:
        raise RuntimeError(
            f"XFoil command '{XFOIL_COMMAND}' was not found on PATH. "
            "Install XFoil (or set XFOIL_COMMAND to its executable path), "
            "or set GENERATE_XFOIL_POLARS = False to run without XFoil."
        )

    # 1) Load and polarize all candidate airfoils.
    airfoils: Dict[str, asb.Airfoil] = {}
    for name, path in AIRFOIL_FILES.items():
        if VERBOSE:
            print(f"Loading airfoil '{name}' from {path}")
        airfoils[name] = load_and_prepare_airfoil(name, path)

    if PRECOMPUTE_POLARS_ONLY:
        print("\nPolar precomputation complete. Exiting before optimization.")
        return

    # 2) Solve all (airfoil, reflex) cases in parallel.
    def _solve_case(args: Tuple) -> Optional[DesignResult]:
        airfoil_name, airfoil, reflex_deg = args
        cache_key = case_cache_key(airfoil_name=airfoil_name, reflex_deg=reflex_deg, airfoil=airfoil)
        result = load_cached_result(cache_key)
        if result is not None:
            if VERBOSE:
                print(f"[CACHE] Using cached optimization result for {airfoil_name} reflex={reflex_deg:+.1f}")
            return result
        result = solve_one_case(
            airfoil_name=airfoil_name,
            airfoil=airfoil,
            reflex_deg=reflex_deg,
        )
        if result is not None:
            save_cached_result(cache_key, result)
        return result

    cases = [
        (airfoil_name, airfoil, reflex_deg)
        for airfoil_name, airfoil in airfoils.items()
        for reflex_deg in REFLEX_CANDIDATES_DEG
    ]

    results: List[DesignResult] = []
    max_workers = min(len(cases), os.cpu_count() or 4)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_solve_case, case) for case in cases]
        for future in as_completed(futures):
            try:
                result = future.result()
                if result is not None:
                    results.append(result)
            except Exception as e:
                if VERBOSE:
                    print(f"[ERROR] Unexpected exception in worker: {e}")

    if not results:
        raise RuntimeError("No feasible design found. Loosen bounds or check airfoil/XFoil setup.")

    # 3) Pick the best with the active objective mode.
    if OBJECTIVE_MODE == "drop_time_with_accel":
        best = max(results, key=lambda r: r.estimated_total_time_from_60ft_s)
    else:
        best = min(results, key=lambda r: r.sink_rate_mps)
    print_result(best)

    # 4) Optional: print ranked shortlist
    print_top_results(results, n=5)

    winning_airfoil = airfoils.get(best.airfoil_name)

    if PLOT_WINNER_AIRFOIL and winning_airfoil is not None:
        path = save_airfoil_geometry_plot(
            airfoil=winning_airfoil,
            title=f"Winning Airfoil: {best.airfoil_name} (reflex {best.reflex_deg:+.1f} deg)",
            output_path=WINNER_AIRFOIL_PLOT_PATH,
            reflex_deg=best.reflex_deg,
            hinge_x=ELEVON_HINGE_POINT_FRACTION,
        )
        print(f"Saved airfoil plot:      {path}")

    if PLOT_WINNER_3D and winning_airfoil is not None:
        winner_airplane, _, _ = make_airplane(
            airfoil=winning_airfoil,
            reflex_deg=best.reflex_deg,
            span_m=best.span_m,
            root_chord_m=best.root_chord_m,
            taper=best.taper,
            sweep_deg=best.sweep_deg,
            washout_deg=best.washout_deg,
            dihedral_deg=best.dihedral_deg,
            cg_x_m=best.cg_x_m,
        )
        path = save_wing_3d_plot(winner_airplane, best, WINNER_3D_PLOT_PATH)
        print(f"Saved 3D wing plot:      {path}")

    if PLOT_WINNER_POLARS and winning_airfoil is not None:
        path = save_polar_plot(winning_airfoil, best, WINNER_POLARS_PLOT_PATH)
        print(f"Saved polar plot:        {path}")

    if PLOT_WINNER_FLIGHT_PATH:
        path = save_flight_path_plot(best, WINNER_FLIGHT_PATH_PLOT_PATH)
        print(f"Saved flight path plot:  {path}")
