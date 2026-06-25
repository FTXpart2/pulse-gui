"""Rule-based parameter advisor for the pulse-gui.

Given a simulation mode ("passive" or "ring"), a desired goal, and the current
parameter values, this returns concrete, physics-motivated suggestions for what
to change. The relationships encoded here come from the GNLSE physics and from
the empirical sweeps run on this cavity (e.g. lower gain near threshold ->
single pulse; longer passive fibre -> more SPM broadening; etc.).

The advisor is deterministic and instant - it does not run simulations.
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Suggestion:
    """A recommended set of parameter changes toward a goal."""
    summary: str
    reasoning: str
    # canonical_key -> target value
    changes: Dict[str, float | str] = field(default_factory=dict)


# Goals available per mode (order matters: first is the default).
GOALS = {
    "ring": [
        "Single pulse (win the race)",
        "Harmonic mode-locking (a few pulses)",
        "Higher pulse energy",
        "Broader optical spectrum",
        "Cleaner / suppress noise background",
    ],
    "passive": [
        "Maximize spectral broadening (SPM)",
        "Preserve input shape (near-linear)",
        "Stronger nonlinear / soliton dynamics",
    ],
}

# Human-readable labels + units for each canonical parameter key.
PARAM_LABELS = {
    "active_length_m": ("EDF (active) length", "m"),
    "passive_length_m": ("Passive fiber length", "m"),
    "pump_power_w": ("Pump power", "W"),
    "round_trips": ("Round trips", ""),
    "sa_mod_depth": ("SA modulation depth", ""),
    "sa_sat_power_w": ("SA saturation power", "W"),
    "bandpass_transmission": ("Bandpass transmission", ""),
    "output_tap_percent": ("Output tap", "%"),
    "width_fs": ("Pulse width", "fs"),
    "amplitude_w": ("Amplitude", "W"),
    "fibre_length_m": ("Fiber length", "m"),
    "fibre_name": ("Fiber", ""),
    "shape": ("Pulse shape", ""),
}


def _ring_suggestion(goal: str) -> Suggestion:
    if goal.startswith("Single pulse"):
        return Suggestion(
            summary="Drop the cavity to just above lasing threshold so the "
                    "energy budget supports only one pulse.",
            reasoning=(
                "Multi-pulsing happens when the round-trip energy exceeds what "
                "a single pulse can hold. Shortening the gain fiber and pumping "
                "near threshold lowers the intracavity energy until only one "
                "pulse survives; gain competition then lets the strongest "
                "fluctuation win the race. Many round trips (~130+) are needed "
                "for the losers to die off."),
            changes={
                "active_length_m": 0.25,
                "passive_length_m": 5.0,
                "pump_power_w": 0.040,
                "round_trips": 250,
                "sa_mod_depth": 0.3,
                "sa_sat_power_w": 300.0,
            },
        )
    if goal.startswith("Harmonic"):
        return Suggestion(
            summary="Raise the gain a little above the single-pulse threshold "
                    "to support a stable train of a few evenly-spaced pulses.",
            reasoning=(
                "Just above threshold the cavity supports a stable, ordered "
                "(harmonic) multi-pulse state. More pump -> more pulses; the "
                "count rises roughly linearly with pump in this cavity "
                "(~0.04 W -> 1 pulse, ~0.10 W -> 6 pulses)."),
            changes={
                "active_length_m": 0.25,
                "passive_length_m": 5.0,
                "pump_power_w": 0.10,
                "round_trips": 200,
            },
        )
    if goal.startswith("Higher pulse energy"):
        return Suggestion(
            summary="Increase gain (longer EDF + more pump) for higher energy, "
                    "accepting that the laser will multi-pulse.",
            reasoning=(
                "Energy scales with available gain, so a longer active fiber "
                "and higher pump raise the per-round-trip energy. Note the "
                "trade-off: above the single-pulse threshold the extra energy "
                "splits into multiple pulses rather than one larger pulse."),
            changes={
                "active_length_m": 0.5,
                "passive_length_m": 5.0,
                "pump_power_w": 0.4,
                "round_trips": 150,
            },
        )
    if goal.startswith("Broader optical spectrum"):
        return Suggestion(
            summary="Use a longer passive fiber so the pulse accumulates more "
                    "self-phase modulation.",
            reasoning=(
                "Spectral broadening in the passive fiber is driven by "
                "self-phase modulation, which grows with both peak power and "
                "propagation length. A longer PM1550 span broadens the "
                "spectrum (at the cost of a longer cavity and more "
                "multi-pulsing tendency)."),
            changes={
                "active_length_m": 0.25,
                "passive_length_m": 10.0,
                "pump_power_w": 0.10,
                "round_trips": 200,
            },
        )
    # Cleaner / suppress noise
    return Suggestion(
        summary="Make the saturable absorber more discriminating and tighten "
                "the bandpass to suppress the noise background.",
        reasoning=(
            "A higher modulation depth and a lower saturation power give the "
            "fast saturable absorber more loss contrast, so low-level noise is "
            "attenuated while real pulses bleach it. A tighter bandpass adds "
            "spectral filtering that the broadband noise cannot overcome."),
        changes={
            "sa_mod_depth": 0.6,
            "sa_sat_power_w": 50.0,
            "bandpass_transmission": 0.7,
        },
    )


def _passive_suggestion(goal: str) -> Suggestion:
    if goal.startswith("Maximize spectral broadening"):
        return Suggestion(
            summary="Raise the peak power and use a longer, highly nonlinear "
                    "fiber to maximize self-phase modulation.",
            reasoning=(
                "Spectral broadening from SPM scales with the nonlinear phase "
                "= peak power x length x fiber nonlinearity. A high-amplitude "
                "pulse in a long, high-nonlinearity fiber (e.g. the NKT "
                "small-core fiber) gives the broadest spectrum."),
            changes={
                "amplitude_w": 1000.0,
                "fibre_length_m": 3.0,
                "fibre_name": "NKT SC-5.0-1040-PM",
            },
        )
    if goal.startswith("Preserve input shape"):
        return Suggestion(
            summary="Lower the peak power and shorten the fiber so propagation "
                    "stays nearly linear.",
            reasoning=(
                "Keeping the nonlinear phase small (low peak power, short "
                "length, standard SMF) means dispersion and nonlinearity barely "
                "reshape the pulse, so the output looks like the input."),
            changes={
                "amplitude_w": 10.0,
                "fibre_length_m": 0.5,
                "fibre_name": "SMF-28 (Corning)",
            },
        )
    # Stronger nonlinear / soliton dynamics
    return Suggestion(
        summary="Use a high peak power in an anomalous-dispersion fiber to "
                "drive soliton / strong nonlinear dynamics.",
        reasoning=(
            "Solitons and rich nonlinear dynamics (e.g. soliton fission) need "
            "a balance of strong nonlinearity and anomalous dispersion. A high "
            "peak power in the NKT NEG (anomalous) fiber over a moderate length "
            "produces pronounced soliton dynamics."),
        changes={
            "amplitude_w": 500.0,
            "fibre_length_m": 2.0,
            "fibre_name": "NKT NL-1050-NEG-1",
        },
    )


def suggest(mode: str, goal: str) -> Suggestion:
    """Return the recommended parameter changes for a mode + goal."""
    if mode == "ring":
        return _ring_suggestion(goal)
    return _passive_suggestion(goal)


def format_change(key: str, target, current=None) -> str:
    """Format a single change line as 'Label: current -> target unit'."""
    label, unit = PARAM_LABELS.get(key, (key, ""))
    unit_s = f" {unit}" if unit else ""

    def fmt(v):
        if isinstance(v, float):
            if v < 0.1:
                return f"{v:.3f}"
            if v < 10:
                return f"{v:g}"
            return f"{v:g}"
        return str(v)

    if current is None:
        return f"{label}: {fmt(target)}{unit_s}"
    same = str(fmt(current)) == str(fmt(target))
    arrow = "=" if same else "->"
    return f"{label}: {fmt(current)}{unit_s} {arrow} {fmt(target)}{unit_s}"
