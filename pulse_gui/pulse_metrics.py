"""Automatic pulse and spectrum measurements for GUI feedback."""

from dataclasses import dataclass, field

import numpy as np

try:
    from scipy.optimize import curve_fit
except ImportError:  # pragma: no cover
    curve_fit = None

_LOG2 = np.log(2.0)
_SECH2_FWHM_FACTOR = 2.0 * np.arccosh(np.sqrt(2.0))  # FWHM = factor * tau


@dataclass
class ShapeFit:
    """Least-squares fit of a pulse shape to the time-domain power trace."""

    shape: str = ""
    amplitude_w: float = float("nan")
    center_ps: float = float("nan")
    fwhm_ps: float = float("nan")
    rmse: float = float("nan")

    @property
    def valid(self) -> bool:
        return (self.shape
                and np.isfinite(self.fwhm_ps)
                and self.fwhm_ps > 0
                and np.isfinite(self.amplitude_w))


@dataclass
class PulseMetrics:
    """Measured quantities for the current time/spectrum trace."""

    peak_power_w: float = 0.0
    time_fwhm_ps: float = float("nan")
    time_peak_ps: float = float("nan")
    time_fwhm_left_ps: float = float("nan")
    time_fwhm_right_ps: float = float("nan")
    spectral_peak: float = 0.0
    spectral_fwhm_nm: float = float("nan")
    spectral_peak_nm: float = float("nan")
    spectral_fwhm_left_nm: float = float("nan")
    spectral_fwhm_right_nm: float = float("nan")
    gaussian_fit: ShapeFit = field(default_factory=ShapeFit)
    sech2_fit: ShapeFit = field(default_factory=ShapeFit)
    best_fit: ShapeFit = field(default_factory=ShapeFit)

    @property
    def valid(self) -> bool:
        return np.isfinite(self.peak_power_w) and self.peak_power_w > 0


def _gaussian(t, amp, t0, fwhm):
    sigma = max(fwhm, 1e-12) / (2.0 * np.sqrt(_LOG2))
    return amp * np.exp(-((t - t0) / sigma) ** 2)


def _sech2(t, amp, t0, fwhm):
    tau = max(fwhm, 1e-12) / _SECH2_FWHM_FACTOR
    return amp / np.cosh((t - t0) / tau) ** 2


def _fit_shape(time_ps, power, model, shape_name, amp0, t0, fwhm0):
    if curve_fit is None:
        return ShapeFit(shape=shape_name)
    t = np.asarray(time_ps, dtype=float)
    y = np.asarray(power, dtype=float)
    if y.size < 8 or amp0 <= 0 or not np.isfinite(fwhm0) or fwhm0 <= 0:
        return ShapeFit(shape=shape_name)

    peak_idx = int(np.argmax(y))
    half_win = max(3.0 * fwhm0, 5.0)
    mask = ((t >= t[peak_idx] - half_win)
            & (t <= t[peak_idx] + half_win)
            & (y > 0.05 * amp0))
    if mask.sum() < 8:
        mask = np.ones_like(y, dtype=bool)

    t_fit = t[mask]
    y_fit = y[mask]
    p0 = (amp0, t0, fwhm0)
    bounds = (
        (0.0, t.min(), 1e-4),
        (max(amp0 * 5.0, amp0 + 1e-12), t.max(), min(100.0, (t.max() - t.min()))),
    )
    try:
        popt, _ = curve_fit(
            model, t_fit, y_fit, p0=p0, bounds=bounds, maxfev=8000)
        amp, tc, fwhm = map(float, popt)
        if fwhm <= 0 or amp <= 0:
            return ShapeFit(shape=shape_name)
        pred = model(t_fit, amp, tc, fwhm)
        rmse = float(np.sqrt(np.mean((pred - y_fit) ** 2)))
        return ShapeFit(shape_name, amp, tc, fwhm, rmse)
    except (RuntimeError, ValueError, OverflowError):
        return ShapeFit(shape=shape_name)


def fit_pulse_shapes(time_ps, power, t_peak=None, fwhm_guess=None):
    """Fit Gaussian and sech² profiles; pick the lower-RMSE model."""
    power = np.asarray(power, dtype=float)
    time_ps = np.asarray(time_ps, dtype=float)
    if power.size == 0 or power.max() <= 0:
        empty = ShapeFit()
        return empty, empty, empty

    peak_idx = int(np.argmax(power))
    amp0 = float(power[peak_idx])
    t0 = float(t_peak if t_peak is not None else time_ps[peak_idx])
    if fwhm_guess is None or not np.isfinite(fwhm_guess) or fwhm_guess <= 0:
        fwhm0 = 1.0
    else:
        fwhm0 = float(fwhm_guess)

    if amp0 / max(float(np.median(power)), 1e-30) < 2.5:
        empty = ShapeFit()
        return empty, empty, empty

    gauss = _fit_shape(time_ps, power, _gaussian, "Gaussian", amp0, t0, fwhm0)
    sech = _fit_shape(time_ps, power, _sech2, "Sech²", amp0, t0, fwhm0)

    best = ShapeFit()
    if gauss.valid and sech.valid:
        best = gauss if gauss.rmse <= sech.rmse else sech
    elif gauss.valid:
        best = gauss
    elif sech.valid:
        best = sech
    return gauss, sech, best


def evaluate_fit(time_ps, fit: ShapeFit):
    """Return fitted power trace for plotting."""
    if not fit.valid:
        return None
    t = np.asarray(time_ps, dtype=float)
    if fit.shape == "Gaussian":
        return _gaussian(t, fit.amplitude_w, fit.center_ps, fit.fwhm_ps)
    if fit.shape == "Sech²":
        return _sech2(t, fit.amplitude_w, fit.center_ps, fit.fwhm_ps)
    return None


