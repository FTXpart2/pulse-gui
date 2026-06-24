# pulse-gui

A graphical pulse generator and fiber-propagation visualizer built on top of
[pyLaserPulse](https://github.com/jsfeehan/pyLaserPulse). It provides an
interactive PyQt5 interface for generating laser pulses, propagating them
through optical fibers, and simulating a mode-locked Er-doped fiber **ring
laser** that builds a pulse up from noise.

> **Standalone:** this repository bundles a copy of the pyLaserPulse package
> (see the `pyLaserPulse/` directory), so you do **not** need to install it
> separately. Just install the Python requirements below and run.

## Features

### Two simulation modes

**1. Passive fiber (single pass)**
- Pulse shapes: Gaussian, Soliton (sech²), Square
- Adjustable pulse width (fs) and amplitude (W)
- Selectable catalogue fibers (SMF-28, HI1060, NKT SC-5.0-1040-PM, NKT NL-1050-NEG-1)
- Watch a single pulse propagate and spectrally broaden

**2. Mode-locked Er-doped fiber ring laser**
- Cavity: WDM/isolator/tap → Er active fiber → saturable absorber → bandpass filter → PM1550 passive fiber → loop
- Er gain fibers: nLight Er80-4/125-HD-PM, OFS EDF07 PM, OFS EDF08 PM
- Custom fast **saturable absorber** for pulse formation
- Start from noise and watch the pulse build up over cavity round trips
- Tunable pump power, output tap, bandpass transmission, SA depth/saturation, fiber lengths, round trips

### Visualization
- **Time domain** and **frequency domain** shown together
- A **combined** time + spectrum plot (power vs time, spectrum vs wavelength)
- **3D evolution** surface (time × fiber position / round trip × power)
- A single slider steps through fiber position (passive) or round trips (ring laser)
- Play/Pause animation

## Installation

This project is self-contained. Clone it and install the Python requirements:

```bash
git clone https://github.com/FTXpart2/pulse-gui.git
cd pulse-gui
python -m venv .venv
# Windows:  .\.venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
```

> Tested with Python 3.13. A bundled copy of pyLaserPulse lives in the
> `pyLaserPulse/` directory and is imported automatically when you run from the
> repository root — no separate pyLaserPulse install is required.

## Running

```bash
python run_pulse_gui.py
```

or

```bash
python -m pulse_gui
```

## Quick start values

**Passive — supercontinuum:**
| Field | Value |
|-------|-------|
| Mode | Passive fiber (single pass) |
| Pulse shape | Soliton |
| Width | 100 fs |
| Amplitude | 10000 W |
| Central λ | 1040 nm |
| Fiber | NKT SC-5.0-1040-PM |
| Length | 1.0 m |

**Mode-locked ring laser:**
| Field | Value |
|-------|-------|
| Er fiber | nLight Er80-4/125-HD-PM |
| Active length | 0.5 m |
| Passive length | 10.0 m |
| Pump power | 0.6 W |
| Output tap | 10 % |
| Bandpass T | 0.85 |
| SA mod. depth | 0.3 |
| SA sat. power | 300 W |
| Round trips | 30–60 |

Tip: first run the ring laser with **Start from noise unchecked** to confirm the
cavity lases, then enable it to watch buildup from noise.

## Project layout

```
pulse_gui/                      # the GUI application
├── __main__.py                 # python -m pulse_gui entry point
├── pulse_shapes.py             # Gaussian / Soliton / Square generation
├── simulation.py               # Passive single-pass fiber propagation
├── mode_locked_simulation.py   # Er-doped ring laser backend
├── saturable_absorber.py       # Custom fast saturable absorber component
└── main_window.py              # PyQt5 GUI
pyLaserPulse/                   # bundled physics engine (see attribution)
run_pulse_gui.py                # Launcher
requirements.txt
LICENSE
```

## Notes

Reaching a clean, stable mode-locked pulse from noise is parameter-sensitive
and may require tuning (pump power, saturable-absorber settings, filter
transmission) and many round trips. All parameters are exposed in the UI.

## Attribution & License

The `pyLaserPulse/` directory is a bundled copy of
[pyLaserPulse](https://github.com/jsfeehan/pyLaserPulse) by James S. Feehan,
distributed under the **GPLv3** license (see `LICENSE`). All credit for the
underlying physics — the GNLSE solver, fiber models, Giles gain model, and
component catalogue — belongs to that project.

Because this repository includes GPLv3-licensed code, it is also distributed
under the GPLv3.
