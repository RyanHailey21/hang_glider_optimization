from __future__ import annotations

import math
from pathlib import Path

import aerosandbox as asb
import matplotlib.pyplot as plt
import numpy as np

from .models import DesignResult


def save_airfoil_geometry_plot(
    airfoil: asb.Airfoil,
    title: str,
    output_path: Path,
    reflex_deg: float = 0.0,
    hinge_x: float = 0.70,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    coords = np.array(airfoil.coordinates, dtype=float)
    x = coords[:, 0]
    y = coords[:, 1]

    # Approximate "modified" section for visualization only:
    # rotate all points aft of hinge as a rigid flap segment.
    # Aero model uses down-positive control deflection, so negative means reflex/up.
    # For the geometric overlay, use positive theta as trailing-edge-up rotation.
    theta = np.radians(-reflex_deg)
    deflected = coords.copy()
    mask = deflected[:, 0] >= hinge_x
    xr = deflected[mask, 0] - hinge_x
    yr = deflected[mask, 1]
    deflected[mask, 0] = hinge_x + xr * np.cos(theta) - yr * np.sin(theta)
    deflected[mask, 1] = xr * np.sin(theta) + yr * np.cos(theta)

    fig, ax = plt.subplots(figsize=(8, 3))
    ax.plot(x, y, linewidth=2, label="Base airfoil")
    ax.plot(deflected[:, 0], deflected[:, 1], linewidth=2, linestyle="--", label=f"Approx. deflected ({reflex_deg:+.1f} deg)")
    ax.axvline(hinge_x, linestyle=":", linewidth=1, alpha=0.7, label=f"Hinge x/c={hinge_x:.2f}")
    ax.set_title(title)
    ax.set_xlabel("x/c")
    ax.set_ylabel("y/c")
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)

    return output_path


