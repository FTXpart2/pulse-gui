"""Mode-locked Er-doped fibre ring laser simulation backend.

Builds a ring cavity from pyLaserPulse catalogue components:

    WDM/isolator/tap -> Er active fibre -> PM1550 passive fibre
        -> saturable absorber -> bandpass filter -> (loop back)

The cavity is seeded with quantum noise and propagated for many round trips
using optical_assemblies.sm_fibre_laser. The tapped output is recorded each
round trip so the GUI can show the laser building up from noise to a pulse.
"""

from dataclasses import dataclass, field

import numpy as np

import pyLaserPulse.grid as grid_mod
import pyLaserPulse.pulse as pulse_mod
import pyLaserPulse.optical_assemblies as oa
import pyLaserPulse.utils as utils
import pyLaserPulse.catalogue_components.active_fibres as af
import pyLaserPulse.catalogue_components.passive_fibres as pf
import pyLaserPulse.catalogue_components.fibre_components as fc
import pyLaserPulse.catalogue_components.bulk_components as bulk

from pulse_gui.saturable_absorber import FastSaturableAbsorber


ER_FIBRES = {
    "nLight Er80-4/125-HD-PM": af.nLight_Er80_4_125_HD_PM,
    "OFS EDF07 PM": af.OFS_EDF07_PM,
    "OFS EDF08 PM": af.OFS_EDF08_PM,
}


@dataclass
class RingLaserConfig:
    er_fibre_name: str = "nLight Er80-4/125-HD-PM"
    active_length_m: float = 0.5
    passive_length_m: float = 10.0
    pump_power_w: float = 0.6
    pump_wavelength_nm: float = 976.0
    output_tap_percent: float = 10.0
    bandpass_transmission: float = 0.85
    round_trips: int = 60
    grid_points: int = 2**11
    central_wl_nm: float = 1550.0
    max_wl_nm: float = 2000.0
    ase_min_nm: float = 960.0
    ase_max_nm: float = 1575.0
    ase_points: int = 2**8
    rep_rate_hz: float = 40e6
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


def run_ring_laser(config: RingLaserConfig) -> RingLaserResult:
    """Run the mode-locked ring laser and return per-round-trip evolution."""
    g = grid_mod.grid(
        config.grid_points, config.central_wl_nm * 1e-9,
        config.max_wl_nm * 1e-9)

    if config.seed_from_noise:
        peak_power = [1e-6, 1e-9]
    else:
        peak_power = [50.0, 0.05]
    seed = pulse_mod.pulse(
        200e-15, peak_power, "Gauss", config.rep_rate_hz, g)

    components = _build_components(g, config, seed.repetition_rate)

    laser = oa.sm_fibre_laser(
        g, components, config.round_trips, "ring laser",
        round_trip_output_samples=config.round_trips,
        plot=False, verbose=config.verbose)

    seed = laser.simulate(seed)

    time_ps = g.time_window * 1e12
    wavelength_nm = g.lambda_window * 1e9

    fields = []
    for sample in seed.output_samples:
        if isinstance(sample, list) and len(sample) > 0:
            fields.append(np.asarray(sample[0]))

    if not fields:
        fields = [seed.field]

    time_evolution = []
    spectral_evolution = []
    pulse_energy_nj = []
    dt = g.dt
    for f in fields:
        power = np.sum(np.abs(f) ** 2, axis=0)
        if np.any(np.isnan(power)):
            power = np.zeros_like(power)
        time_evolution.append(power)
        spectral_evolution.append(_field_to_spectrum(f, config.grid_points))
        pulse_energy_nj.append(np.sum(power) * dt * 1e9)

    return RingLaserResult(
        time_ps=time_ps,
        wavelength_nm=wavelength_nm,
        round_trip=np.arange(len(fields)),
        time_evolution=np.asarray(time_evolution),
        spectral_evolution=np.asarray(spectral_evolution),
        pulse_energy_nj=np.asarray(pulse_energy_nj),
    )
