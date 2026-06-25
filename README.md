# pulse-gui

An interactive desktop application for **generating laser pulses**, **propagating
them through optical fiber**, and **simulating a mode-locked Er-doped fiber ring
laser** that builds a pulse up from noise. It pairs a GNLSE physics engine with a
PyQt5 interface, live visualization, a parameter advisor, and a closed-loop
auto-tuner.

> **Standalone:** everything needed to run is bundled in this repository. Install
> the Python requirements and go — no extra packages or external setup required.

---

## What this project does

### Two simulation modes

**1. Passive fiber (single pass)**
- Pulse shapes: **Gaussian**, **Soliton** (sech²), **Square**
- Adjustable pulse **width** (fs), **amplitude** (W), and **center wavelength** (nm)
- Selectable fibers: SMF-28, HI1060, NKT SC-5.0-1040-PM, NKT NL-1050-NEG-1
- Watch a pulse propagate and spectrally broaden via self-phase modulation,
  dispersion, and soliton dynamics

**2. Mode-locked Er-doped fiber ring laser**
- Ring cavity: WDM / isolator / output tap → Er active fiber → fast saturable
  absorber → bandpass filter → passive fiber → loop back
- Seeded from quantum noise; watch the field evolve over cavity round trips
- A custom **fast saturable absorber** provides the pulse-shaping nonlinearity
- Repetition rate is computed physically from the cavity length

### Visualization
- **Time domain** and **frequency domain** shown side by side
- A **combined** time + spectrum plot
- A **3D evolution** surface (time × round-trip/position × power)
- A slider + Play/Pause animation to step through fiber position (passive) or
  cavity round trips (ring laser)

### Suggestions Advisor (side panel)
A docked panel that recommends parameter changes for a chosen goal and applies
them with one click. Goals include:
- **Ring laser:** single pulse (win the race), harmonic mode-locking, higher
  pulse energy, broader spectrum, suppress noise background
- **Passive:** maximize spectral broadening, preserve input shape, stronger
  nonlinear/soliton dynamics

Each suggestion shows the recommended values (as `current → target`) and a short
physics explanation of *why*.

### Auto-tune (closed-loop optimizer)
For the ring laser, set a **target number of pulses** and the app runs
simulations in the background, bisecting the pump power until it hits the target
(or gets as close as possible) — a software analogue of automated
mode-locking optimization. Progress is logged live and the search is cancelable.

### Calibration (Tools → Cavity / Model Calibration)
Enter measured values to match a real setup: fiber **group index** (sets the
repetition rate), **center wavelength**, grid **max wavelength**, **pump
wavelength**, **gain/ASE band**, and **grid resolution**. These feed directly
into the simulation on the next run.

---

## The single-pulse story

A central result of this project: getting a **single pulse to "win the race"**
out of noise.

Early on, the ring laser settled into a chaotic, noise-like state of 10–17
fluctuating spikes regardless of pump, fiber length, round trips, or saturable-
absorber settings — it was lasing as an incoherent (ASE-dominated) source rather
than mode-locking. Systematic experiments (see `experiments/`) showed that the
key lever is **gain**: shortening the active fiber and pumping near threshold
lowers the intracavity energy until it can only support coherent, evenly-spaced
mode-locked pulses, and then a clean **winner-take-all race** emerges.

Reducing the pump steadily reduced the surviving pulse count until exactly one
remained:

| Pump (W) | Surviving pulses |
|----------|------------------|
| 0.095 | 6 |
| 0.065 | 4 |
| 0.050 | 2 |
| **0.040** | **1** (reproducible) |

At **~40 mW** (EDF 0.25 m, passive 5 m, ~250 round trips), ~13 pulses nucleate
from noise and progressively die off over ~130 round trips until a single clean
pulse survives. These are now the **default ring-laser settings**, so the GUI
demonstrates single-pulse operation out of the box.

> Note: this is **near-threshold operation and is mildly stochastic** — just like
> a real laser near threshold, it occasionally lands on 2 pulses. Nudge the pump
> down slightly if so.

---

## Deployment & running

The project is self-contained: everything needed to run is in this repository.
It is a desktop GUI application, so it must run on a machine with a graphical
display (it cannot be used over a plain headless SSH session without an X
server / remote desktop).

### Prerequisites
- **Python 3.10+** (tested on 3.13), 64-bit, with `pip`
- A desktop environment (Windows, macOS, or a Linux desktop)
- ~500 MB free disk for the virtual environment

Check your Python:

```bash
python --version      # Windows
python3 --version     # macOS / Linux
```

