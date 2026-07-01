"""Mode-locked Er-doped fibre ring laser simulation backend.

Builds a ring cavity from pulse_engine catalogue components:

    WDM/isolator/tap -> Er active fibre -> PM1550 passive fibre
        -> saturable absorber -> bandpass filter -> (loop back)

The cavity is seeded with quantum noise and propagated for many round trips
using optical_assemblies.sm_fibre_laser. The tapped output is recorded each
round trip so the GUI can show the laser building up from noise to a pulse.
"""

from dataclasses import dataclass, field

import numpy as np

import pulse_engine.grid as grid_mod
import pulse_engine.pulse as pulse_mod
import pulse_engine.optical_assemblies as oa
import pulse_engine.utils as utils
import pulse_engine.catalogue_components.active_fibres as af
import pulse_engine.catalogue_components.passive_fibres as pf
import pulse_engine.catalogue_components.fibre_components as fc
import pulse_engine.catalogue_components.bulk_components as bulk

from pulse_gui.saturable_absorber import FastSaturableAbsorber


ER_FIBRES = {
    "nLight Er80-4/125-HD-PM": af.nLight_Er80_4_125_HD_PM,
    "OFS EDF07 PM": af.OFS_EDF07_PM,
    "OFS EDF08 PM": af.OFS_EDF08_PM,
}


@dataclass
class RingLaserConfig:
    er_fibre_name: str = "nLight Er80-4/125-HD-PM"
    active_length_m: float = 0.25
    passive_length_m: float = 5.0
    pump_power_w: float = 0.040
    pump_wavelength_nm: float = 976.0
    output_tap_percent: float = 10.0
    bandpass_transmission: float = 0.85
    round_trips: int = 300
    loop_to_steady_state: bool = True
    batch_round_trips: int = 10
    steady_state_window: int = 25
    steady_state_tol: float = 0.02
    grid_points: int = 2**11
    central_wl_nm: float = 1550.0
    max_wl_nm: float = 2000.0
    ase_min_nm: float = 960.0
    ase_max_nm: float = 1575.0
    ase_points: int = 2**8
    rep_rate_hz: float = 40e6
    derive_rep_rate: bool = True
    group_index: float = 1.468
    sa_mod_depth: float = 0.3
    sa_sat_power_w: float = 300.0
    seed_from_noise: bool = True
    verbose: bool = False


@dataclass
class RingLaserResult:
    time_ps: np.ndarray
    wavelength_nm: np.ndarray
    round_trip: np.ndarray = field(default_factory=lambda: np.array([]))
    time_evolution: np.ndarray = field(default_factory=lambda: np.array([]))
    spectral_evolution: np.ndarray = field(default_factory=lambda: np.array([]))
    pulse_energy_nj: np.ndarray = field(default_factory=lambda: np.array([]))
    rep_rate_hz: float = 0.0
    cavity_length_m: float = 0.0
    converged: bool = False
    round_trips_run: int = 0


# Speed of light (m/s).
_C = 299792458.0


def cavity_rep_rate(config: "RingLaserConfig") -> float:
    """Fundamental repetition rate from the round-trip time of the cavity.

    f_rep = c / (n_g * L_cavity), where L_cavity is the total fibre length and
    n_g is the group index of the fibre (~1.468 for silica near 1550 nm).
    """
    cavity_length = config.active_length_m + config.passive_length_m
    return _C / (config.group_index * cavity_length)


def _build_components(g, config: RingLaserConfig, rep_rate: float):
    split_fraction = 1.0 - config.output_tap_percent / 100.0

    wdm_iso_tap = fc.DKPhotonics_P_WDM_iso_tap_980_1550(
        g, 0.5, 0.5, split_fraction, output_coupler=True,
        verbose=config.verbose)

    bounds = {
        "co_pump_power": config.pump_power_w,
        "co_pump_wavelength": config.pump_wavelength_nm * 1e-9,
        "co_pump_bandwidth": 1e-9,
    }
    er_cls = ER_FIBRES[config.er_fibre_name]
    er_fibre = er_cls(
        g, config.active_length_m, rep_rate, config.ase_points,
        [config.ase_min_nm * 1e-9, config.ase_max_nm * 1e-9],
        bounds, time_domain_gain=False, verbose=config.verbose)

    passive = pf.PM1550_XP(g, config.passive_length_m, 1e-5)

    sa = FastSaturableAbsorber(
        g, mod_depth=config.sa_mod_depth, sat_power=config.sa_sat_power_w,
        verbose=config.verbose)

    bandpass = bulk.Andover_155FS10_25_bandpass(
        g, peak_transmission=config.bandpass_transmission)

    # Order matters for the assembly's automatic coupling-loss insertion:
    # bulk components (SA, bandpass) must sit between actual fibres, and the
    # loop seam (last -> first) must be fibre-to-fibre. WDM/tap is therefore
    # adjacent only to fibres (Er fibre after it, passive fibre before it).
    return [wdm_iso_tap, er_fibre, sa, bandpass, passive]


def _field_to_spectrum(field_array, n_points):
    spec = utils.fftshift(utils.fft(field_array, axis=-1), axes=-1)
    return np.sum(np.abs(spec) ** 2, axis=0)


