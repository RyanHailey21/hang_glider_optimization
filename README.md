# Hang Glider Optimization

AeroSandbox-based optimizer for a tailless drop-wing glider with fixed elevon reflex.

The code searches over candidate airfoils and fixed reflex angles, then solves a continuous geometry/trim optimization to minimize estimated sink rate.

## What It Optimizes

For each `(airfoil, reflex)` pair:
- Geometry: span, root chord, taper, sweep, washout, dihedral
- Trim: speed, angle of attack, CG location (fraction of MAC)

Subject to:
- Lift equals weight
- Pitching moment trim (`m_b = 0`)
- Static stability constraint (`Cma <= MIN_STATIC_STABILITY_CMA`)
- Practical geometry and aspect ratio bounds

Objective:
- Minimize estimated sink rate `V * D / W`

Note on low-speed launch:
- You can switch to a low-speed-aware objective (`drop_time_with_accel`) that penalizes altitude spent accelerating from near-zero launch speed before steady glide.

## Project Layout

- `main.py`: Thin entrypoint
- `hang_glider_opt/config.py`: User-configurable constants and bounds
- `hang_glider_opt/models.py`: Result dataclasses
- `hang_glider_opt/geometry.py`: Geometry + mass helper functions
- `hang_glider_opt/airfoil_loader.py`: DAT parsing, airfoil prep, NeuralFoil/XFoil cache pipeline
- `hang_glider_opt/aircraft.py`: Aircraft geometry builder
- `hang_glider_opt/solver.py`: CasADi/AeroSandbox optimization problem
- `hang_glider_opt/reporting.py`: Output formatting
- `hang_glider_opt/app.py`: End-to-end workflow

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Put airfoil DAT files in `./airfoils/`:
- `mh45.dat`
- `mh60.dat`
- `fauvel.dat`

## Run

```bash
python main.py
```

Optional mode in `hang_glider_opt/config.py`:
- `PRECOMPUTE_POLARS_ONLY = True` to generate/load polars and exit.

## Key Configuration

Edit `hang_glider_opt/config.py`:
- Mass model:
  - `ELECTRONICS_MASS_KG`
  - `FIXED_NON_ELECTRONICS_MASS_KG`
  - `WING_AREAL_DENSITY_KG_PER_M2`
- Airfoil set:
  - `AIRFOIL_FILES`
  - `BUILTIN_AIRFOIL_FALLBACKS`
- Reflex candidates:
  - `REFLEX_CANDIDATES_DEG`
- Objective model:
  - `OBJECTIVE_MODE` (`"sink_rate"` or `"drop_time_with_accel"`)
  - `LAUNCH_SPEED_MPS`
  - `MIN_REMAINING_ALTITUDE_M`
- Polar generation/caching:
  - `GENERATE_NEURALFOIL_POLARS`
  - `USE_NEURALFOIL_POLARS_IN_3D`
  - `GENERATE_XFOIL_POLARS`
  - `FORCE_REGENERATE_POLAR_CACHE`
  - `POLAR_ALPHAS_DEG`, `POLAR_RES`
- Optimization result caching:
  - `USE_RESULT_CACHE`
  - `FORCE_REGENERATE_RESULT_CACHE`
  - `RESULT_CACHE_DIR`
- Winner geometry plotting:
  - `PLOT_WINNER_AIRFOIL`
  - `WINNER_AIRFOIL_PLOT_PATH`
- Bounds and stability:
  - `SPAN_BOUNDS_M`, `ROOT_CHORD_BOUNDS_M`, etc.
  - `MIN_STATIC_STABILITY_CMA`

## Caching and Numerical Stability

Polar caches are stored in `./polar_cache`.

The loader validates cache shape and rejects non-finite values (`NaN`, `Inf`). If invalid, cache files are removed and regenerated automatically.

If you suspect stale/corrupt caches, set:
- `FORCE_REGENERATE_POLAR_CACHE = True`

Optimization case results are cached in `./result_cache` so repeated runs can reuse previous solve outputs.

## Common Errors

### `Invalid_Number_Detected` from CasADi/IPOPT

Typical causes:
- Invalid sectional aero data (`NaN`/`Inf`) in cached polars
- Out-of-range interpolation behavior from bad inputs
- Corrupt/malformed airfoil geometry

Checks:
1. Delete `polar_cache/*` and rerun.
2. Confirm DAT files are valid coordinate sets.
3. Temporarily tighten bounds to keep optimizer in conservative regions.

### XFoil not found

If using XFoil mode (`GENERATE_XFOIL_POLARS = True`), ensure `XFOIL_COMMAND` points to an installed executable.

## Development Notes

- Keep solver logic in `solver.py`.
- Keep all tunable constants in `config.py`.
- Add new constraints/objective terms in one place and keep reporting fields synchronized with `DesignResult`.
- Prefer adding small tests around parser/caching logic before changing aero data plumbing.
