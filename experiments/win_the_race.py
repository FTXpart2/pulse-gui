"""Experiment: can a single pulse win the race? (5 m passive fibre)

Starts from noise (many pulses) and uses an aggressive fast saturable absorber
(high modulation depth + LOW saturation power so real pulses bleach it but the
noise background does not). Tracks the number of surviving pulses at every
recorded round trip so we can watch the "race" play out, and reports whether it
collapses to a single pulse.

Run from the repo root:
    .venv\\Scripts\\python.exe experiments\\win_the_race.py
Optional:
    --sat-power W   SA saturation power (default 12)
    --mod-depth D   SA modulation depth (default 0.8)
    --pump P        pump power W (default 0.4)
    --trips N       round trips (default 250)
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
    parser.add_argument("--sat-power", type=float, default=12.0)
    parser.add_argument("--mod-depth", type=float, default=0.8)
    parser.add_argument("--pump", type=float, default=0.4)
    parser.add_argument("--trips", type=int, default=250)
    args = parser.parse_args()

    print(f"5 m passive fibre, pump={args.pump} W, "
          f"SA mod_depth={args.mod_depth}, sat_power={args.sat_power} W, "
          f"{args.trips} round trips", flush=True)
    t0 = time.time()
    cfg = RingLaserConfig(
        passive_length_m=5.0,
        pump_power_w=args.pump,
        round_trips=args.trips,
        sa_mod_depth=args.mod_depth,
        sa_sat_power_w=args.sat_power,
        seed_from_noise=True,
    )
    res = run_ring_laser(cfg)
    print(f"simulation done in {time.time() - t0:.1f}s", flush=True)

    # Count pulses at every recorded round trip -> the "race" curve.
    counts = np.array([count_pulses(res.time_ps, p)[0]
                       for p in res.time_evolution])
    trips = res.round_trip
    final_power = res.time_evolution[-1]
    n_final, peak_idx = count_pulses(res.time_ps, final_power)
    energy = res.pulse_energy_nj[-1] if res.pulse_energy_nj.size else 0.0

    fig = plt.figure(figsize=(13, 7))
    fig.suptitle(
        f"Single-pulse race (5 m, pump={args.pump} W, "
        f"SA q0={args.mod_depth}, Psat={args.sat_power} W) -> "
        f"final: {n_final} pulse(s), {energy:.3f} nJ",
        fontsize=12, color=("green" if n_final == 1 else "firebrick"))

    # Race curve: pulse count vs round trip.
    ax1 = fig.add_subplot(2, 2, 1)
    ax1.plot(trips, counts, color="C3", lw=1.5)
    ax1.set_xlabel("Round trip")
    ax1.set_ylabel("# pulses")
    ax1.set_title("The race: pulse count vs round trip")
    ax1.grid(True, alpha=0.3)

    # Energy vs round trip.
    ax2 = fig.add_subplot(2, 2, 2)
    ax2.plot(trips, res.pulse_energy_nj, color="C2", lw=1.5)
    ax2.set_xlabel("Round trip")
    ax2.set_ylabel("Energy (nJ)")
    ax2.set_title("Pulse energy vs round trip")
    ax2.grid(True, alpha=0.3)

    # Final round-trip time trace.
    ax3 = fig.add_subplot(2, 2, 3)
    mask = np.abs(res.time_ps) <= COUNT_WINDOW_PS
    tw, pw = res.time_ps[mask], final_power[mask]
    ax3.plot(tw, pw, color="C0", lw=1.2)
    if len(peak_idx):
        ax3.plot(tw[peak_idx], pw[peak_idx], "rv", ms=6)
    ax3.set_xlabel("Time (ps)")
    ax3.set_ylabel("Power (W)")
    ax3.set_title(f"Final round trip ({n_final} pulse(s))")
    ax3.grid(True, alpha=0.3)

    # Evolution map (time vs round trip).
    ax4 = fig.add_subplot(2, 2, 4)
    evo = res.time_evolution[:, mask]
    ax4.imshow(evo, aspect="auto", origin="lower", cmap="inferno",
               extent=[tw.min(), tw.max(), trips.min(), trips.max()])
    ax4.set_xlabel("Time (ps)")
    ax4.set_ylabel("Round trip")
    ax4.set_title("Temporal evolution")

    fig.tight_layout(rect=[0, 0, 1, 0.95])
    out = "experiments/win_the_race.png"
    fig.savefig(out, dpi=110)
    print(f"Saved {out}", flush=True)
    print(f"\nPulse count: start={counts[0]}, min={counts.min()}, "
          f"final={n_final}", flush=True)


if __name__ == "__main__":
    main()