def _interp_crossing(x0, y0, x1, y1, level):
    if y1 == y0:
        return 0.5 * (x0 + x1)
    return x0 + (level - y0) * (x1 - x0) / (y1 - y0)


def _half_max_width(x, y):
    """Return (peak_value, peak_position, fwhm, x_left, x_right) for data."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.size == 0 or y.size == 0:
        return 0.0, float("nan"), float("nan"), float("nan"), float("nan")

    i_peak = int(np.argmax(y))
    peak_val = float(y[i_peak])
    peak_pos = float(x[i_peak])
    if peak_val <= 0 or not np.isfinite(peak_val):
        return peak_val, peak_pos, float("nan"), float("nan"), float("nan")

    level = 0.5 * peak_val

    i_left = i_peak
    while i_left > 0 and y[i_left] >= level:
        i_left -= 1
    if i_left >= i_peak:
        x_left = peak_pos
    elif y[i_left] < level:
        x_left = _interp_crossing(x[i_left], y[i_left],
                                  x[i_left + 1], y[i_left + 1], level)
    else:
        x_left = float(x[i_left])

    i_right = i_peak
    while i_right < len(y) - 1 and y[i_right] >= level:
        i_right += 1
    if i_right <= i_peak:
        x_right = peak_pos
    elif y[i_right] < level:
        x_right = _interp_crossing(x[i_right - 1], y[i_right - 1],
                                   x[i_right], y[i_right], level)
    else:
        x_right = float(x[i_right])

    width = abs(x_right - x_left)
    if width <= 0 or not np.isfinite(width):
        return peak_val, peak_pos, float("nan"), float("nan"), float("nan")
    return peak_val, peak_pos, width, x_left, x_right


def measure(time_ps, power, wavelength_nm, spectrum) -> PulseMetrics:
    """Measure peak power, FWHM, spectral width, and analytic pulse fits."""
    power = np.asarray(power, dtype=float)
    spectrum = np.asarray(spectrum, dtype=float)

    p_peak, t_peak, t_fwhm, t_left, t_right = _half_max_width(time_ps, power)
    s_peak, wl_peak, s_fwhm, wl_left, wl_right = _half_max_width(
        wavelength_nm, spectrum)
    gauss, sech, best = fit_pulse_shapes(time_ps, power, t_peak, t_fwhm)

    return PulseMetrics(
        peak_power_w=p_peak,
        time_fwhm_ps=t_fwhm,
        time_peak_ps=t_peak,
        time_fwhm_left_ps=t_left,
        time_fwhm_right_ps=t_right,
        spectral_peak=s_peak,
        spectral_fwhm_nm=s_fwhm,
        spectral_peak_nm=wl_peak,
        spectral_fwhm_left_nm=wl_left,
        spectral_fwhm_right_nm=wl_right,
        gaussian_fit=gauss,
        sech2_fit=sech,
        best_fit=best,
    )


def _fmt_power(w):
    if not np.isfinite(w) or w <= 0:
        return "—"
    if w >= 1.0:
        return f"{w:.3f} W"
    if w >= 1e-3:
        return f"{w * 1e3:.2f} mW"
    return f"{w * 1e6:.2f} µW"


def _fmt_duration(ps):
    if not np.isfinite(ps) or ps <= 0:
        return "—"
    if ps >= 1.0:
        return f"{ps:.2f} ps"
    return f"{ps * 1e3:.1f} fs"


def _fmt_width_nm(nm):
    if not np.isfinite(nm) or nm <= 0:
        return "—"
    if nm >= 1.0:
        return f"{nm:.2f} nm"
    return f"{nm * 1e3:.1f} pm"


def _fmt_spectral_peak(val):
    if not np.isfinite(val) or val <= 0:
        return "—"
    if val >= 1e4:
        return f"{val:.3e}"
    return f"{val:.3g}"


def _fit_line(label: str, fit: ShapeFit) -> str:
    if not fit.valid:
        return f"&nbsp;&nbsp;{label}:&nbsp;&nbsp;—<br>"
    return (
        f"&nbsp;&nbsp;{label} FWHM:&nbsp;&nbsp;{_fmt_duration(fit.fwhm_ps)}"
        f"&nbsp;&nbsp;(RMSE {fit.rmse:.2e})<br>"
    )


def format_metrics_html(m: PulseMetrics) -> str:
    """HTML snippet for the metrics panel."""
    best_line = ""
    if m.best_fit.valid:
        best_line = (
            f"<br><b>Best fit</b> ({m.best_fit.shape}): "
            f"{_fmt_duration(m.best_fit.fwhm_ps)}<br>"
        )
    return (
        "<b>Time domain</b><br>"
        f"&nbsp;&nbsp;Peak power:&nbsp;&nbsp;{_fmt_power(m.peak_power_w)}<br>"
        f"&nbsp;&nbsp;FWHM (measured):&nbsp;&nbsp;{_fmt_duration(m.time_fwhm_ps)}"
        f"&nbsp;&nbsp;(at {m.time_peak_ps:.2f} ps)<br>"
        "<br><b>Pulse fitting</b><br>"
        + _fit_line("Gaussian", m.gaussian_fit)
        + _fit_line("Sech²", m.sech2_fit)
        + best_line
        + "<br><b>Spectrum</b><br>"
        f"&nbsp;&nbsp;Peak density:&nbsp;&nbsp;{_fmt_spectral_peak(m.spectral_peak)}"
        f"&nbsp;&nbsp;(at {m.spectral_peak_nm:.1f} nm)<br>"
        f"&nbsp;&nbsp;3 dB width:&nbsp;&nbsp;{_fmt_width_nm(m.spectral_fwhm_nm)}"
    )
