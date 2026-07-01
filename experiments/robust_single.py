import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pulse_gui.mode_locked_simulation import RingLaserConfig, run_ring_laser
from pulse_gui.autotune import count_pulses

# Each entry: (pump_w, output_tap_percent, round_trips)
COMBOS = [
    (0.040, 10.0, 350),
    (0.044, 25.0, 350),
    (0.048, 35.0, 350),
    (0.052, 45.0, 350),
]

N_SEEDS = 2


def run_one(pump, tap, trips):
    cfg = RingLaserConfig(pump_power_w=pump, output_tap_percent=tap,
                          round_trips=trips)
    res = run_ring_laser(cfg)
    counts = [count_pulses(res.time_ps, p) for p in res.time_evolution]
    energy = res.pulse_energy_nj[-1] if res.pulse_energy_nj.size else 0.0
    return counts[-1], counts[-15:], energy


if __name__ == "__main__":
    print("pump  tap%  trips | seed | final  last15                      E(nJ)")
    for pump, tap, trips in COMBOS:
        for s in range(N_SEEDS):
            final, tail, energy = run_one(pump, tap, trips)
            lasing = "LASE" if energy > 1e-4 else "dead"
            print(f"{pump:.3f} {tap:4.0f} {trips:5d} | {s}    | "
                  f"{final:5d}  {tail}  {energy:.4f} {lasing}", flush=True)
