from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional

import aerosandbox as asb

from .config import (
    ALPHA_BOUNDS_DEG,
    CG_FRACTION_BOUNDS,
    DIHEDRAL_BOUNDS_DEG,
    DROP_HEIGHT_M,
    FORCE_REGENERATE_RESULT_CACHE,
    LAUNCH_SPEED_MPS,
    MIN_REMAINING_ALTITUDE_M,
    MIN_STATIC_STABILITY_CMA,
    OBJECTIVE_MODE,
    REFLEX_CANDIDATES_DEG,
    RESULT_CACHE_DIR,
    ROOT_CHORD_BOUNDS_M,
    SPAN_BOUNDS_M,
    SWEEP_BOUNDS_DEG,
    TAPER_BOUNDS,
    USE_RESULT_CACHE,
    VELOCITY_BOUNDS_MPS,
    WASHOUT_BOUNDS_DEG,
)
from .models import DesignResult


def _airfoil_geometry_fingerprint(airfoil: asb.Airfoil) -> str:
    rows = [f"{float(x):.8f},{float(y):.8f}" for x, y in airfoil.coordinates]
    return hashlib.sha1("\n".join(rows).encode("utf-8")).hexdigest()[:16]


def _config_signature() -> Dict[str, Any]:
    return {
        "bounds": {
            "span": SPAN_BOUNDS_M,
            "root_chord": ROOT_CHORD_BOUNDS_M,
            "taper": TAPER_BOUNDS,
            "sweep": SWEEP_BOUNDS_DEG,
            "washout": WASHOUT_BOUNDS_DEG,
            "dihedral": DIHEDRAL_BOUNDS_DEG,
            "cg_frac": CG_FRACTION_BOUNDS,
            "velocity": VELOCITY_BOUNDS_MPS,
            "alpha": ALPHA_BOUNDS_DEG,
        },
        "min_static_stability_cma": MIN_STATIC_STABILITY_CMA,
        "drop_height_m": DROP_HEIGHT_M,
        "objective_mode": OBJECTIVE_MODE,
        "launch_speed_mps": LAUNCH_SPEED_MPS,
        "min_remaining_altitude_m": MIN_REMAINING_ALTITUDE_M,
        "reflex_candidates_deg": REFLEX_CANDIDATES_DEG,
    }


def case_cache_key(airfoil_name: str, reflex_deg: float, airfoil: asb.Airfoil) -> str:
    payload = {
        "airfoil_name": airfoil_name,
        "reflex_deg": float(reflex_deg),
        "airfoil_geom": _airfoil_geometry_fingerprint(airfoil),
        "config": _config_signature(),
    }
    encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha1(encoded).hexdigest()[:16]


def _cache_path(case_key: str) -> Path:
    return RESULT_CACHE_DIR / f"{case_key}.json"


def load_cached_result(case_key: str) -> Optional[DesignResult]:
    if not USE_RESULT_CACHE or FORCE_REGENERATE_RESULT_CACHE:
        return None

    path = _cache_path(case_key)
    if not path.exists() or path.stat().st_size <= 0:
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return DesignResult.from_dict(data)
    except Exception:
        return None


def save_cached_result(case_key: str, result: DesignResult) -> None:
    if not USE_RESULT_CACHE:
        return

    RESULT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(case_key)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, indent=2)
