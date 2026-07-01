"""Pulse shape generation for the GUI."""

from dataclasses import dataclass

import numpy as np

import pulse_engine.grid as plp_grid
import pulse_engine.pulse as plp_pulse


PULSE_SHAPES = ("Gaussian", "Soliton", "Square")


@dataclass
class PulseParams:
    shape: str
    width_fs: float
    amplitude_w: float
    central_wl_nm: float = 1030.0
    max_wl_nm: float = 1600.0
    grid_points: int = 2**11
    repetition_rate_hz: float = 40e6


def _width_seconds(width_fs: float) -> float:
    return width_fs * 1e-15


def preview_intensity(grid, params: PulseParams) -> np.ndarray:
    """Return total intensity profile (W) for the input waveform preview."""
    t = grid.time_window
    width = _width_seconds(params.width_fs)
    amp = params.amplitude_w

    if params.shape == "Gaussian":
        profile = np.exp(-4.0 * np.log(2.0) * (t / width) ** 2)
    elif params.shape == "Soliton":
        tau = width / 1.76
        profile = 1.0 / np.cosh(t / tau) ** 2
    elif params.shape == "Square":
        profile = np.where(np.abs(t) <= width / 2.0, 1.0, 0.0)
    else:
        raise ValueError(f"Unknown pulse shape: {params.shape}")

    peak = np.max(profile)
    if peak > 0:
        profile = profile / peak
    return amp * profile


def build_grid(params: PulseParams):
    wl = params.central_wl_nm * 1e-9
    max_wl = params.max_wl_nm * 1e-9
    return plp_grid.grid(params.grid_points, wl, max_wl)


def create_pulse(grid, params: PulseParams, high_res_sampling: bool = True):
    """Create a pulse_engine pulse object ready for fiber propagation."""
    width = _width_seconds(params.width_fs)
    peak_power = [params.amplitude_w, params.amplitude_w * 1e-3]

    if params.shape == "Gaussian":
        return plp_pulse.pulse(
            width, peak_power, "Gauss", params.repetition_rate_hz, grid,
            high_res_sampling=high_res_sampling)
    if params.shape == "Soliton":
        return plp_pulse.pulse(
            width, peak_power, "sech", params.repetition_rate_hz, grid,
            high_res_sampling=high_res_sampling)
    if params.shape == "Square":
        intensity = preview_intensity(grid, params)
        return plp_pulse.pulse_from_numpy_array(
            grid, intensity, peak_power, params.repetition_rate_hz,
            high_res_sampling=high_res_sampling)

    raise ValueError(f"Unknown pulse shape: {params.shape}")
