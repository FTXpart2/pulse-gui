import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from pulse_gui.mode_locked_simulation import RingLaserConfig, run_ring_laser
from pulse_gui.autotune import count_pulses

TRIPS = 600

cfg = RingLaserConfig(round_trips=TRIPS)
res = run_ring_laser(cfg)
t = res.time_ps
counts = np.array([count_pulses(t, p) for p in res.time_evolution])
energy = res.pulse_energy_nj

# First round trip after which the count is permanently 1.
settle = None
for i in range(len(counts)):
    if np.all(counts[i:] == 1):
        settle = i
        break

print(f"round trips run: {TRIPS}")
print(f"final count: {counts[-1]}  | final energy: {energy[-1]:.4f} nJ")
print(f"count stays == 1 permanently from round trip: {settle}")
print("count trajectory (every 25 trips):")
for i in range(0, len(counts), 25):
    print(f"  rt {i:4d}: {counts[i]} pulse(s), E={energy[i]:.4f} nJ")
print(f"last 30 counts: {list(counts[-30:])}")
print(f"energy std over last 100 trips: {np.std(energy[-100:]):.2e} nJ "
      f"(mean {np.mean(energy[-100:]):.4f} nJ)")
