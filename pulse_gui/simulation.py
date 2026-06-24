"""Fiber propagation simulation wrapper around pyLaserPulse."""

from dataclasses import dataclass, field

import numpy as np

import pyLaserPulse.catalogue_components.passive_fibres as pf
import pyLaserPulse.optical_assemblies as oa

from pulse_gui.pulse_shapes import PulseParams, build_grid, create_pulse


def _make_smf28(grid, length, verbose):
    return pf.SMF_28(grid, length, 1e-2, 1e-8, verbose=verbose)


def _make_hi1060(grid, length, verbose):
    return pf.Corning_HI1060(grid, length, 1e-2, 1e-8, verbose=verbose)


def _make_nkt_sc(grid, length, verbose):
    return pf.NKT_SC_5_1040_PM(grid, length, 1e-8, verbose=verbose)


def _make_nkt_neg(grid, length, verbose):
    return pf.NKT_NL_1050_NEG_1(grid, length, 1e-8, 1e-2, verbose=verbose)


FIBRE_OPTIONS = {
    "SMF-28 (Corning)": _make_smf28,
    "HI1060 (Corning)": _make_hi1060,
    "NKT SC-5.0-1040-PM": _make_nkt_sc,
    "NKT NL-1050-NEG-1": _make_nkt_neg,
}


@dataclass
class SimulationConfig:
    pulse: PulseParams
    fibre_name: str = "NKT SC-5.0-1040-PM"
    fibre_length_m: float = 1.0
    num_samples: int = 80
    verbose: bool = False


@dataclass
class SimulationResult:
    time_ps: np.ndarray
    wavelength_nm: np.ndarray
    z_m: np.ndarray = field(default_factory=lambda: np.array([]))
    input_intensity: np.ndarray = field(default_factory=lambda: np.array([]))
    time_evolution: np.ndarray = field(default_factory=lambda: np.array([]))
    spectral_evolution: np.ndarray = field(default_factory=lambda: np.array([]))
    step_intensity: np.ndarray = field(default_factory=lambda: np.array([]))
    step_spectrum: np.ndarray = field(default_factory=lambda: np.array([]))


def _make_fibre(grid, config: SimulationConfig):
    factory = FIBRE_OPTIONS[config.fibre_name]
    return factory(grid, config.fibre_length_m, config.verbose)


def run_simulation(config: SimulationConfig) -> SimulationResult:
    """Run passive-fibre propagation and collect time/spectral evolution data."""
    grid = build_grid(config.pulse)
    pulse_obj = create_pulse(grid, config.pulse, high_res_sampling=True)

    input_intensity = np.sum(np.abs(pulse_obj.field) ** 2, axis=0)
    fibre = _make_fibre(grid, config)
    assembly = oa.passive_assembly(
        grid, [fibre], "gui_sim",
        high_res_sampling=config.num_samples,
        plot=False, verbose=config.verbose)

    pulse_obj = assembly.simulate(pulse_obj)

    time_ps = grid.time_window * 1e12
    wavelength_nm = grid.lambda_window * 1e9

    if pulse_obj.high_res_field_samples:
        time_evolution = np.sum(
            np.abs(np.asarray(pulse_obj.high_res_field_samples)) ** 2, axis=1)
        z_m = np.cumsum(pulse_obj.high_res_field_sample_points)
        pulse_obj.get_ESD_and_PSD_from_high_res_field_samples(grid)
        spectral_evolution = np.asarray(pulse_obj.high_res_PSD_samples)
    else:
        time_evolution = np.sum(np.abs(pulse_obj.field) ** 2, axis=0, keepdims=True)
        z_m = np.array([config.fibre_length_m])
        pulse_obj.get_ESD_and_PSD(grid, pulse_obj.field)
        spectral_evolution = np.sum(
            pulse_obj.power_spectral_density, axis=0, keepdims=True)

    return SimulationResult(
        time_ps=time_ps,
        wavelength_nm=wavelength_nm,
        z_m=z_m,
        input_intensity=input_intensity,
        time_evolution=time_evolution,
        spectral_evolution=spectral_evolution,
        step_intensity=time_evolution[0],
        step_spectrum=spectral_evolution[0],
    )
