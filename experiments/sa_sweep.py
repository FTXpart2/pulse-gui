"""Experiment: effect of saturable-absorber settings on pulse count.

Fixes the cavity and sweeps the saturable-absorber saturation power at a chosen
modulation depth, counting surviving pulses in the final round trip. Lets us
test whether a given (mod_depth, sat_power) collapses the laser to one pulse.

Run from the repo root:
    .venv\\Scripts\\python.exe experiments\\sa_sweep.py --mod-depth 0.5 --sat-powers 300
    .venv\\Scripts\\python.exe experiments\\sa_sweep.py --mod-depth 0.5 --sat-powers 30,50,100,300
"""

import argparse
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mod-depth", type=float, default=0.5)
    parser.add_argument("--sat-powers", type=str, default="30,50,100,300")
    parser.add_argument("--length", type=float, default=2.0)
    parser.add_argument("--pump", type=float, default=0.3)
    parser.add_argument("--round-trips", type=int, default=150)
    args = parser.parse_args()

    sat_powers = [float(x) for x in args.sat_powers.split(",")]

    ncols = len(sat_powers)
    fig, axs = plt.subplots(1, ncols, figsize=(4.2 * ncols, 3.4),
                            squeeze=False)
    fig.suptitle(
        f"SA sweep: mod_depth={args.mod_depth:.0%}, "
        f"L={args.length} m, pump={args.pump} W, "
        f"{args.round_trips} round trips", fontsize=13)

    summary = []
    t0 = time.time()
    for j, sat_power in enumerate(sat_powers):
        print(f"[{time.time() - t0:6.1f}s] running sat_power={sat_power} W ...",
              flush=True)
        cfg = RingLaserConfig(
            passive_length_m=args.length,
            pump_power_w=args.pump,
            round_trips=args.round_trips,
            sa_mod_depth=args.mod_depth,
            sa_sat_power_w=sat_power,
        )
        res = run_ring_laser(cfg)
        final_power = res.time_evolution[-1]
        n_pulses, peak_idx = count_pulses(res.time_ps, final_power)
        energy = res.pulse_energy_nj[-1] if res.pulse_energy_nj.size else 0.0
        summary.append((sat_power, n_pulses, energy))
        print(f"            -> {n_pulses} pulse(s), E={energy:.3f} nJ",
              flush=True)

        ax = axs[0][j]
        mask = np.abs(res.time_ps) <= COUNT_WINDOW_PS
        tw = res.time_ps[mask]
        pw = final_power[mask]
        ax.plot(tw, pw, color="C0", lw=1.2)
        if len(peak_idx):
            ax.plot(tw[peak_idx], pw[peak_idx], "rv", ms=6)
        colour = "green" if n_pulses == 1 else "firebrick"
        ax.set_title(f"sat_power={sat_power:g} W\n"
                     f"{n_pulses} pulse(s), {energy:.2f} nJ",
                     fontsize=9, color=colour)
        ax.set_xlabel("Time (ps)")
        ax.set_ylabel("Power (W)")
        ax.grid(True, alpha=0.3)

    fig.tight_layout(rect=[0, 0, 1, 0.9])
    out = "experiments/sa_sweep.png"
    fig.savefig(out, dpi=110)
    print(f"\nSaved {out}")

    print("\n=== summary ===")
    print(f"{'sat_power(W)':>13} {'#pulses':>8} {'energy(nJ)':>11}")
    for sp, n, e in summary:
        print(f"{sp:>13.0f} {n:>8d} {e:>11.3f}")


if __name__ == "__main__":
    main()
