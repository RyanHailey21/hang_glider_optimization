from __future__ import annotations

from pathlib import Path

import aerosandbox as asb
import matplotlib.pyplot as plt
import numpy as np


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
