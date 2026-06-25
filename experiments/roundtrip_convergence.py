"""Experiment: does the pulse count drop toward 1 with more round trips?

Fixes a modest cavity (short passive fibre, low pump) and runs the ring laser
for increasing numbers of round trips, counting surviving pulses each time.
This tests whether the "single pulse wins the race" behaviour just needs more
cavity round trips to emerge from noise.

Run from the repo root:
    .venv\\Scripts\\python.exe experiments\\roundtrip_convergence.py
Optional args:
    --length L           passive fibre length in metres (default 2.0)
    --pump P             pump power in W (default 0.3)
    --trips a,b,c        round-trip counts to test (default 40,100,200,400)
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
    parser.add_argument("--length", type=float, default=2.0)
    parser.add_argument("--pump", type=float, default=0.3)
    parser.add_argument("--trips", type=str, default="40,100,200,400")
    args = parser.parse_args()

    trips = [int(x) for x in args.trips.split(",")]

    ncols = len(trips)
    fig, axs = plt.subplots(1, ncols, figsize=(4.2 * ncols, 3.4),
                            squeeze=False)
    fig.suptitle(
        f"Pulse count vs round trips (L={args.length} m, "
        f"pump={args.pump} W, from noise)", fontsize=13)

    summary = []
    t0 = time.time()
    for j, n_trips in enumerate(trips):
        print(f"[{time.time() - t0:6.1f}s] running {n_trips} round trips ...",
              flush=True)
        cfg = RingLaserConfig(
            passive_length_m=args.length,
            pump_power_w=args.pump,
            round_trips=n_trips,
        )
        res = run_ring_laser(cfg)
        final_power = res.time_evolution[-1]
        n_pulses, peak_idx = count_pulses(res.time_ps, final_power)
        energy = res.pulse_energy_nj[-1] if res.pulse_energy_nj.size else 0.0
        summary.append((n_trips, n_pulses, energy))
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
        ax.set_title(f"{n_trips} trips\n{n_pulses} pulse(s), {energy:.2f} nJ",
                     fontsize=9, color=colour)
        ax.set_xlabel("Time (ps)")
        ax.set_ylabel("Power (W)")
        ax.grid(True, alpha=0.3)

    fig.tight_layout(rect=[0, 0, 1, 0.92])
    out = "experiments/roundtrip_convergence.png"
    fig.savefig(out, dpi=110)
    print(f"\nSaved {out}")

    print("\n=== summary ===")
    print(f"{'trips':>6} {'#pulses':>8} {'energy(nJ)':>11}")
    for n_trips, n, e in summary:
        print(f"{n_trips:>6d} {n:>8d} {e:>11.3f}")


if __name__ == "__main__":
    main()
