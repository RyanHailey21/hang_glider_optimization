from __future__ import annotations

import shutil
from typing import Dict, List

import aerosandbox as asb

from .airfoil_loader import load_and_prepare_airfoil
from .config import (
    AIRFOIL_FILES,
    GENERATE_XFOIL_POLARS,
    PRECOMPUTE_POLARS_ONLY,
    REFLEX_CANDIDATES_DEG,
    VERBOSE,
    XFOIL_COMMAND,
)
from .models import DesignResult
from .reporting import print_result, print_top_results
from .solver import solve_one_case


def main() -> None:
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

    # 2) Loop over fixed reflex candidates and solve one continuous optimization each time.
    results: List[DesignResult] = []
    for airfoil_name, airfoil in airfoils.items():
        for reflex_deg in REFLEX_CANDIDATES_DEG:
            result = solve_one_case(
                airfoil_name=airfoil_name,
                airfoil=airfoil,
                reflex_deg=reflex_deg,
            )
            if result is not None:
                results.append(result)

    if not results:
        raise RuntimeError("No feasible design found. Loosen bounds or check airfoil/XFoil setup.")

    # 3) Pick the best by estimated sink rate.
    best = min(results, key=lambda r: r.sink_rate_mps)
    print_result(best)

    # 4) Optional: print ranked shortlist
    print_top_results(results, n=5)
