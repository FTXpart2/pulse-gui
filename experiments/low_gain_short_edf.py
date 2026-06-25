"""Experiment: short EDF (0.25 m) + low pump -> fewer pulses?

Reduces the active Er fibre to 0.25 m and sweeps low pump powers (passive fibre
fixed at 5 m). Lower gain -> lower intracavity energy and less ASE, which may
drop the laser below the multi-pulsing threshold. Reports surviving pulse count
and the pulse-count-vs-round-trip "race" curve for each pump.

Run from the repo root:
    .venv\\Scripts\\python.exe experiments\\low_gain_short_edf.py
Optional:
    --pumps a,b,c     pump powers in W (default 0.15,0.25,0.35)
    --edf L           active fibre length m (default 0.25)
    --trips N         round trips (default 150)
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
    parser.add_argument("--pumps", type=str, default="0.15,0.25,0.35")
    parser.add_argument("--edf", type=float, default=0.25)
    parser.add_argument("--passive", type=float, default=5.0)
    parser.add_argument("--trips", type=int, default=150)
    args = parser.parse_args()

    pumps = [float(x) for x in args.pumps.split(",")]
    ncols = len(pumps)
    fig, axs = plt.subplots(2, ncols, figsize=(4.2 * ncols, 6.4),
                            squeeze=False)
    fig.suptitle(
        f"EDF={args.edf} m, passive={args.passive} m, "
        f"{args.trips} round trips - low-gain pump sweep", fontsize=13)

    summary = []
    t0 = time.time()
    for j, pump in enumerate(pumps):
        print(f"[{time.time() - t0:6.1f}s] pump={pump} W ...", flush=True)
        cfg = RingLaserConfig(
            active_length_m=args.edf,
            passive_length_m=args.passive,
            pump_power_w=pump,
            round_trips=args.trips,
            seed_from_noise=True,
        )
        res = run_ring_laser(cfg)
        final_power = res.time_evolution[-1]
        n_final, peak_idx = count_pulses(res.time_ps, final_power)
        energy = res.pulse_energy_nj[-1] if res.pulse_energy_nj.size else 0.0
        counts = np.array([count_pulses(res.time_ps, p)[0]
                           for p in res.time_evolution])
        summary.append((pump, n_final, energy, counts.min()))
        print(f"            -> final {n_final} pulse(s), E={energy:.3f} nJ, "
              f"min over race={counts.min()}", flush=True)

        # Top row: final round-trip trace.
        ax = axs[0][j]
        mask = np.abs(res.time_ps) <= COUNT_WINDOW_PS
        tw, pw = res.time_ps[mask], final_power[mask]
        ax.plot(tw, pw, color="C0", lw=1.2)
        if len(peak_idx):
            ax.plot(tw[peak_idx], pw[peak_idx], "rv", ms=6)
        colour = "green" if n_final == 1 else "firebrick"
        ax.set_title(f"pump={pump} W\nfinal {n_final} pulse(s), {energy:.2f} nJ",
                     fontsize=9, color=colour)
        ax.set_xlabel("Time (ps)")
        ax.set_ylabel("Power (W)")
        ax.grid(True, alpha=0.3)

        # Bottom row: the race curve.
        ax2 = axs[1][j]
        ax2.plot(res.round_trip, counts, color="C3", lw=1.2)
        ax2.set_xlabel("Round trip")
        ax2.set_ylabel("# pulses")
        ax2.set_title(f"race (min={counts.min()})", fontsize=9)
        ax2.grid(True, alpha=0.3)

    fig.tight_layout(rect=[0, 0, 1, 0.94])
    out = "experiments/low_gain_short_edf.png"
    fig.savefig(out, dpi=110)
    print(f"\nSaved {out}", flush=True)

    print("\n=== summary ===")
    print(f"{'pump(W)':>8} {'final#':>7} {'energy(nJ)':>11} {'min#':>6}")
    for pump, n, e, mn in summary:
        flag = "  <== SINGLE" if n == 1 else ""
        print(f"{pump:>8.2f} {n:>7d} {e:>11.3f} {mn:>6d}{flag}")


if __name__ == "__main__":
    main()