def _extract_fields(seed):
    """Pull the tapped output field for each sampled round trip."""
    fields = []
    for sample in seed.output_samples:
        if isinstance(sample, list) and len(sample) > 0:
            fields.append(np.asarray(sample[0]))
    return fields


def _count_peaks(power, dt):
    """Lightweight pulse counter used for the steady-state check.

    Counts peaks above 20% of the maximum, separated by at least 1 ps, within
    a 40 ps window around the dominant peak. Kept local to avoid importing the
    autotune module (which imports this module)."""
    peak = power.max()
    if not np.isfinite(peak) or peak <= 0:
        return 0
    try:
        from scipy.signal import find_peaks
    except Exception:  # pragma: no cover - scipy always present in practice
        return 1
    min_sep = max(1, int(round(1e-12 / dt)))
    peaks, _ = find_peaks(power, height=0.20 * peak, distance=min_sep)
    return int(len(peaks)) if len(peaks) else 1


def _is_steady_state(energies, counts, window, tol):
    """True if pulse energy and pulse count have both settled over `window`."""
    if len(energies) < window:
        return False
    recent_e = np.asarray(energies[-window:])
    mean_e = recent_e.mean()
    if mean_e <= 0:
        return False
    if recent_e.std() / mean_e > tol:
        return False
    recent_c = counts[-window:]
    if len(set(recent_c)) != 1 or recent_c[-1] < 1:
        return False
    return True


def run_ring_laser(config: RingLaserConfig) -> RingLaserResult:
    """Run the mode-locked ring laser and return per-round-trip evolution.

    With ``config.loop_to_steady_state`` the cavity is propagated in batches of
    ``batch_round_trips`` and stops automatically once the output pulse energy
    and pulse count have settled (relative energy std over ``steady_state_window``
    round trips below ``steady_state_tol`` and a constant pulse count), up to a
    maximum of ``round_trips``. Otherwise a single fixed run of ``round_trips``
    is performed.
    """
    g = grid_mod.grid(
        config.grid_points, config.central_wl_nm * 1e-9,
        config.max_wl_nm * 1e-9)
    dt = g.dt
    time_ps = g.time_window * 1e12
    wavelength_nm = g.lambda_window * 1e9

    rep_rate = cavity_rep_rate(config) if config.derive_rep_rate \
        else config.rep_rate_hz

    if config.seed_from_noise:
        peak_power = [1e-6, 1e-9]
    else:
        peak_power = [50.0, 0.05]
    seed = pulse_mod.pulse(
        200e-15, peak_power, "Gauss", rep_rate, g)

    components = _build_components(g, config, seed.repetition_rate)

    time_evolution = []
    spectral_evolution = []
    pulse_energy_nj = []
    counts = []
    converged = False

    def _absorb(fields):
        for f in fields:
            power = np.sum(np.abs(f) ** 2, axis=0)
            if np.any(np.isnan(power)):
                power = np.zeros_like(power)
            time_evolution.append(power)
            spectral_evolution.append(
                _field_to_spectrum(f, config.grid_points))
            pulse_energy_nj.append(np.sum(power) * dt * 1e9)
            counts.append(_count_peaks(power, dt))

    if config.loop_to_steady_state:
        batch = max(1, int(config.batch_round_trips))
        window = max(2, int(config.steady_state_window))
        max_trips = int(config.round_trips)
        laser = oa.sm_fibre_laser(
            g, components, batch, "ring laser",
            round_trip_output_samples=batch, plot=False,
            verbose=config.verbose)
        run = 0
        while run < max_trips:
            this_batch = min(batch, max_trips - run)
            laser.round_trips = this_batch
            laser.round_trip_output_samples = this_batch
            seed.output_samples = []
            seed = laser.simulate(seed)
            batch_fields = _extract_fields(seed)
            if not batch_fields:
                break
            _absorb(batch_fields)
            run += len(batch_fields)
            if np.any(np.isnan(seed.field)):
                break
            if _is_steady_state(pulse_energy_nj, counts, window,
                                config.steady_state_tol):
                converged = True
                break
    else:
        laser = oa.sm_fibre_laser(
            g, components, config.round_trips, "ring laser",
            round_trip_output_samples=config.round_trips,
            plot=False, verbose=config.verbose)
        seed = laser.simulate(seed)
        fields = _extract_fields(seed)
        if not fields:
            fields = [seed.field]
        _absorb(fields)

    if not time_evolution:
        power = np.sum(np.abs(seed.field) ** 2, axis=0)
        time_evolution.append(power)
        spectral_evolution.append(
            _field_to_spectrum(seed.field, config.grid_points))
        pulse_energy_nj.append(np.sum(power) * dt * 1e9)

    return RingLaserResult(
        time_ps=time_ps,
        wavelength_nm=wavelength_nm,
        round_trip=np.arange(len(time_evolution)),
        time_evolution=np.asarray(time_evolution),
        spectral_evolution=np.asarray(spectral_evolution),
        pulse_energy_nj=np.asarray(pulse_energy_nj),
        rep_rate_hz=rep_rate,
        cavity_length_m=config.active_length_m + config.passive_length_m,
        converged=converged,
        round_trips_run=len(time_evolution),
    )
