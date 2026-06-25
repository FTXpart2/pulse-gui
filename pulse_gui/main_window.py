"""Main PyQt5 window for the pulse generator GUI.

Two modes are supported:
  * Passive single-pass propagation through a fibre (pulse_gui.simulation)
  * Mode-locked Er-doped fibre ring laser (pulse_gui.mode_locked_simulation)

The plot area always shows the time domain and frequency domain together,
plus a combined time + spectrum view, with a single slider stepping through
either fibre position (passive) or cavity round trips (ring laser).
"""

import traceback

import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5 import QtCore, QtWidgets

from pulse_gui.pulse_shapes import (
    PULSE_SHAPES, PulseParams, build_grid, preview_intensity)
from pulse_gui.simulation import (
    FIBRE_OPTIONS, SimulationConfig, SimulationResult, run_simulation)
from pulse_gui.mode_locked_simulation import (
    ER_FIBRES, RingLaserConfig, RingLaserResult, run_ring_laser,
    cavity_rep_rate)
from pulse_gui import advisor


TIME_AXIS_LIMITS = (-25.0, 25.0)


class Evolution:
    """Unified view of either simulation result for the plotting code."""

    def __init__(self, time_ps, wavelength_nm, steps, step_unit,
                 time_evolution, spectral_evolution, input_intensity=None):
        self.time_ps = time_ps
        self.wavelength_nm = wavelength_nm
        self.steps = np.asarray(steps)
        self.step_unit = step_unit
        self.time_evolution = np.asarray(time_evolution)
        self.spectral_evolution = np.asarray(spectral_evolution)
        self.input_intensity = input_intensity

    @property
    def n_steps(self):
        return len(self.steps)

    def label(self, index):
        if self.step_unit == "round trip":
            return f"round trip {int(self.steps[index])}"
        return f"z = {self.steps[index]:.3f} m"


def _passive_to_evolution(result: SimulationResult) -> Evolution:
    return Evolution(
        result.time_ps, result.wavelength_nm, result.z_m, "m",
        result.time_evolution, result.spectral_evolution,
        input_intensity=result.input_intensity)


def _ring_to_evolution(result: RingLaserResult) -> Evolution:
    return Evolution(
        result.time_ps, result.wavelength_nm, result.round_trip, "round trip",
        result.time_evolution, result.spectral_evolution)


class SimulationWorker(QtCore.QThread):
    finished = QtCore.pyqtSignal(object)
    error = QtCore.pyqtSignal(str)

    def __init__(self, mode, config):
        super().__init__()
        self.mode = mode
        self.config = config

    def run(self):
        try:
            if self.mode == "passive":
                result = _passive_to_evolution(run_simulation(self.config))
            else:
                result = _ring_to_evolution(run_ring_laser(self.config))
            self.finished.emit(result)
        except Exception:
            self.error.emit(traceback.format_exc())


class AutotuneWorker(QtCore.QThread):
    progress = QtCore.pyqtSignal(str)
    finished = QtCore.pyqtSignal(object)
    error = QtCore.pyqtSignal(str)

    def __init__(self, base_config, target_pulses):
        super().__init__()
        self.base_config = base_config
        self.target_pulses = target_pulses
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            from pulse_gui.autotune import autotune_pump
            result = autotune_pump(
                self.base_config, self.target_pulses,
                progress_cb=self.progress.emit,
                cancel_cb=lambda: self._cancel)
            self.finished.emit(result)
        except Exception:
            self.error.emit(traceback.format_exc())


class PlotCanvas(FigureCanvas):
    def __init__(self, width=7, height=6):
        self.figure = Figure(figsize=(width, height), tight_layout=True)
        super().__init__(self.figure)