If Python is missing, install it from [python.org](https://www.python.org/downloads/)
(on Windows, tick **"Add python.exe to PATH"** during setup).

### Option A — Windows one-click

1. Download/clone this repository.
2. Double-click **`launch_gui.bat`**.

On first run it creates a virtual environment and installs the requirements
automatically, then launches the GUI. Subsequent launches start instantly.

### Option B — Manual setup (Windows / macOS / Linux)

```bash
# 1. Get the code
git clone https://github.com/FTXpart2/pulse-gui.git
cd pulse-gui

# 2. Create and activate a virtual environment
python -m venv .venv
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# Windows (cmd):
.\.venv\Scripts\activate.bat
# macOS / Linux:
source .venv/bin/activate

# 3. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 4. Run
python run_pulse_gui.py
```

You can also start it as a module:

```bash
python -m pulse_gui
```

On Linux you may additionally need the system Qt/X libraries, e.g. on
Debian/Ubuntu:

```bash
sudo apt-get install libxcb-xinerama0 libgl1
```

### Option C — Build a standalone executable (deploy to machines without Python)

To hand the app to a lab computer that has no Python installed, bundle it into a
single executable with [PyInstaller](https://pyinstaller.org/):

```bash
# inside the activated virtual environment
pip install pyinstaller
pyinstaller --noconfirm --windowed --name pulse-gui ^
  --add-data "pyLaserPulse;pyLaserPulse" ^
  run_pulse_gui.py
```

(Use `:` instead of `;` in the `--add-data` separator on macOS/Linux.) The
build appears in `dist/pulse-gui/`; copy that whole folder to the target
machine and run the `pulse-gui` executable inside it. No Python required there.

> The `--add-data` flag bundles the simulation engine's data files (fiber and
> component data) so they ship with the executable.

### Running the parameter experiments (optional)

The studies behind the single-pulse result can be reproduced from the activated
environment:

```bash
python experiments/single_pulse_sweep.py
python experiments/low_gain_short_edf.py --pumps 0.04,0.05,0.065
python experiments/win_the_race.py
```

Each writes a `.png` figure into `experiments/`.

### Troubleshooting

- **No window appears / "offscreen" platform:** make sure the environment
  variable `QT_QPA_PLATFORM` is **not** set to `offscreen`. Unset it
  (`set QT_QPA_PLATFORM=` on Windows, `unset QT_QPA_PLATFORM` on macOS/Linux).
- **`ModuleNotFoundError`:** confirm the virtual environment is activated and
  `pip install -r requirements.txt` completed successfully.
- **Window opens behind others:** it may launch behind the active window — check
  the taskbar/dock.
- **A ring-laser run seems stuck:** a full 250-round-trip run takes a couple of
  minutes; progress is shown in the status bar.

---

## Quick-start values

**Single-pulse mode-locked ring laser (default):**
| Field | Value |
|-------|-------|
| Mode | Mode-locked ring laser |
| Er fiber | nLight Er80-4/125-HD-PM |
| Active (EDF) length | 0.25 m |
| Passive length | 5.0 m |
| Pump power | 0.040 W |
| Round trips | 250 |
| Start from noise | checked |

Then watch the **Evolution (3D)** tab and use the round-trip slider to see the
pulses die off until one wins.

**Passive — strong spectral broadening:**
| Field | Value |
|-------|-------|
| Mode | Passive fiber (single pass) |
| Pulse shape | Soliton |
| Width | 100 fs |
| Amplitude | 1000 W |
| Center λ | 1040 nm |
| Fiber | NKT SC-5.0-1040-PM |
| Length | 1–3 m |

Tip: in either mode, use the **Suggestions Advisor** panel to set good values for
a chosen goal automatically.

---

## Project layout

```
pulse_gui/                      # the GUI application
├── __main__.py                 # `python -m pulse_gui` entry point
├── main_window.py              # PyQt5 GUI, advisor, auto-tune, calibration
├── pulse_shapes.py             # Gaussian / Soliton / Square generation
├── simulation.py               # passive single-pass fiber propagation
├── mode_locked_simulation.py   # Er-doped ring laser backend + rep-rate model
├── saturable_absorber.py       # custom fast saturable absorber
├── advisor.py                  # rule-based parameter suggestions
└── autotune.py                 # closed-loop pump-power search
experiments/                    # reproducible parameter-study scripts + figures
run_pulse_gui.py                # launcher
launch_gui.bat                  # Windows double-click launcher
requirements.txt
LICENSE
```

The `experiments/` folder contains the scripts used to investigate single-pulse
operation (length/pump sweeps, round-trip convergence, saturable-absorber
sweeps, the pulse "race", and the near-threshold search), each of which saves a
figure.

---

## Notes & limitations

- This is a **simulator and design/teaching tool**, not instrument-control
  software — it does not connect to or measure real hardware.
- The model is **not calibrated to a specific physical device**; use the
  Calibration dialog to bring it closer to a real setup.
- Reaching a clean mode-locked pulse from noise is parameter-sensitive; the
  defaults are tuned for single-pulse operation but operate near threshold.
- A full ring-laser run (250 round trips) takes a couple of minutes.

## License

This project includes a bundled, third-party GNLSE simulation engine distributed
under the **GPLv3** license (see the `LICENSE` file). Because it incorporates
GPLv3-licensed code, this repository is also distributed under the **GPLv3**.
