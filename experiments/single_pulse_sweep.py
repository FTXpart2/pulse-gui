"""Experiment: when does the Er ring laser collapse to a single pulse?

Sweeps passive-fibre length and pump power, runs the mode-locked ring laser
from noise for each combination, counts how many pulses survive in the final
round trip, and saves a comparison figure.

Run from the repo root:
    .venv\\Scripts\\python.exe experiments\\single_pulse_sweep.py
Optional args:
    --round-trips N      number of cavity round trips (default 50)
    --lengths a,b,c      passive fibre lengths in metres (default 2,5,10)
    --pumps a,b          pump powers in W (default 0.3,0.6)
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
from scipy.signal import find_peaks

from pulse_gui.mode_locked_simulation import RingLaserConfig, run_ring_laser

# Pulses are counted only inside this window (ps) around the cavity centre.
COUNT_WINDOW_PS = 40.0
# A peak must exceed this fraction of the global maximum to count as a pulse.
PEAK_REL_HEIGHT = 0.20
# Minimum separation between distinct pulses (ps).
MIN_PULSE_SEP_PS = 1.0


def count_pulses(time_ps, power):
    """Count distinct pulses in the final-round-trip power trace."""
    peak = power.max()
    if peak <= 0 or not np.isfinite(peak):
        return 0, np.array([], dtype=int)
    mask = np.abs(time_ps) <= COUNT_WINDOW_PS
    t = time_ps[mask]
    p = power[mask]
    if t.size < 3:
        t, p = time_ps, power
    dt_ps = np.median(np.diff(t))
    distance = max(1, int(round(MIN_PULSE_SEP_PS / max(dt_ps, 1e-6))))
    idx, _ = find_peaks(p, height=PEAK_REL_HEIGHT * peak, distance=distance)
    return len(idx), idx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--round-trips", type=int, default=50)
    parser.add_argument("--lengths", type=str, default="2,5,10")
    parser.add_argument("--pumps", type=str, default="0.3,0.6")
    args = parser.parse_args()

    lengths = [float(x) for x in args.lengths.split(",")]
    pumps = [float(x) for x in args.pumps.split(",")]

    nrows, ncols = len(pumps), len(lengths)
    fig, axs = plt.subplots(nrows, ncols, figsize=(4.2 * ncols, 3.2 * nrows),
                            squeeze=False)
    fig.suptitle(
        "Er ring laser: surviving pulses vs passive length & pump "
        f"({args.round_trips} round trips, seeded from noise)", fontsize=13)

    summary = []
    t0 = time.time()
    for i, pump in enumerate(pumps):
        for j, length in enumerate(lengths):
            tag = f"L={length} m, pump={pump} W"
            print(f"[{time.time() - t0:6.1f}s] running {tag} ...", flush=True)
            cfg = RingLaserConfig(
                passive_length_m=length,
                pump_power_w=pump,
                round_trips=args.round_trips,
            )
            res = run_ring_laser(cfg)

            final_power = res.time_evolution[-1]
            n_pulses, peak_idx = count_pulses(res.time_ps, final_power)
            energy = res.pulse_energy_nj[-1] if res.pulse_energy_nj.size else 0.0
            summary.append((length, pump, n_pulses, energy))
            print(f"            -> {n_pulses} pulse(s), "
                  f"E={energy:.3f} nJ", flush=True)

            ax = axs[i][j]
            mask = np.abs(res.time_ps) <= COUNT_WINDOW_PS
            ax.plot(res.time_ps[mask], final_power[mask], color="C0", lw=1.2)
            if len(peak_idx):
                tw = res.time_ps[np.abs(res.time_ps) <= COUNT_WINDOW_PS]
                pw = final_power[np.abs(res.time_ps) <= COUNT_WINDOW_PS]
                ax.plot(tw[peak_idx], pw[peak_idx], "rv", ms=6)
            colour = "green" if n_pulses == 1 else "firebrick"
            ax.set_title(f"{tag}\n{n_pulses} pulse(s), {energy:.2f} nJ",
                         fontsize=9, color=colour)
            ax.set_xlabel("Time (ps)")
            ax.set_ylabel("Power (W)")
            ax.grid(True, alpha=0.3)

    fig.tight_layout(rect=[0, 0, 1, 0.95])
    out = "experiments/single_pulse_sweep.png"
    fig.savefig(out, dpi=110)
    print(f"\nSaved {out}")

    print("\n=== summary (pulse count) ===")
    print(f"{'length (m)':>10} {'pump (W)':>9} {'#pulses':>8} {'energy(nJ)':>11}")
    for length, pump, n, e in summary:
        print(f"{length:>10.1f} {pump:>9.2f} {n:>8d} {e:>11.3f}")


if __name__ == "__main__":
    main()
