# Hang Glider Optimization

AeroSandbox-based optimizer for a tailless drop-wing glider with fixed elevon reflex.

The code searches over candidate airfoils and fixed reflex angles in parallel, then solves a continuous geometry/trim optimization to maximize estimated flight time from a fixed drop height.

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
- `"sink_rate"`: minimize `V * D / W` (classic steady-trim sink rate)
- `"drop_time_with_accel"` *(default)*: maximize `(DROP_HEIGHT - accel_height_loss) / sink_rate`, where `accel_height_loss = (V² - V_launch²) / (2g)` accounts for altitude consumed accelerating from near-zero launch speed

## Candidate Airfoils

Seven sections are evaluated by default:

| Key | Airfoil | Notes |
|-----|---------|-------|
| `mh45` | Müller-Heinz MH 45 | Flying wing section, low drag |
| `mh60` | Müller-Heinz MH 60 | Flying wing section, more camber |
| `fauvel` | Fauvel AV-36 | Very stable, lower L/D |
| `rg15` | René Gagnon RG 15 | Excellent low-Re glider performance |
| `sd7037` | Selig-Donovan SD 7037 | Top-performing RC sailplane section at low Re |
| `s5010` | Selig S 5010 | Reflexed; designed specifically for tailless aircraft |
| `e387` | Eppler E 387 | Classic low-Re benchmark |

Put `.dat` files in `./airfoils/`. If a file is missing, the loader falls back to the built-in UIUC database entry and optionally writes it to disk (`AUTO_EXPORT_FALLBACK_DAT = True`).

## Project Layout

- `main.py`: Thin entrypoint
- `hang_glider_opt/config.py`: User-configurable constants and bounds
- `hang_glider_opt/models.py`: Result dataclasses
- `hang_glider_opt/geometry.py`: Geometry + mass helper functions
- `hang_glider_opt/airfoil_loader.py`: DAT parsing, airfoil prep, NeuralFoil/XFoil cache pipeline
- `hang_glider_opt/aircraft.py`: Aircraft geometry builder
- `hang_glider_opt/solver.py`: CasADi/AeroSandbox optimization problem
- `hang_glider_opt/reporting.py`: Output formatting
- `hang_glider_opt/plotting.py`: All plot-saving functions
- `hang_glider_opt/app.py`: End-to-end workflow

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Optionally place custom airfoil DAT files in `./airfoils/`. Missing files are pulled from the built-in UIUC database automatically.

## Run

```bash
python main.py
```

Optional mode in `hang_glider_opt/config.py`:
- `PRECOMPUTE_POLARS_ONLY = True` to generate/load polars and exit.

## Output Plots

All plots are saved to `./outputs/` after each run:

| File | Contents |
|------|----------|
| `winner_airfoil.png` | Airfoil cross-section with deflected elevon overlay |
| `winner_3d_wing.png` | 3D matplotlib view of the winning wing geometry (sweep, taper, dihedral) |
| `winner_polars.png` | Lift curve, drag polar, and L/D vs alpha at the operating Reynolds number |
| `winner_flight_path.png` | 2D altitude vs horizontal distance: accel phase + steady glide, annotated with time and speed |

Each plot can be toggled independently in `config.py` (`PLOT_WINNER_3D`, `PLOT_WINNER_POLARS`, etc.).

## Key Configuration

Edit `hang_glider_opt/config.py`:

- **Mass model:**
  - `ELECTRONICS_MASS_KG`
  - `FIXED_NON_ELECTRONICS_MASS_KG`
  - `WING_AREAL_DENSITY_KG_PER_M2`
- **Airfoil set:**
  - `AIRFOIL_FILES`
  - `BUILTIN_AIRFOIL_FALLBACKS`
- **Reflex candidates:**
  - `REFLEX_CANDIDATES_DEG`
- **Objective model:**
  - `OBJECTIVE_MODE` (`"sink_rate"` or `"drop_time_with_accel"`)
  - `LAUNCH_SPEED_MPS`
  - `MIN_REMAINING_ALTITUDE_M`
- **Polar generation/caching:**
  - `GENERATE_NEURALFOIL_POLARS`
  - `USE_NEURALFOIL_POLARS_IN_3D`
  - `GENERATE_XFOIL_POLARS`
  - `FORCE_REGENERATE_POLAR_CACHE`
  - `POLAR_ALPHAS_DEG`, `POLAR_RES`
- **Optimization result caching:**
  - `USE_RESULT_CACHE`
  - `FORCE_REGENERATE_RESULT_CACHE`
  - `RESULT_CACHE_DIR`
- **Output plots:**
  - `PLOT_WINNER_AIRFOIL` / `WINNER_AIRFOIL_PLOT_PATH`
  - `PLOT_WINNER_3D` / `WINNER_3D_PLOT_PATH`
  - `PLOT_WINNER_POLARS` / `WINNER_POLARS_PLOT_PATH`
  - `PLOT_WINNER_FLIGHT_PATH` / `WINNER_FLIGHT_PATH_PLOT_PATH`
- **Bounds and stability:**
  - `SPAN_BOUNDS_M`, `ROOT_CHORD_BOUNDS_M`, etc.
  - `MIN_STATIC_STABILITY_CMA`

## Caching and Numerical Stability

Polar caches are stored in `./polar_cache`. The loader validates cache shape and rejects non-finite values (`NaN`, `Inf`); corrupt files are removed and regenerated automatically.

Optimization case results are cached in `./result_cache`. After changing solver settings (e.g. `spanwise_resolution`, bounds, objective mode), clear this directory to force fresh solves:

```bash
# Windows
Remove-Item -Recurse -Force .\result_cache\*

# Unix
rm -rf result_cache/*
```

To force polar regeneration: `FORCE_REGENERATE_POLAR_CACHE = True`.

## Parallelization

All `(airfoil, reflex)` cases run in parallel via `ThreadPoolExecutor`. The worker count is capped at `min(n_cases, cpu_count)` to avoid BLAS contention from simultaneous IPOPT solves. Cases that are already cached are returned immediately without running the solver.

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
