"""Experiment: find a recipe that yields a single mode-locked pulse.

Tries several named cavity strategies and reports how many pulses survive in
the final round trip for each. The aim is to find settings where exactly one
pulse "wins the race".

Run from the repo root:
    .venv\\Scripts\\python.exe experiments\\single_pulse_recipe.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from pulse_gui.mode_locked_simulation import RingLaserConfig, run_ring_laser
from experiments.single_pulse_sweep import count_pulses, COUNT_WINDOW_PS

ROUND_TRIPS = 150

# (label, overrides) - each overrides RingLaserConfig defaults.
STRATEGIES = [
    ("baseline: noise seed",
     dict(seed_from_noise=True, passive_length_m=10.0, pump_power_w=0.6)),
    ("single-pulse seed",
     dict(seed_from_noise=False, passive_length_m=10.0, pump_power_w=0.6)),
    ("single seed + short cavity (2 m)",
     dict(seed_from_noise=False, passive_length_m=2.0, pump_power_w=0.6)),
    ("single seed + short + low pump",
     dict(seed_from_noise=False, passive_length_m=2.0, pump_power_w=0.3)),
    ("single seed + strong SA",
     dict(seed_from_noise=False, passive_length_m=2.0, pump_power_w=0.3,
          sa_mod_depth=0.6, sa_sat_power_w=80.0)),
]


def main():
    n = len(STRATEGIES)
    fig, axs = plt.subplots(1, n, figsize=(3.8 * n, 3.6), squeeze=False)
    fig.suptitle(f"Searching for single-pulse operation "
                 f"({ROUND_TRIPS} round trips)", fontsize=13)

    summary = []
    t0 = time.time()
    for j, (label, overrides) in enumerate(STRATEGIES):
        print(f"[{time.time() - t0:6.1f}s] {label} ...", flush=True)
        cfg = RingLaserConfig(round_trips=ROUND_TRIPS, **overrides)
        res = run_ring_laser(cfg)
        final_power = res.time_evolution[-1]
        n_pulses, peak_idx = count_pulses(res.time_ps, final_power)
        energy = res.pulse_energy_nj[-1] if res.pulse_energy_nj.size else 0.0
        summary.append((label, n_pulses, energy))
        print(f"            -> {n_pulses} pulse(s), E={energy:.3f} nJ",
              flush=True)

        ax = axs[0][j]
        mask = np.abs(res.time_ps) <= COUNT_WINDOW_PS
        tw, pw = res.time_ps[mask], final_power[mask]
        ax.plot(tw, pw, color="C0", lw=1.2)
        if len(peak_idx):
            ax.plot(tw[peak_idx], pw[peak_idx], "rv", ms=6)
        colour = "green" if n_pulses == 1 else "firebrick"
        ax.set_title(f"{label}\n{n_pulses} pulse(s), {energy:.2f} nJ",
                     fontsize=8, color=colour)
        ax.set_xlabel("Time (ps)")
        ax.set_ylabel("Power (W)")
        ax.grid(True, alpha=0.3)

    fig.tight_layout(rect=[0, 0, 1, 0.9])
    out = "experiments/single_pulse_recipe.png"
    fig.savefig(out, dpi=110)
    print(f"\nSaved {out}")

    print("\n=== summary ===")
    for label, n, e in summary:
        flag = "  <== SINGLE PULSE" if n == 1 else ""
        print(f"{n:>3d} pulse(s)  E={e:6.3f} nJ   {label}{flag}")


if __name__ == "__main__":
    main()
