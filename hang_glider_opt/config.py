from __future__ import annotations

import pathlib

import aerosandbox.numpy as np

# ----------------------------
# User inputs / project setup
# ----------------------------

ELECTRONICS_MASS_KG = 0.103  # given by you
DROP_HEIGHT_M = 60 * 0.3048  # 60 ft

# Add your best estimate for the rest of the mass here.
# You can also make this a function of geometry if you have a better structure model.
FIXED_NON_ELECTRONICS_MASS_KG = 0.060  # battery, motors, ESCs, frame, wiring, mounts, etc.

# Very rough structure mass model coefficient:
# structure_mass ~= area * areal_density
# Tune this after you weigh one printed prototype.
WING_AREAL_DENSITY_KG_PER_M2 = 0.18

# Airfoil files: put .dat files here.
# Example expected filenames:
#   ./airfoils/mh45.dat
#   ./airfoils/mh60.dat
#   ./airfoils/fauvel.dat
AIRFOIL_DIR = pathlib.Path("./airfoils")

# Candidate airfoils to compare. These are local DAT filenames, not built-in names.
# MH45/MH60: Müller-Heinz flying wing sections — good L/D, low drag bucket
# RG15:      René Gagnon 15 — one of the best low-Re glider sections
# SD7037:    Selig-Donovan — excellent low-Re RC sailplane performance
# S5010:     Selig flying wing — reflexed, designed specifically for tailless aircraft
# E387:      Eppler 387 — classic low-Re benchmark, well characterized
AIRFOIL_FILES = {
    "mh45": AIRFOIL_DIR / "mh45.dat",
    "mh60": AIRFOIL_DIR / "mh60.dat",
    "fauvel": AIRFOIL_DIR / "fauvel.dat",
    "rg15": AIRFOIL_DIR / "rg15.dat",
    "sd7037": AIRFOIL_DIR / "sd7037.dat",
    "s5010": AIRFOIL_DIR / "s5010.dat",
    "e387": AIRFOIL_DIR / "e387.dat",
}

# Fallback built-in/UIUC airfoil names if local DAT files are not present.
# These names are passed to asb.Airfoil(name), which can pull known profiles.
BUILTIN_AIRFOIL_FALLBACKS = {
    "mh45": "naca2412",
    "mh60": "naca4412",
    "fauvel": "naca0012",
    "rg15": "rg15",
    "sd7037": "sd7037",
    "s5010": "s5010",
    "e387": "e387",
}

# If a local DAT is missing, save the fallback geometry to that DAT path for future runs.
AUTO_EXPORT_FALLBACK_DAT = True

# Fixed reflex settings to try [deg].
# AeroSandbox ControlSurface deflection is documented as down-positive,
# so reflex (up) is negative.
REFLEX_CANDIDATES_DEG = [-8, -6, -4, -2, 0]

# XFoil command (only used when GENERATE_XFOIL_POLARS=True).
XFOIL_COMMAND = "xfoil"

# Default: use NeuralFoil-generated section polars and cache them to disk.
GENERATE_NEURALFOIL_POLARS = True

# Optional legacy path: generate section polars with XFoil instead.
GENERATE_XFOIL_POLARS = False

# Cache directory for section polar JSON files.
POLAR_CACHE_DIR = pathlib.Path("./polar_cache")

# Set True to ignore existing cache files and regenerate all polars.
FORCE_REGENERATE_POLAR_CACHE = False

# Polar sampling grids used for cache key + XFoil calls.
POLAR_ALPHAS_DEG = np.linspace(-12, 18, 31)
POLAR_RES = np.geomspace(2e4, 3e5, 9)

# Set True to only generate/load cached polars and then exit.
PRECOMPUTE_POLARS_ONLY = False

# Persistent cache for solved optimization cases (airfoil+reflex+config signature).
USE_RESULT_CACHE = True
FORCE_REGENERATE_RESULT_CACHE = False
RESULT_CACHE_DIR = pathlib.Path("./result_cache")

# NeuralFoil cache controls.
NEURALFOIL_MODEL_SIZE = "large"
USE_NEURALFOIL_POLARS_IN_3D = True

# If True, monkey-patch each Airfoil instance so 3D analyses (e.g., LiftingLine)
# use cached XFoil polar surrogate functions instead of direct NeuralFoil calls.
USE_XFOIL_POLARS_IN_3D = False

# If True, print progress
VERBOSE = True

# Objective mode:
# - "sink_rate": classic steady-trim sink-rate optimization
# - "drop_time_with_accel": includes an altitude cost to accelerate from low launch speed
OBJECTIVE_MODE = "drop_time_with_accel"

# Low-speed launch proxy used when OBJECTIVE_MODE == "drop_time_with_accel"
LAUNCH_SPEED_MPS = 0.3
MIN_REMAINING_ALTITUDE_M = 1.0

# Save a simple geometry plot for the winning airfoil.
PLOT_WINNER_AIRFOIL = True
WINNER_AIRFOIL_PLOT_PATH = pathlib.Path("./outputs/winner_airfoil.png")

# 3D top-down/isometric view of the winning wing geometry.
PLOT_WINNER_3D = True
WINNER_3D_PLOT_PATH = pathlib.Path("./outputs/winner_3d_wing.png")

# Airfoil polar curves (CL, CD, L/D vs alpha) at the operating Reynolds number.
PLOT_WINNER_POLARS = True
WINNER_POLARS_PLOT_PATH = pathlib.Path("./outputs/winner_polars.png")

# 2D glide path: altitude vs horizontal distance, including acceleration phase.
PLOT_WINNER_FLIGHT_PATH = True
WINNER_FLIGHT_PATH_PLOT_PATH = pathlib.Path("./outputs/winner_flight_path.png")

# Elevon starts at this span fraction and extends to tip.
ELEVON_START_SPAN_FRACTION = 0.60
ELEVON_HINGE_POINT_FRACTION = 0.70

# ----------------------------
# Optimization bounds
# ----------------------------

SPAN_BOUNDS_M = (0.45, 0.95)
ROOT_CHORD_BOUNDS_M = (0.10, 0.28)
TAPER_BOUNDS = (0.25, 0.95)
SWEEP_BOUNDS_DEG = (0.0, 38.0)
WASHOUT_BOUNDS_DEG = (0.0, 8.0)
DIHEDRAL_BOUNDS_DEG = (0.0, 8.0)
CG_FRACTION_BOUNDS = (0.08, 0.35)  # fraction of MAC from LE
VELOCITY_BOUNDS_MPS = (1.0, 20.0)
ALPHA_BOUNDS_DEG = (-2.0, 18.0)

# You can tighten these after you get a few solutions.
MIN_STATIC_STABILITY_CMA = -0.01  # require Cma < this
MIN_CLEARANCE_MARGIN = 0.0