class CalibrationDialog(QtWidgets.QDialog):
    """Enter measured cavity / model values to match a real setup."""

    def __init__(self, calib: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cavity / Model Calibration")
        self.setMinimumWidth(380)
        form = QtWidgets.QFormLayout(self)

        intro = QtWidgets.QLabel(
            "Set physical/numerical values to match your real device. "
            "These feed the simulation grid, gain band, and repetition rate.")
        intro.setWordWrap(True)
        form.addRow(intro)

        self.ng_spin = QtWidgets.QDoubleSpinBox()
        self.ng_spin.setRange(1.0, 2.0)
        self.ng_spin.setDecimals(4)
        self.ng_spin.setSingleStep(0.001)
        self.ng_spin.setValue(calib["group_index"])
        form.addRow("Fiber group index n_g:", self.ng_spin)

        self.cwl_spin = QtWidgets.QDoubleSpinBox()
        self.cwl_spin.setRange(900.0, 2000.0)
        self.cwl_spin.setSuffix(" nm")
        self.cwl_spin.setValue(calib["central_wl_nm"])
        form.addRow("Center wavelength:", self.cwl_spin)

        self.maxwl_spin = QtWidgets.QDoubleSpinBox()
        self.maxwl_spin.setRange(1600.0, 4000.0)
        self.maxwl_spin.setSuffix(" nm")
        self.maxwl_spin.setValue(calib["max_wl_nm"])
        form.addRow("Grid max wavelength:", self.maxwl_spin)

        self.pumpwl_spin = QtWidgets.QDoubleSpinBox()
        self.pumpwl_spin.setRange(800.0, 1500.0)
        self.pumpwl_spin.setSuffix(" nm")
        self.pumpwl_spin.setValue(calib["pump_wavelength_nm"])
        form.addRow("Pump wavelength:", self.pumpwl_spin)

        self.asemin_spin = QtWidgets.QDoubleSpinBox()
        self.asemin_spin.setRange(900.0, 1600.0)
        self.asemin_spin.setSuffix(" nm")
        self.asemin_spin.setValue(calib["ase_min_nm"])
        form.addRow("Gain/ASE band min:", self.asemin_spin)

        self.asemax_spin = QtWidgets.QDoubleSpinBox()
        self.asemax_spin.setRange(1000.0, 1700.0)
        self.asemax_spin.setSuffix(" nm")
        self.asemax_spin.setValue(calib["ase_max_nm"])
        form.addRow("Gain/ASE band max:", self.asemax_spin)

        self.grid_combo = QtWidgets.QComboBox()
        self._grid_options = [2 ** n for n in (10, 11, 12, 13)]
        self.grid_combo.addItems([str(g) for g in self._grid_options])
        self.grid_combo.setCurrentText(str(calib["grid_points"]))
        form.addRow("Grid points:", self.grid_combo)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self) -> dict:
        return {
            "group_index": self.ng_spin.value(),
            "central_wl_nm": self.cwl_spin.value(),
            "max_wl_nm": self.maxwl_spin.value(),
            "pump_wavelength_nm": self.pumpwl_spin.value(),
            "ase_min_nm": self.asemin_spin.value(),
            "ase_max_nm": self.asemax_spin.value(),
            "grid_points": int(self.grid_combo.currentText()),
        }


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(
            "pyLaserPulse — Pulse Generator, Fiber Propagation & Ring Laser")
        self.resize(1500, 950)

        self._evolution: Evolution | None = None
        self._worker: SimulationWorker | None = None
        _defaults = RingLaserConfig()
        self._calib = {
            "group_index": _defaults.group_index,
            "central_wl_nm": _defaults.central_wl_nm,
            "max_wl_nm": _defaults.max_wl_nm,
            "pump_wavelength_nm": _defaults.pump_wavelength_nm,
            "ase_min_nm": _defaults.ase_min_nm,
            "ase_max_nm": _defaults.ase_max_nm,
            "grid_points": _defaults.grid_points,
        }
        self._anim_timer = QtCore.QTimer(self)
        self._anim_timer.timeout.connect(self._advance_animation)
        self._anim_index = 0
        self._anim_playing = False

        self._build_ui()
        self._connect_signals()
        self._on_mode_changed()
        self.update_input_preview()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        menu = self.menuBar().addMenu("&Tools")
        calib_action = menu.addAction("Cavity / Model Calibration…")
        calib_action.triggered.connect(self._open_calibration)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QHBoxLayout(central)

        control_widget = QtWidgets.QWidget()
        control_widget.setFixedWidth(340)
        control_layout = QtWidgets.QVBoxLayout(control_widget)

        # Mode selector
        mode_box = QtWidgets.QGroupBox("Simulation Mode")
        mode_layout = QtWidgets.QVBoxLayout(mode_box)
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems(
            ["Passive fiber (single pass)", "Mode-locked ring laser"])
        mode_layout.addWidget(self.mode_combo)
        control_layout.addWidget(mode_box)

        control_layout.addWidget(self._build_passive_controls())
        control_layout.addWidget(self._build_ring_controls())

        # Run / animation buttons
        self.preview_btn = QtWidgets.QPushButton("Preview Input")
        self.run_btn = QtWidgets.QPushButton("Run Simulation")
        self.run_btn.setStyleSheet("font-weight: bold;")
        control_layout.addWidget(self.preview_btn)
        control_layout.addWidget(self.run_btn)

        anim_box = QtWidgets.QGroupBox("Step / Round-trip Animation")
        anim_layout = QtWidgets.QVBoxLayout(anim_box)
        self.step_label = QtWidgets.QLabel("Step: input")
        self.step_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.step_slider.setEnabled(False)
        play_row = QtWidgets.QHBoxLayout()
        self.play_btn = QtWidgets.QPushButton("Play")
        self.play_btn.setEnabled(False)
        self.stop_btn = QtWidgets.QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        play_row.addWidget(self.play_btn)
        play_row.addWidget(self.stop_btn)
        anim_layout.addWidget(self.step_label)
        anim_layout.addWidget(self.step_slider)
        anim_layout.addLayout(play_row)
        control_layout.addWidget(anim_box)

        self.status_label = QtWidgets.QLabel("Ready.")
        self.status_label.setWordWrap(True)
        control_layout.addWidget(self.status_label)
        control_layout.addStretch()

        layout.addWidget(control_widget)

        # Plot tabs
        self.tabs = QtWidgets.QTabWidget()
        self.live_canvas = PlotCanvas()
        gs = self.live_canvas.figure.add_gridspec(2, 2)
        self.time_ax = self.live_canvas.figure.add_subplot(gs[0, 0])
        self.spec_ax = self.live_canvas.figure.add_subplot(gs[0, 1])
        self.combined_ax = self.live_canvas.figure.add_subplot(gs[1, :])
        self.combined_twin = self.combined_ax.twiny()
        self.tabs.addTab(self.live_canvas, "Time + Spectrum")

        self.evo_canvas = PlotCanvas(width=7, height=6)
        self.evo_ax = self.evo_canvas.figure.add_subplot(111, projection="3d")
        self._evo_cbar = None
        self.tabs.addTab(self.evo_canvas, "Evolution (3D)")

        layout.addWidget(self.tabs, stretch=1)

        self._build_advisor_panel()

        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        self.statusBar().addPermanentWidget(self.progress)

    def _build_advisor_panel(self):
        dock = QtWidgets.QDockWidget("Suggestions Advisor", self)
        dock.setFeatures(
            QtWidgets.QDockWidget.DockWidgetMovable
            | QtWidgets.QDockWidget.DockWidgetFloatable)
        panel = QtWidgets.QWidget()
        panel.setMinimumWidth(300)
        v = QtWidgets.QVBoxLayout(panel)

        intro = QtWidgets.QLabel(
            "Pick what you want and get parameter suggestions for the "
            "current mode.")
        intro.setWordWrap(True)
        v.addWidget(intro)

        v.addWidget(QtWidgets.QLabel("Goal:"))
        self.goal_combo = QtWidgets.QComboBox()
        v.addWidget(self.goal_combo)

        self.advisor_text = QtWidgets.QTextEdit()
        self.advisor_text.setReadOnly(True)
        v.addWidget(self.advisor_text, stretch=1)

        self.apply_suggestion_btn = QtWidgets.QPushButton(
            "Apply suggested values")
        v.addWidget(self.apply_suggestion_btn)

        # Auto-tune (closed-loop search) - ring laser only.
        self.autotune_box = QtWidgets.QGroupBox("Auto-tune (ring laser)")
        at = QtWidgets.QFormLayout(self.autotune_box)
        self.autotune_target_spin = QtWidgets.QSpinBox()
        self.autotune_target_spin.setRange(1, 10)
        self.autotune_target_spin.setValue(1)
        at.addRow("Target # pulses:", self.autotune_target_spin)
        self.autotune_btn = QtWidgets.QPushButton("Auto-tune pump power")
        at.addRow(self.autotune_btn)
        self.autotune_log = QtWidgets.QTextEdit()
        self.autotune_log.setReadOnly(True)
        self.autotune_log.setMaximumHeight(150)
        at.addRow(self.autotune_log)
        v.addWidget(self.autotune_box)

        dock.setWidget(panel)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
        self._current_changes = {}
        self._autotune_worker = None

    def _build_passive_controls(self):
        self.passive_box = QtWidgets.QGroupBox("Passive Fiber Parameters")
        form = QtWidgets.QFormLayout(self.passive_box)

        self.shape_combo = QtWidgets.QComboBox()
        self.shape_combo.addItems(PULSE_SHAPES)

        self.width_spin = QtWidgets.QDoubleSpinBox()
        self.width_spin.setRange(10.0, 5000.0)
        self.width_spin.setValue(150.0)
        self.width_spin.setSuffix(" fs")

        self.amplitude_spin = QtWidgets.QDoubleSpinBox()
        self.amplitude_spin.setRange(0.1, 1e6)
        self.amplitude_spin.setValue(150.0)
        self.amplitude_spin.setSuffix(" W")

        self.wavelength_spin = QtWidgets.QDoubleSpinBox()
        self.wavelength_spin.setRange(800.0, 2000.0)
        self.wavelength_spin.setValue(1030.0)
        self.wavelength_spin.setSuffix(" nm")

        self.fibre_combo = QtWidgets.QComboBox()
        self.fibre_combo.addItems(list(FIBRE_OPTIONS.keys()))

        self.length_spin = QtWidgets.QDoubleSpinBox()
        self.length_spin.setRange(0.01, 50.0)
        self.length_spin.setValue(1.0)
        self.length_spin.setSuffix(" m")

        self.samples_spin = QtWidgets.QSpinBox()
        self.samples_spin.setRange(10, 300)
        self.samples_spin.setValue(60)

        form.addRow("Pulse shape:", self.shape_combo)
        form.addRow("Pulse width:", self.width_spin)
        form.addRow("Amplitude:", self.amplitude_spin)
        form.addRow("Central λ:", self.wavelength_spin)
        form.addRow("Fiber type:", self.fibre_combo)
        form.addRow("Fiber length:", self.length_spin)
        form.addRow("Z samples:", self.samples_spin)
        return self.passive_box

    def _build_ring_controls(self):
        self.ring_box = QtWidgets.QGroupBox("Mode-locked Ring Laser")
        form = QtWidgets.QFormLayout(self.ring_box)

        self.er_combo = QtWidgets.QComboBox()
        self.er_combo.addItems(list(ER_FIBRES.keys()))

        self.active_len_spin = QtWidgets.QDoubleSpinBox()
        self.active_len_spin.setRange(0.05, 5.0)
        self.active_len_spin.setValue(0.25)
        self.active_len_spin.setSuffix(" m")
        self.active_len_spin.setDecimals(2)
        self.active_len_spin.setSingleStep(0.05)

        self.passive_len_spin = QtWidgets.QDoubleSpinBox()
        self.passive_len_spin.setRange(0.1, 50.0)
        self.passive_len_spin.setValue(5.0)
        self.passive_len_spin.setSuffix(" m")

        self.pump_spin = QtWidgets.QDoubleSpinBox()
        self.pump_spin.setRange(0.0, 5.0)
        self.pump_spin.setDecimals(3)
        self.pump_spin.setSingleStep(0.005)
        self.pump_spin.setValue(0.040)
        self.pump_spin.setSuffix(" W")

        self.tap_spin = QtWidgets.QDoubleSpinBox()
        self.tap_spin.setRange(1.0, 90.0)
        self.tap_spin.setValue(10.0)
        self.tap_spin.setSuffix(" %")

        self.bandpass_spin = QtWidgets.QDoubleSpinBox()
        self.bandpass_spin.setRange(0.05, 1.0)
        self.bandpass_spin.setValue(0.85)
        self.bandpass_spin.setSingleStep(0.05)

        self.sa_depth_spin = QtWidgets.QDoubleSpinBox()
        self.sa_depth_spin.setRange(0.0, 1.0)
        self.sa_depth_spin.setValue(0.3)
        self.sa_depth_spin.setSingleStep(0.05)

        self.sa_satp_spin = QtWidgets.QDoubleSpinBox()
        self.sa_satp_spin.setRange(1.0, 5000.0)
        self.sa_satp_spin.setValue(300.0)
        self.sa_satp_spin.setSuffix(" W")

        self.round_trips_spin = QtWidgets.QSpinBox()
        self.round_trips_spin.setRange(2, 1000)
        self.round_trips_spin.setValue(250)

        self.noise_check = QtWidgets.QCheckBox("Start from noise")
        self.noise_check.setChecked(True)

        self.rep_rate_label = QtWidgets.QLabel("—")
        self.rep_rate_label.setStyleSheet("color: #2a7;")

        form.addRow("Er fiber:", self.er_combo)
        form.addRow("Active length:", self.active_len_spin)
        form.addRow("Passive length:", self.passive_len_spin)
        form.addRow("Est. rep. rate:", self.rep_rate_label)
        form.addRow("Pump power:", self.pump_spin)
        form.addRow("Output tap:", self.tap_spin)
        form.addRow("Bandpass T:", self.bandpass_spin)
        form.addRow("SA mod. depth:", self.sa_depth_spin)
        form.addRow("SA sat. power:", self.sa_satp_spin)
        form.addRow("Round trips:", self.round_trips_spin)
        form.addRow("", self.noise_check)
        return self.ring_box

    def _connect_signals(self):
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self.goal_combo.currentIndexChanged.connect(self._refresh_suggestions)
        self.apply_suggestion_btn.clicked.connect(self._apply_suggestion)
        self.active_len_spin.valueChanged.connect(self._update_rep_rate_label)
        self.passive_len_spin.valueChanged.connect(self._update_rep_rate_label)
        self.autotune_btn.clicked.connect(self._start_autotune)
        self.preview_btn.clicked.connect(self.update_input_preview)
        self._update_rep_rate_label()
        self.run_btn.clicked.connect(self.start_simulation)
        self.play_btn.clicked.connect(self.toggle_animation)
        self.stop_btn.clicked.connect(self.stop_animation)
        self.step_slider.valueChanged.connect(self.show_step)
        for widget in (self.shape_combo, self.width_spin, self.amplitude_spin,
                       self.wavelength_spin):
            if isinstance(widget, QtWidgets.QComboBox):
                widget.currentIndexChanged.connect(self.update_input_preview)
            else:
                widget.valueChanged.connect(self.update_input_preview)

    # -------------------------------------------------------------- helpers
    def _mode(self):
        return "passive" if self.mode_combo.currentIndex() == 0 else "ring"

    def _on_mode_changed(self):
        is_passive = self._mode() == "passive"
        self.passive_box.setVisible(is_passive)
        self.ring_box.setVisible(not is_passive)
        self.preview_btn.setEnabled(is_passive)
        self.autotune_box.setVisible(not is_passive)
        self._populate_goals()
        if is_passive:
            self.update_input_preview()
        else:
            self.status_label.setText(
                "Ring laser mode: set parameters and Run. Reaching a stable "
                "mode-locked pulse can require tuning and many round trips.")

    def _open_calibration(self):
        dialog = CalibrationDialog(self._calib, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            self._calib = dialog.values()
            self._update_rep_rate_label()
            self.status_label.setText(
                "Calibration updated. New values apply on the next Run.")

    def _update_rep_rate_label(self):
        cfg = RingLaserConfig(
            active_length_m=self.active_len_spin.value(),
            passive_length_m=self.passive_len_spin.value(),
            group_index=self._calib["group_index"])
        f = cavity_rep_rate(cfg)
        self.rep_rate_label.setText(
            f"{f / 1e6:.1f} MHz  (cavity {cfg.active_length_m + cfg.passive_length_m:.2f} m)")

    # -------------------------------------------------------------- advisor
    def _populate_goals(self):
        goals = advisor.GOALS[self._mode()]
        self.goal_combo.blockSignals(True)
        self.goal_combo.clear()
        self.goal_combo.addItems(goals)
        self.goal_combo.blockSignals(False)
        self._refresh_suggestions()

    def _widget_for_key(self):
        return {
            "active_length_m": self.active_len_spin,
            "passive_length_m": self.passive_len_spin,
            "pump_power_w": self.pump_spin,
            "round_trips": self.round_trips_spin,
            "sa_mod_depth": self.sa_depth_spin,
            "sa_sat_power_w": self.sa_satp_spin,
            "bandpass_transmission": self.bandpass_spin,
            "output_tap_percent": self.tap_spin,
            "width_fs": self.width_spin,
            "amplitude_w": self.amplitude_spin,
            "fibre_length_m": self.length_spin,
            "fibre_name": self.fibre_combo,
            "shape": self.shape_combo,
        }

    def _current_value(self, key):
        widget = self._widget_for_key().get(key)
        if widget is None:
            return None
        if isinstance(widget, QtWidgets.QComboBox):
            return widget.currentText()
        return widget.value()

    def _refresh_suggestions(self):
        goal = self.goal_combo.currentText()
        if not goal:
            return
        sugg = advisor.suggest(self._mode(), goal)
        self._current_changes = dict(sugg.changes)

        lines = [
            f"<b>Goal:</b> {goal}",
            f"<p>{sugg.summary}</p>",
            "<b>Suggested changes</b><ul>",
        ]
        for key, target in sugg.changes.items():
            current = self._current_value(key)
            lines.append("<li>" + advisor.format_change(key, target, current)
                         + "</li>")
        lines.append("</ul>")
        lines.append(f"<b>Why:</b><br>{sugg.reasoning}")
        self.advisor_text.setHtml("\n".join(lines))

    def _apply_suggestion(self):
        mapping = self._widget_for_key()
        for key, target in self._current_changes.items():
            widget = mapping.get(key)
            if widget is None:
                continue
            if isinstance(widget, QtWidgets.QComboBox):
                idx = widget.findText(str(target))
                if idx >= 0:
                    widget.setCurrentIndex(idx)
            else:
                widget.setValue(target)
        self._refresh_suggestions()
        self.status_label.setText(
            "Applied suggested values. Click Run to simulate.")

    # ------------------------------------------------------------- autotune
    def _start_autotune(self):
        if self._autotune_worker and self._autotune_worker.isRunning():
            self._autotune_worker.cancel()
            self.autotune_btn.setText("Auto-tune pump power")
            return
        target = self.autotune_target_spin.value()
        base = self._ring_config()
        self.autotune_log.clear()
        self.autotune_log.append(
            f"Searching for pump power giving {target} pulse(s)...\n"
            f"(each step runs a full simulation; this takes a few minutes)")
        self.autotune_btn.setText("Cancel auto-tune")
        self.run_btn.setEnabled(False)

        self._autotune_worker = AutotuneWorker(base, target)
        self._autotune_worker.progress.connect(self._on_autotune_progress)
        self._autotune_worker.finished.connect(self._on_autotune_done)
        self._autotune_worker.error.connect(self._on_autotune_error)
        self._autotune_worker.start()

    def _on_autotune_progress(self, message: str):
        self.autotune_log.append(message)

    def _on_autotune_done(self, result):
        self.autotune_btn.setText("Auto-tune pump power")
        self.run_btn.setEnabled(True)
        self.pump_spin.setValue(result.found_pump_w)
        verdict = "SUCCESS" if result.success else "closest match"
        self.autotune_log.append(
            f"\n{verdict}: pump = {result.found_pump_w:.3f} W -> "
            f"{result.found_count} pulse(s), "
            f"{result.found_energy_nj:.4f} nJ.\nPump field updated; click Run.")
        self._refresh_suggestions()

    def _on_autotune_error(self, message: str):
        self.autotune_btn.setText("Auto-tune pump power")
        self.run_btn.setEnabled(True)
        self.autotune_log.append("\nAuto-tune error:\n" + message)

    def _passive_config(self):
        params = PulseParams(
            shape=self.shape_combo.currentText(),
            width_fs=self.width_spin.value(),
            amplitude_w=self.amplitude_spin.value(),
            central_wl_nm=self.wavelength_spin.value())
        return SimulationConfig(
            pulse=params,
            fibre_name=self.fibre_combo.currentText(),
            fibre_length_m=self.length_spin.value(),
            num_samples=self.samples_spin.value())

    def _ring_config(self):
        return RingLaserConfig(
            er_fibre_name=self.er_combo.currentText(),
            active_length_m=self.active_len_spin.value(),
            passive_length_m=self.passive_len_spin.value(),
            pump_power_w=self.pump_spin.value(),
            output_tap_percent=self.tap_spin.value(),
            bandpass_transmission=self.bandpass_spin.value(),
            sa_mod_depth=self.sa_depth_spin.value(),
            sa_sat_power_w=self.sa_satp_spin.value(),
            round_trips=self.round_trips_spin.value(),
            seed_from_noise=self.noise_check.isChecked(),
            group_index=self._calib["group_index"],
            central_wl_nm=self._calib["central_wl_nm"],
            max_wl_nm=self._calib["max_wl_nm"],
            pump_wavelength_nm=self._calib["pump_wavelength_nm"],
            ase_min_nm=self._calib["ase_min_nm"],
            ase_max_nm=self._calib["ase_max_nm"],
            grid_points=self._calib["grid_points"])

    # ------------------------------------------------------------- preview
    def update_input_preview(self):
        if self._mode() != "passive":
            return
        params = PulseParams(
            shape=self.shape_combo.currentText(),
            width_fs=self.width_spin.value(),
            amplitude_w=self.amplitude_spin.value(),
            central_wl_nm=self.wavelength_spin.value())
        grid = build_grid(params)
        intensity = preview_intensity(grid, params)
        time_ps = grid.time_window * 1e12
        spectrum = np.abs(np.fft.fftshift(np.fft.fft(intensity))) ** 2
        wl = grid.lambda_window * 1e9

        self._plot_time(time_ps, intensity, title="Input Pulse — Time Domain")
        self._plot_spectrum(wl, spectrum, title="Input Pulse — Spectrum")
        self._plot_combined(time_ps, intensity, wl, spectrum)
        self.live_canvas.draw()
        self.status_label.setText("Input waveform preview updated.")

    # ----------------------------------------------------------- simulation
    def start_simulation(self):
        if self._worker and self._worker.isRunning():
            return
        self.stop_animation()
        self.run_btn.setEnabled(False)
        self.preview_btn.setEnabled(False)
        self.progress.setVisible(True)
        mode = self._mode()
        config = self._passive_config() if mode == "passive" \
            else self._ring_config()
        self.status_label.setText(
            "Running simulation… (ring laser can take a while)")

        self._worker = SimulationWorker(mode, config)
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_done(self, evolution: Evolution):
        self._evolution = evolution
        self.progress.setVisible(False)
        self.run_btn.setEnabled(True)
        self.preview_btn.setEnabled(self._mode() == "passive")

        max_step = max(0, evolution.n_steps - 1)
        self.step_slider.setMaximum(max_step)
        self.step_slider.setValue(max_step)
        self.step_slider.setEnabled(max_step > 0)
        self.play_btn.setEnabled(max_step > 0)

        self._plot_evolution_3d(evolution)
        self.show_step(max_step)
        self.status_label.setText(
            f"Done — {evolution.n_steps} steps ({evolution.step_unit}). "
            f"Use the slider or Play to step through.")

    def _on_error(self, message: str):
        self.progress.setVisible(False)
        self.run_btn.setEnabled(True)
        self.preview_btn.setEnabled(self._mode() == "passive")
        self.status_label.setText("Simulation failed.")
        QtWidgets.QMessageBox.critical(self, "Simulation Error", message)

    # --------------------------------------------------------------- replay
    def show_step(self, index: int):
        if self._evolution is None:
            return
        index = int(index)
        self._anim_index = index
        evo = self._evolution
        intensity = evo.time_evolution[index]
        spectrum = evo.spectral_evolution[index]
        label = evo.label(index)

        self.step_label.setText(f"Step {index}: {label}")
        overlay = evo.input_intensity
        self._plot_time(evo.time_ps, intensity, overlay=overlay,
                        title=f"Time Domain — {label}")
        self._plot_spectrum(evo.wavelength_nm, spectrum,
                            title=f"Spectrum — {label}")
        self._plot_combined(evo.time_ps, intensity, evo.wavelength_nm,
                            spectrum)
        self.live_canvas.draw()

    def toggle_animation(self):
        if self._anim_playing:
            self.stop_animation()
        else:
            self._anim_playing = True
            self.play_btn.setText("Pause")
            self.stop_btn.setEnabled(True)
            self._anim_timer.start(150)

    def stop_animation(self):
        self._anim_playing = False
        self._anim_timer.stop()
        self.play_btn.setText("Play")
        self.stop_btn.setEnabled(False)

    def _advance_animation(self):
        if self._evolution is None:
            return
        nxt = self._anim_index + 1
        if nxt > self.step_slider.maximum():
            nxt = 0
        self.step_slider.setValue(nxt)

    # ---------------------------------------------------------------- plots
    def _plot_time(self, time_ps, intensity, overlay=None, title=""):
        self.time_ax.clear()
        if overlay is not None:
            self.time_ax.plot(time_ps, overlay, color="0.7", lw=1.0,
                              label="input", alpha=0.8)
        self.time_ax.plot(time_ps, intensity, color="C0", lw=1.5,
                          label="current")
        self.time_ax.set_xlim(*TIME_AXIS_LIMITS)
        self.time_ax.set_xlabel("Time (ps)")
        self.time_ax.set_ylabel("Power (W)")
        self.time_ax.set_title(title, fontsize=10)
        self.time_ax.grid(True, alpha=0.3)
        self.time_ax.legend(loc="upper right", fontsize=8)

    def _plot_spectrum(self, wavelength_nm, spectrum, title=""):
        self.spec_ax.clear()
        spec = np.maximum(spectrum, 1e-30)
        self.spec_ax.semilogy(wavelength_nm, spec, color="C1", lw=1.2)
        self.spec_ax.set_xlabel("Wavelength (nm)")
        self.spec_ax.set_ylabel("Spectral density (arb.)")
        self.spec_ax.set_title(title, fontsize=10)
        self.spec_ax.grid(True, which="both", alpha=0.3)

    def _plot_combined(self, time_ps, intensity, wavelength_nm, spectrum):
        self.combined_ax.clear()
        self.combined_twin.clear()

        ipeak = np.max(intensity) if np.max(intensity) > 0 else 1.0
        speak = np.max(spectrum) if np.max(spectrum) > 0 else 1.0

        line_t, = self.combined_ax.plot(
            time_ps, intensity / ipeak, color="C0", lw=1.5)
        self.combined_ax.set_xlim(*TIME_AXIS_LIMITS)
        self.combined_ax.set_xlabel("Time (ps)", color="C0")
        self.combined_ax.set_ylabel("Normalized power / spectrum")
        self.combined_ax.tick_params(axis="x", colors="C0")
        self.combined_ax.set_title(
            "Combined: time (bottom) + spectrum (top)", fontsize=10)
        self.combined_ax.grid(True, alpha=0.3)

        line_s, = self.combined_twin.plot(
            wavelength_nm, spectrum / speak, color="C1", lw=1.2)
        self.combined_twin.set_xlabel("Wavelength (nm)", color="C1")
        self.combined_twin.tick_params(axis="x", colors="C1")
        self.combined_ax.legend(
            [line_t, line_s], ["Power(t)", "Spectrum(λ)"],
            loc="upper right", fontsize=8)

    def _plot_evolution_3d(self, evo: Evolution):
        if self._evo_cbar is not None:
            self._evo_cbar.remove()
            self._evo_cbar = None
        self.evo_ax.clear()
        t = evo.time_ps
        steps = evo.steps
        data = evo.time_evolution

        mask = (t >= TIME_AXIS_LIMITS[0]) & (t <= TIME_AXIS_LIMITS[1])
        t_win = t[mask]
        data_win = data[:, mask]
        stride = max(1, len(t_win) // 200)
        t_ds = t_win[::stride]
        data_ds = data_win[:, ::stride]

        T, S = np.meshgrid(t_ds, steps)
        surf = self.evo_ax.plot_surface(
            T, S, data_ds, cmap="inferno", linewidth=0, antialiased=True)
        self.evo_ax.set_xlabel("Time (ps)")
        ylabel = "Round trip" if evo.step_unit == "round trip" \
            else "Fiber position (m)"
        self.evo_ax.set_ylabel(ylabel)
        self.evo_ax.set_zlabel("Power (W)")
        self.evo_ax.set_title("Pulse Evolution")
        self._evo_cbar = self.evo_canvas.figure.colorbar(
            surf, ax=self.evo_ax, shrink=0.6, pad=0.1)
        self.evo_canvas.draw()
