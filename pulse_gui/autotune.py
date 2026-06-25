"""Closed-loop auto-tuner for the mode-locked ring laser.

Runs the ring-laser simulation repeatedly while adjusting the pump power, using
bisection, to find a setting that produces a target number of surviving pulses.
This is a software analogue of automated mode-locking optimization: pick the
result you want and let it search for the parameter that gets there.

The pulse count rises monotonically with pump in this cavity, so bisection on
pump power converges quickly.
"""

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

import numpy as np
from scipy.signal import find_peaks

from pulse_gui.mode_locked_simulation import RingLaserConfig, run_ring_laser

# Count pulses only within this window (ps) around the cavity centre.
COUNT_WINDOW_PS = 40.0
PEAK_REL_HEIGHT = 0.20
MIN_PULSE_SEP_PS = 1.0


def count_pulses(time_ps: np.ndarray, power: np.ndarray) -> int:
    """Count distinct pulses in a final-round-trip power trace."""
    peak = power.max()
    if peak <= 0 or not np.isfinite(peak):
        return 0
    mask = np.abs(time_ps) <= COUNT_WINDOW_PS
    t, p = time_ps[mask], power[mask]
    if t.size < 3:
        t, p = time_ps, power
    dt_ps = np.median(np.diff(t))
    distance = max(1, int(round(MIN_PULSE_SEP_PS / max(dt_ps, 1e-6))))
    idx, _ = find_peaks(p, height=PEAK_REL_HEIGHT * peak, distance=distance)
    return int(len(idx))


@dataclass
class AutotuneResult:
    success: bool
    target_pulses: int
    found_pump_w: float
    found_count: int
    found_energy_nj: float
    history: List[Tuple[float, int]] = field(default_factory=list)


def autotune_pump(
    base_config: RingLaserConfig,
    target_pulses: int,
    pump_lo: float = 0.02,
    pump_hi: float = 0.30,
    max_iter: int = 8,
    progress_cb: Optional[Callable[[str], None]] = None,
    cancel_cb: Optional[Callable[[], bool]] = None,
) -> AutotuneResult:
    """Bisection search over pump power for a target pulse count."""

    def log(msg: str):
        if progress_cb is not None:
            progress_cb(msg)

    def evaluate(pump: float) -> Tuple[int, float]:
        cfg = RingLaserConfig(**{**base_config.__dict__, "pump_power_w": pump})
        res = run_ring_laser(cfg)
        n = count_pulses(res.time_ps, res.time_evolution[-1])
        e = float(res.pulse_energy_nj[-1]) if res.pulse_energy_nj.size else 0.0
        return n, e

    history: List[Tuple[float, int]] = []
    best = None  # (pump, count, energy)

    lo, hi = pump_lo, pump_hi
    for i in range(max_iter):
        if cancel_cb is not None and cancel_cb():
            log("Cancelled.")
            break
        pump = round((lo + hi) / 2.0, 4)
        log(f"Iteration {i + 1}/{max_iter}: trying pump = {pump:.3f} W ...")
        count, energy = evaluate(pump)
        history.append((pump, count))
        log(f"    -> {count} pulse(s), {energy:.4f} nJ")

        if best is None or abs(count - target_pulses) < abs(best[1] - target_pulses):
            best = (pump, count, energy)

        if count == target_pulses:
            log(f"Hit target of {target_pulses} pulse(s) at "
                f"pump = {pump:.3f} W.")
            return AutotuneResult(True, target_pulses, pump, count, energy,
                                  history)
        if count > target_pulses:
            hi = pump  # too much gain -> lower pump
        else:
            lo = pump  # too little (or no lasing) -> raise pump

    pump, count, energy = best if best else (pump, 0, 0.0)
    success = count == target_pulses
    log(f"Search finished. Closest: {count} pulse(s) at pump = {pump:.3f} W.")
    return AutotuneResult(success, target_pulses, pump, count, energy, history)
