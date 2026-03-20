from __future__ import annotations

import hashlib
import json
import pathlib
import re
import types

import aerosandbox as asb
import aerosandbox.numpy as np

from .config import (
    AUTO_EXPORT_FALLBACK_DAT,
    BUILTIN_AIRFOIL_FALLBACKS,
    FORCE_REGENERATE_POLAR_CACHE,
    GENERATE_NEURALFOIL_POLARS,
    GENERATE_XFOIL_POLARS,
    NEURALFOIL_MODEL_SIZE,
    POLAR_ALPHAS_DEG,
    POLAR_CACHE_DIR,
    POLAR_RES,
    USE_NEURALFOIL_POLARS_IN_3D,
    USE_XFOIL_POLARS_IN_3D,
    VERBOSE,
    XFOIL_COMMAND,
)


def _parse_airfoil_dat_coordinates(dat_path: pathlib.Path):
    """
    Best-effort parser for common airfoil DAT formats (Selig, Fauvel/sectioned).
    Returns an Nx2 coordinate array or None if parsing fails.
    """
    float_pattern = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")

    try:
        with open(dat_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return None

    if not lines:
        return None

    # Check if this is a sectioned format (e.g., Fauvel: upper surface, then lower surface).
    # Look for a line with exactly 2 numbers that look like point counts.
    upper_coords = []
    lower_coords = []
    is_sectioned = False

    for i, line in enumerate(lines[1:], start=1):  # Skip title line
        clean = line.split("!")[0].split("#")[0].strip()
        if not clean:
            continue
        nums = float_pattern.findall(clean)
        # If we find a line with 2 numbers early on, it might be point counts (sectioned format)
        if len(nums) == 2 and i < 5:
            try:
                n_upper = int(float(nums[0]))
                n_lower = int(float(nums[1]))
                if 5 <= n_upper <= 500 and 5 <= n_lower <= 500:
                    is_sectioned = True
                    section_start_idx = i
                    break
            except Exception:
                pass

    if is_sectioned:
        # Parse upper and lower surfaces separately, then merge.
        section_idx = section_start_idx + 1
        while section_idx < len(lines) and not lines[section_idx].strip():
            section_idx += 1  # Skip blank lines

        # Parse upper surface
        upper_count = 0
        while section_idx < len(lines) and upper_count < n_upper:
            clean = lines[section_idx].split("!")[0].split("#")[0].strip()
            if clean:
                nums = float_pattern.findall(clean)
                if len(nums) >= 2:
                    try:
                        upper_coords.append([float(nums[0]), float(nums[1])])
                        upper_count += 1
                    except Exception:
                        pass
            section_idx += 1

        # Skip blank lines to lower surface
        while section_idx < len(lines) and not lines[section_idx].strip():
            section_idx += 1

        # Parse lower surface
        lower_count = 0
        while section_idx < len(lines) and lower_count < n_lower:
            clean = lines[section_idx].split("!")[0].split("#")[0].strip()
            if clean:
                nums = float_pattern.findall(clean)
                if len(nums) >= 2:
                    try:
                        lower_coords.append([float(nums[0]), float(nums[1])])
                        lower_count += 1
                    except Exception:
                        pass
            section_idx += 1

        # Merge: upper surface + reversed lower surface to form closed loop.
        # Remove duplicate points at junctions (typically at trailing/leading edges).
        if upper_coords and lower_coords:
            lower_rev = lower_coords[::-1]

            # Check if junction points are duplicates (common at TE where upper ends and lower_rev starts).
            coords = []
            if np.allclose(upper_coords[-1], lower_rev[0], atol=1e-6):
                # Remove duplicate: upper + lower_rev[1:]
                coords = upper_coords + lower_rev[1:]
            else:
                coords = upper_coords + lower_rev

            # Also remove duplicate if last point equals first point (should close loop naturally).
            if len(coords) > 2 and np.allclose(coords[0], coords[-1], atol=1e-6):
                coords = coords[:-1]  # Keep first, remove last duplicate
        else:
            coords = []
    else:
        # Standard Selig format: continuous coordinate list.
        coords = []
        # Skip title/header line. Many DAT headers contain numbers (e.g. "MH 45 9.85%"),
        # which can be incorrectly parsed as a bogus coordinate if included.
        for line in lines[1:]:
            clean = line.split("!")[0].split("#")[0].strip()
            if not clean:
                continue
            nums = float_pattern.findall(clean)
            if len(nums) < 2:
                continue
            try:
                x = float(nums[0])
                y = float(nums[1])
                coords.append([x, y])
            except Exception:
                continue

    # A practical minimum for a usable airfoil polyline.
    if len(coords) < 10:
        return None

    return np.array(coords)


def load_and_prepare_airfoil(name: str, dat_path: pathlib.Path) -> asb.Airfoil:
    """
    Loads an airfoil from a local DAT file and generates XFoil/NeuralFoil-backed surrogate models.
    """
    if dat_path.exists():
        # Parse with tolerant loader first to avoid spurious parser warnings on
        # sectioned DAT formats (e.g., Fauvel upper/lower-surface blocks).
        airfoil_source_tag = dat_path.stem.lower()
        parsed_coords = _parse_airfoil_dat_coordinates(dat_path)
        if parsed_coords is not None:
            if VERBOSE:
                print(f"[INFO] Parsed DAT with tolerant loader: {dat_path}")
            airfoil = asb.Airfoil(name=name, coordinates=parsed_coords)
        else:
            airfoil = asb.Airfoil(str(dat_path))
            native_coords = getattr(airfoil, "coordinates", None)
            native_ok = native_coords is not None and len(native_coords) >= 10
            if not native_ok:
                fallback_name = BUILTIN_AIRFOIL_FALLBACKS.get(name, name)
                if VERBOSE:
                    print(
                        f"[WARN] Could not parse local DAT for '{name}' at {dat_path}; "
                        f"falling back to built-in/UIUC airfoil '{fallback_name}'."
                    )
                airfoil = asb.Airfoil(fallback_name)
                airfoil_source_tag = fallback_name.lower()
    else:
        fallback_name = BUILTIN_AIRFOIL_FALLBACKS.get(name, name)
        if VERBOSE:
            print(
                f"[WARN] Missing local DAT for '{name}' at {dat_path}; "
                f"falling back to built-in/UIUC airfoil '{fallback_name}'."
            )
        airfoil = asb.Airfoil(fallback_name)
        airfoil_source_tag = fallback_name.lower()

        # Optional: write fallback geometry to the expected local DAT path.
        if AUTO_EXPORT_FALLBACK_DAT:
            dat_path.parent.mkdir(parents=True, exist_ok=True)
            airfoil.write_dat(dat_path)
            if VERBOSE:
                print(f"[INFO] Wrote fallback airfoil DAT: {dat_path}")

    airfoil = airfoil.normalize().repanel(n_points_per_side=120)

    # Fingerprint the actual geometry so cache keys update when DAT contents change.
    geom_rows = []
    for x, y in airfoil.coordinates:
        geom_rows.append(f"{float(x):.8f},{float(y):.8f}")
    geometry_fingerprint = hashlib.sha1("\n".join(geom_rows).encode("utf-8")).hexdigest()[:16]

    # Optional: generate CL/CD/CM surrogate models from NeuralFoil data.
    if GENERATE_NEURALFOIL_POLARS:
        try:
            POLAR_CACHE_DIR.mkdir(parents=True, exist_ok=True)

            cache_key = (
                f"backend=neuralfoil|"
                f"src={airfoil_source_tag}|"
                f"geom={geometry_fingerprint}|"
                f"a={','.join([f'{a:.3f}' for a in POLAR_ALPHAS_DEG])}|"
                f"re={','.join([f'{r:.1f}' for r in POLAR_RES])}|"
                f"model={NEURALFOIL_MODEL_SIZE}"
            )
            cache_hash = hashlib.sha1(cache_key.encode("utf-8")).hexdigest()[:12]
            cache_path_nf = POLAR_CACHE_DIR / f"{name}_nf_{cache_hash}.json"

            def nf_cache_is_valid(path: pathlib.Path) -> bool:
                if not path.exists() or path.stat().st_size <= 0:
                    return False
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    alpha_grid = np.array(data.get("alpha_grid", []), dtype=float)
                    re_grid = np.array(data.get("re_grid", []), dtype=float)
                    cl_grid = np.array(data.get("CL", []), dtype=float)
                    cd_grid = np.array(data.get("CD", []), dtype=float)
                    cm_grid = np.array(data.get("CM", []), dtype=float)

                    if alpha_grid.ndim != 1 or re_grid.ndim != 1:
                        return False
                    if len(alpha_grid) == 0 or len(re_grid) == 0:
                        return False
                    target_shape = (len(alpha_grid), len(re_grid))
                    if cl_grid.shape != target_shape:
                        return False
                    if cd_grid.shape != target_shape:
                        return False
                    if cm_grid.shape != target_shape:
                        return False
                    if not np.all(np.isfinite(cl_grid)):
                        return False
                    if not np.all(np.isfinite(cd_grid)):
                        return False
                    if not np.all(np.isfinite(cm_grid)):
                        return False
                    return True
                except Exception:
                    return False

            cache_valid_nf = nf_cache_is_valid(cache_path_nf)
            if cache_path_nf.exists() and not cache_valid_nf:
                if VERBOSE:
                    print(f"[WARN] Corrupt/incomplete NeuralFoil cache removed: {cache_path_nf}")
                cache_path_nf.unlink()

            if FORCE_REGENERATE_POLAR_CACHE and cache_path_nf.exists():
                cache_path_nf.unlink()
                cache_valid_nf = False

            if cache_valid_nf:
                if VERBOSE:
                    print(f"[CACHE] Using cached NeuralFoil polars: {cache_path_nf}")
                with open(cache_path_nf, "r", encoding="utf-8") as f:
                    nf_data = json.load(f)
            else:
                if VERBOSE:
                    print(f"[NEURALFOIL] Generating polars and caching to: {cache_path_nf}")
                alpha_grid = np.array(POLAR_ALPHAS_DEG, dtype=float)
                re_grid = np.array(POLAR_RES, dtype=float)
                cl_grid = np.empty((len(alpha_grid), len(re_grid)))
                cd_grid = np.empty((len(alpha_grid), len(re_grid)))
                cm_grid = np.empty((len(alpha_grid), len(re_grid)))

                for j, re_val in enumerate(re_grid):
                    aero = airfoil.get_aero_from_neuralfoil(
                        alpha=alpha_grid,
                        Re=re_val * np.ones_like(alpha_grid),
                        mach=0.0,
                        model_size=NEURALFOIL_MODEL_SIZE,
                    )
                    cl_grid[:, j] = np.array(aero["CL"], dtype=float)
                    cd_grid[:, j] = np.array(aero["CD"], dtype=float)
                    cm_grid[:, j] = np.array(aero["CM"], dtype=float)

                # Reject non-finite data before writing cache.
                if not np.all(np.isfinite(cl_grid)):
                    raise ValueError("NeuralFoil CL grid contains non-finite values.")
                if not np.all(np.isfinite(cd_grid)):
                    raise ValueError("NeuralFoil CD grid contains non-finite values.")
                if not np.all(np.isfinite(cm_grid)):
                    raise ValueError("NeuralFoil CM grid contains non-finite values.")

                nf_data = {
                    "alpha_grid": alpha_grid.tolist(),
                    "re_grid": re_grid.tolist(),
                    "CL": cl_grid.tolist(),
                    "CD": cd_grid.tolist(),
                    "CM": cm_grid.tolist(),
                    "model_size": NEURALFOIL_MODEL_SIZE,
                }

                with open(cache_path_nf, "w", encoding="utf-8") as f:
                    json.dump(nf_data, f, indent=2)

            alpha_grid = np.array(nf_data["alpha_grid"], dtype=float)
            re_grid = np.array(nf_data["re_grid"], dtype=float)
            cl_grid = np.array(nf_data["CL"], dtype=float)
            cd_grid = np.array(nf_data["CD"], dtype=float)
            cm_grid = np.array(nf_data["CM"], dtype=float)
            log_re_grid = np.log10(np.maximum(re_grid, 1.0))

            cl_interp = asb.InterpolatedModel(
                x_data_coordinates={"alpha": alpha_grid, "log10_Re": log_re_grid},
                y_data_structured=cl_grid,
                method="bspline",
                fill_value=None,
            )
            cd_interp = asb.InterpolatedModel(
                x_data_coordinates={"alpha": alpha_grid, "log10_Re": log_re_grid},
                y_data_structured=cd_grid,
                method="bspline",
                fill_value=None,
            )
            cm_interp = asb.InterpolatedModel(
                x_data_coordinates={"alpha": alpha_grid, "log10_Re": log_re_grid},
                y_data_structured=cm_grid,
                method="bspline",
                fill_value=None,
            )

            def cl_function(alpha, Re, mach=0.0):
                return cl_interp({"alpha": alpha, "log10_Re": np.log10(np.maximum(Re, 1.0))})

            def cd_function(alpha, Re, mach=0.0):
                return cd_interp({"alpha": alpha, "log10_Re": np.log10(np.maximum(Re, 1.0))})

            def cm_function(alpha, Re, mach=0.0):
                return cm_interp({"alpha": alpha, "log10_Re": np.log10(np.maximum(Re, 1.0))})

            airfoil.CL_function = cl_function
            airfoil.CD_function = cd_function
            airfoil.CM_function = cm_function

            if USE_NEURALFOIL_POLARS_IN_3D:

                def neuralfoil_cached_section_aero(
                    self,
                    alpha,
                    Re,
                    mach=0.0,
                    n_crit=9.0,
                    xtr_upper=1.0,
                    xtr_lower=1.0,
                    model_size="large",
                    control_surfaces=None,
                    include_360_deg_effects=True,
                ):
                    if control_surfaces is None:
                        control_surfaces = []

                    # Reuse AeroSandbox's control-surface alpha-shift/drag heuristics.
                    effective_d_alpha = 0.0
                    effective_CD_multiplier_from_control_surfaces = 1.0

                    for surf in control_surfaces:
                        effectiveness = 1 - np.maximum(0, surf.hinge_point + 1e-16) ** 2.751428551177291
                        effective_d_alpha += surf.deflection * effectiveness
                        effective_CD_multiplier_from_control_surfaces *= (
                            2
                            + (surf.deflection / 11.5) ** 2
                            - (1 + (surf.deflection / 11.5) ** 2) ** 0.5
                        )

                    alpha_eff = alpha + effective_d_alpha
                    CL = self.CL_function(alpha=alpha_eff, Re=Re, mach=mach)
                    CD = self.CD_function(alpha=alpha_eff, Re=Re, mach=mach) * effective_CD_multiplier_from_control_surfaces
                    CM = self.CM_function(alpha=alpha_eff, Re=Re, mach=mach)

                    return {
                        "CL": CL,
                        "CD": CD,
                        "CM": CM,
                    }

                airfoil.get_aero_from_neuralfoil = types.MethodType(neuralfoil_cached_section_aero, airfoil)
        except Exception as e:
            if VERBOSE:
                print(
                    f"[WARN] NeuralFoil polar cache generation failed for '{name}' ({e}); "
                    "continuing with direct NeuralFoil calls."
                )

    # Optional: generate CL/CD/CM surrogate models from XFoil data.
    # If disabled or if XFoil is unavailable, AeroSandbox can still run
    # using its default sectional aero models.
    if GENERATE_XFOIL_POLARS:
        try:
            POLAR_CACHE_DIR.mkdir(parents=True, exist_ok=True)

            cache_key = (
                f"src={airfoil_source_tag}|"
                f"geom={geometry_fingerprint}|"
                f"a={','.join([f'{a:.3f}' for a in POLAR_ALPHAS_DEG])}|"
                f"re={','.join([f'{r:.1f}' for r in POLAR_RES])}|"
                "sym=0"
            )
            cache_hash = hashlib.sha1(cache_key.encode("utf-8")).hexdigest()[:12]
            cache_path = POLAR_CACHE_DIR / f"{name}_{cache_hash}.json"

            def cache_is_valid(path: pathlib.Path) -> bool:
                if not path.exists() or path.stat().st_size <= 0:
                    return False
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    def _length_or_zero(v) -> int:
                        try:
                            return len(v)
                        except Exception:
                            return 0

                    # Reject empty/incomplete caches (these can be written when XFoil fails).
                    alpha_n = _length_or_zero(data.get("alpha", []))
                    if alpha_n == 0:
                        return False
                    if _length_or_zero(data.get("CL", [])) != alpha_n:
                        return False
                    if _length_or_zero(data.get("CD", [])) != alpha_n:
                        return False
                    if _length_or_zero(data.get("CM", [])) != alpha_n:
                        return False
                    if _length_or_zero(data.get("Re", [])) == 0:
                        return False
                    return True
                except Exception:
                    return False

            cache_valid = cache_is_valid(cache_path)

            if cache_path.exists() and not cache_valid:
                if VERBOSE:
                    print(f"[WARN] Corrupt/incomplete polar cache removed: {cache_path}")
                cache_path.unlink()

            if FORCE_REGENERATE_POLAR_CACHE and cache_path.exists():
                cache_path.unlink()
                cache_valid = False

            if VERBOSE:
                if cache_valid:
                    print(f"[CACHE] Using cached polars: {cache_path}")
                else:
                    print(f"[XFOIL] Generating polars and caching to: {cache_path}")

            airfoil.generate_polars(
                alphas=POLAR_ALPHAS_DEG,
                Res=POLAR_RES,
                cache_filename=str(cache_path),
                xfoil_kwargs={
                    "xfoil_command": XFOIL_COMMAND,
                    "timeout": 90,
                    "max_iter": 100,
                },
                include_compressibility_effects=False,
                make_symmetric_polars=False,
            )

            # Only apply XFoil monkey-patch if polars were actually generated successfully.
            has_xfoil_polars = (
                hasattr(airfoil, "CL_function")
                and hasattr(airfoil, "CD_function")
                and hasattr(airfoil, "CM_function")
                and airfoil.CL_function is not None
                and airfoil.CD_function is not None
                and airfoil.CM_function is not None
            )

            if USE_XFOIL_POLARS_IN_3D and has_xfoil_polars:

                def xfoil_backed_section_aero(
                    self,
                    alpha,
                    Re,
                    mach=0.0,
                    n_crit=9.0,
                    xtr_upper=1.0,
                    xtr_lower=1.0,
                    model_size="large",
                    control_surfaces=None,
                    include_360_deg_effects=True,
                ):
                    if control_surfaces is None:
                        control_surfaces = []

                    # Reuse AeroSandbox's control-surface alpha-shift/drag heuristics.
                    effective_d_alpha = 0.0
                    effective_CD_multiplier_from_control_surfaces = 1.0

                    for surf in control_surfaces:
                        effectiveness = 1 - np.maximum(0, surf.hinge_point + 1e-16) ** 2.751428551177291
                        effective_d_alpha += surf.deflection * effectiveness
                        effective_CD_multiplier_from_control_surfaces *= (
                            2
                            + (surf.deflection / 11.5) ** 2
                            - (1 + (surf.deflection / 11.5) ** 2) ** 0.5
                        )

                    alpha_eff = alpha + effective_d_alpha
                    CL = self.CL_function(alpha=alpha_eff, Re=Re, mach=mach)
                    CD = self.CD_function(alpha=alpha_eff, Re=Re, mach=mach) * effective_CD_multiplier_from_control_surfaces
                    CM = self.CM_function(alpha=alpha_eff, Re=Re, mach=mach)

                    return {
                        "CL": CL,
                        "CD": CD,
                        "CM": CM,
                    }

                airfoil.get_aero_from_neuralfoil = types.MethodType(xfoil_backed_section_aero, airfoil)
        except Exception as e:
            try:
                if "cache_path" in locals() and cache_path.exists() and not cache_is_valid(cache_path):
                    cache_path.unlink()
                    if VERBOSE:
                        print(f"[WARN] Removed invalid polar cache after failure: {cache_path}")
            except Exception:
                pass
            if VERBOSE:
                print(
                    f"[WARN] XFoil polar generation failed for '{name}' ({e}); "
                    "continuing without pre-generated polars."
                )

    return airfoil