def save_wing_3d_plot(
    airplane: asb.Airplane,
    result: DesignResult,
    output_path: Path,
) -> Path:
    """Top-down + isometric matplotlib view of the winning wing geometry."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    airplane.draw(
        backend="matplotlib",
        thin_wings=True,
        show=False,
    )
    fig = plt.gcf()
    ar = result.span_m ** 2 / result.area_m2
    fig.suptitle(
        f"{result.airfoil_name}  |  reflex {result.reflex_deg:+.1f}°  |  "
        f"span {result.span_m:.3f} m  |  AR {ar:.1f}  |  "
        f"sweep {result.sweep_deg:.1f}°  |  washout {result.washout_deg:.1f}°",
        fontsize=9,
    )
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return output_path


def save_polar_plot(
    airfoil: asb.Airfoil,
    result: DesignResult,
    output_path: Path,
) -> Path:
    """CL, CD, and L/D vs alpha at the operating Reynolds number."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rho = 1.225   # kg/m³  ISA sea level
    nu  = 1.5e-5  # m²/s   kinematic viscosity
    re_op = rho * result.speed_mps * result.mac_m / nu

    alphas = np.linspace(-4, 18, 300)
    re_arr = re_op * np.ones_like(alphas)

    if hasattr(airfoil, "CL_function") and airfoil.CL_function is not None:
        cls = np.array(airfoil.CL_function(alpha=alphas, Re=re_arr), dtype=float)
        cds = np.array(airfoil.CD_function(alpha=alphas, Re=re_arr), dtype=float)
    else:
        aero = airfoil.get_aero_from_neuralfoil(alpha=alphas, Re=re_arr, mach=0.0)
        cls = np.array(aero["CL"], dtype=float)
        cds = np.array(aero["CD"], dtype=float)

    ld = cls / np.where(cds > 0, cds, np.nan)

    fig, axes = plt.subplots(1, 3, figsize=(13, 4))

    ax = axes[0]
    ax.plot(alphas, cls, "b-", linewidth=1.5)
    ax.axvline(result.alpha_deg, color="r", linestyle="--", linewidth=1,
               label=f"Op. point  α={result.alpha_deg:.1f}°")
    ax.axhline(result.CL, color="r", linestyle=":", linewidth=0.8)
    ax.set_xlabel("α (deg)")
    ax.set_ylabel("CL")
    ax.set_title("Lift curve")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    ax = axes[1]
    ax.plot(cds * 1e4, cls, "b-", linewidth=1.5)
    ax.plot(result.CD * 1e4, result.CL, "ro", markersize=6,
            label=f"Op. point  L/D={result.CL/result.CD:.1f}")
    ax.set_xlabel("CD × 10⁴")
    ax.set_ylabel("CL")
    ax.set_title("Drag polar")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    ax = axes[2]
    ax.plot(alphas, ld, "b-", linewidth=1.5)
    ax.axvline(result.alpha_deg, color="r", linestyle="--", linewidth=1,
               label=f"Op. point  L/D={result.CL/result.CD:.1f}")
    ax.set_xlabel("α (deg)")
    ax.set_ylabel("L/D")
    ax.set_title("Glide ratio")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    fig.suptitle(
        f"{result.airfoil_name}  reflex {result.reflex_deg:+.1f}°  "
        f"at Re = {re_op:.0f}",
        fontsize=10,
    )
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def save_flight_path_plot(
    result: DesignResult,
    output_path: Path,
) -> Path:
    """2D altitude vs horizontal distance showing accel phase then steady glide."""
    from .config import DROP_HEIGHT_M

    output_path.parent.mkdir(parents=True, exist_ok=True)

    h0 = DROP_HEIGHT_M
    h_glide = h0 - result.accel_height_loss_m
    glide_angle_rad = math.atan2(result.CD, result.CL)   # ≈ atan(1/LD)
    h_speed = result.speed_mps * math.cos(glide_angle_rad)

    # Phase 1: near-vertical free-fall acceleration (approximate as vertical)
    t1 = np.linspace(0, 1, 30)
    x1 = np.zeros(30)
    y1 = h0 - t1 * result.accel_height_loss_m

    # Phase 2: steady glide at constant sink rate
    n = 300
    y2 = np.linspace(h_glide, 0, n)
    x2 = (h_glide - y2) * (result.CL / result.CD)

    fig, ax = plt.subplots(figsize=(11, 5))

    ax.plot(x1, y1, color="steelblue", linewidth=2, label="Accel phase (approx. vertical)")
    ax.plot(x2, y2, color="seagreen", linewidth=2,
            label=f"Steady glide  L/D = {result.CL/result.CD:.1f}")
    ax.fill_between(x2, y2, alpha=0.07, color="seagreen")

    # Ground line
    x_total = x2[-1]
    ax.axhline(0, color="#8B6914", linewidth=2, zorder=0)

    # Annotations
    ax.annotate(
        f"Drop  {h0*3.281:.0f} ft ({h0:.1f} m)",
        xy=(0, h0), xytext=(x_total * 0.08, h0 * 1.03),
        fontsize=8, arrowprops=dict(arrowstyle="->", color="gray", lw=0.8),
    )
    ax.annotate(
        f"Accel height lost: {result.accel_height_loss_m:.2f} m",
        xy=(0, h_glide), xytext=(x_total * 0.08, h_glide * 0.82),
        fontsize=8, arrowprops=dict(arrowstyle="->", color="gray", lw=0.8),
    )
    ax.text(
        x_total * 0.5, h_glide * 0.55,
        f"Total time ≈ {result.estimated_total_time_from_60ft_s:.1f} s\n"
        f"Trim speed  {result.speed_mps:.2f} m/s\n"
        f"Sink rate    {result.sink_rate_mps:.3f} m/s",
        fontsize=8.5, ha="center", va="center",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="lightyellow", alpha=0.85),
    )

    ax.set_xlabel("Horizontal distance (m)")
    ax.set_ylabel("Altitude (m)")
    ax.set_title(
        f"Flight path — {result.airfoil_name}  reflex {result.reflex_deg:+.1f}°  "
        f"|  {result.airfoil_name}  span {result.span_m:.3f} m  area {result.area_m2:.4f} m²"
    )
    ax.set_xlim(-x_total * 0.05, x_total * 1.08)
    ax.set_ylim(-0.5, h0 * 1.12)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.25)

    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path
