"""
Spline Controller Panel – MetaMobility Unified GUI
Improved redesign of Final_spline_gui.py
"""

import sys
import os
import subprocess
import threading
import time
from collections import deque

import numpy as np
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QLineEdit, QGroupBox,
    QSplitter, QSizePolicy, QFrame, QDoubleSpinBox,
    QMessageBox, QAction
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QColor
import pyqtgraph as pg
from scipy.interpolate import CubicHermiteSpline

from data_receiver import ExoDataReceiver
import theme


# ── pyqtgraph config ──────────────────────────────────────────────────────────
pg.setConfigOption("background", theme.PLOT_BG)
pg.setConfigOption("foreground", theme.PLOT_FG)
pg.setConfigOptions(antialias=True)


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _styled_plot(title: str, x_label: str, y_label: str) -> pg.PlotWidget:
    w = pg.PlotWidget(title=title)
    w.setLabel("left",   y_label)
    w.setLabel("bottom", x_label)
    w.showGrid(x=True, y=True, alpha=0.15)
    w.getPlotItem().getViewBox().setBackgroundColor(theme.PLOT_BG)
    title_item = w.getPlotItem().titleLabel
    title_item.setText(title, color=theme.TEXT_SECONDARY, size="11pt")
    for ax in ("left", "bottom"):
        w.getPlotItem().getAxis(ax).setPen(pg.mkPen(theme.BORDER))
        w.getPlotItem().getAxis(ax).setTextPen(pg.mkPen(theme.TEXT_SECONDARY))
    return w


def _badge(text: str, color: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"background:{color}22; color:{color}; border:1px solid {color}55;"
        " border-radius:10px; padding:2px 10px; font-size:11px; font-weight:600;"
    )
    lbl.setFixedHeight(22)
    return lbl


# ─────────────────────────────────────────────────────────────────────────────
#  SplineSpinBox – combined numeric box with validation
# ─────────────────────────────────────────────────────────────────────────────

class SplineSpinBox(QDoubleSpinBox):
    def __init__(self, value: float, vmin: float, vmax: float,
                 step: float = 1.0, decimals: int = 1, parent=None):
        super().__init__(parent)
        self.setRange(vmin, vmax)
        self.setSingleStep(step)
        self.setDecimals(decimals)
        self.setValue(value)
        self.setFixedWidth(72)
        self.setAlignment(Qt.AlignCenter)


# ─────────────────────────────────────────────────────────────────────────────
#  SplineControllerPanel
# ─────────────────────────────────────────────────────────────────────────────

class SplineControllerPanel(QWidget):
    """Full Spline Controller UI embedded as a QWidget (no QMainWindow)."""

    status_changed = pyqtSignal(str, str)   # (message, colour)
    controller_state_changed = pyqtSignal(bool)  # running=True/False

    # ── Default spline control-point values ───────────────────────────────────
    _DEFAULTS = dict(
        ext_start_phase=0,   ext_start_torque=0,
        ext_max_phase=15,    ext_max_torque=5.0,
        ext_end_phase=30,    ext_end_torque=0,
        flex_start_phase=40, flex_start_torque=0,
        flex_max_phase=65,   flex_max_torque=-5.0,
        flex_end_phase=85,   flex_end_torque=0,
    )

    TIME_WINDOW  = 10   # seconds
    SAMPLE_RATE  = 100  # Hz
    PLOT_HZ      = 20   # GUI refresh rate

    def __init__(self, parent=None):
        super().__init__(parent)

        # ── State ─────────────────────────────────────────────────────────────
        self.__dict__.update(self._DEFAULTS)

        max_n = self.TIME_WINDOW * self.SAMPLE_RATE
        self._t_idx       = 0
        self._time        = deque(maxlen=max_n)
        self._gait_L      = deque(maxlen=max_n)
        self._gait_R      = deque(maxlen=max_n)
        self._pos_L       = deque(maxlen=max_n)
        self._pos_R       = deque(maxlen=max_n)
        self._vel_L       = deque(maxlen=max_n)
        self._vel_R       = deque(maxlen=max_n)
        self._cmd_L       = deque(maxlen=max_n)
        self._cmd_R       = deque(maxlen=max_n)
        self._latest_gait = 0.0

        self._spline      = None
        self._spline_x    = np.array([])
        self._spline_y    = np.array([])

        self._controller_proc   = None
        self._controller_mode   = None
        self._connected         = False

        # ── Data receiver ─────────────────────────────────────────────────────
        self._receiver = ExoDataReceiver()
        self._receiver.motor_data_received.connect(self._on_data)
        self._receiver.connection_status.connect(self._on_conn_status)

        # ── Build UI ──────────────────────────────────────────────────────────
        self._build_ui()
        self._rebuild_spline()
        self._update_spline_plot()

        # ── Plot timer ────────────────────────────────────────────────────────
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_plots)
        self._timer.start(1000 // self.PLOT_HZ)

        # ── Start listening ───────────────────────────────────────────────────
        self._receiver.start()

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # Top bar
        root.addWidget(self._build_top_bar())

        # Main splitter: plots | controls
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        plots_widget = QWidget()
        plots_layout = QVBoxLayout(plots_widget)
        plots_layout.setContentsMargins(0, 0, 0, 0)
        plots_layout.setSpacing(8)

        # Gait phase + spline side by side
        upper = QSplitter(Qt.Horizontal)
        upper.setChildrenCollapsible(False)
        upper.addWidget(self._build_gait_phase_plot())
        upper.addWidget(self._build_spline_plot())
        upper.setSizes([500, 600])
        plots_layout.addWidget(upper, stretch=2)

        # Lower data plot
        plots_layout.addWidget(self._build_data_plot(), stretch=1)

        splitter.addWidget(plots_widget)
        splitter.addWidget(self._build_control_panel())
        splitter.setSizes([900, 320])

        root.addWidget(splitter, stretch=1)

        # Status bar row
        root.addWidget(self._build_status_row())

    # ── Top bar (controller controls) ─────────────────────────────────────────

    def _build_top_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("topBar")
        bar.setStyleSheet(
            f"QFrame#topBar {{ background:{theme.BG_CARD}; border-radius:8px;"
            f" border:1px solid {theme.BORDER}; }}"
        )
        bar.setFixedHeight(52)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(12)

        # Controller type selector
        type_lbl = QLabel("Controller:")
        type_lbl.setStyleSheet(f"color:{theme.TEXT_SECONDARY}; font-weight:500;")
        layout.addWidget(type_lbl)

        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["TBE Controller", "CNN Controller"])
        self._mode_combo.setFixedWidth(160)
        layout.addWidget(self._mode_combo)

        layout.addSpacing(8)

        # Start / Stop button
        self._ctrl_btn = QPushButton("▶  Start Controller")
        self._ctrl_btn.setStyleSheet(theme.BTN_GREEN)
        self._ctrl_btn.setFixedWidth(175)
        self._ctrl_btn.clicked.connect(self._toggle_controller)
        layout.addWidget(self._ctrl_btn)

        layout.addStretch()

        # Display leg selector
        leg_lbl = QLabel("Display Leg:")
        leg_lbl.setStyleSheet(f"color:{theme.TEXT_SECONDARY}; font-weight:500;")
        layout.addWidget(leg_lbl)

        self._leg_combo = QComboBox()
        self._leg_combo.addItems(["Left Leg", "Right Leg"])
        self._leg_combo.setFixedWidth(120)
        layout.addWidget(self._leg_combo)

        layout.addSpacing(8)

        # Reset button
        reset_btn = QPushButton("↺  Reset Data")
        reset_btn.setStyleSheet(theme.BTN_GHOST)
        reset_btn.setFixedWidth(120)
        reset_btn.clicked.connect(self._reset_data)
        layout.addWidget(reset_btn)

        return bar

    # ── Gait Phase Plot ───────────────────────────────────────────────────────

    def _build_gait_phase_plot(self) -> QWidget:
        w = _styled_plot("Gait Phase Estimation", "Time (s)", "Gait Phase (%)")
        w.setYRange(0, 100)
        w.setXRange(0, self.TIME_WINDOW)
        self._gait_curve = w.plot(
            pen=pg.mkPen(theme.ACCENT_BLUE, width=2), name="Gait %"
        )
        w.getPlotItem().addLegend(offset=(10, 10))
        self._gait_plot_widget = w
        return w

    # ── Spline Profile Plot ───────────────────────────────────────────────────

    def _build_spline_plot(self) -> QWidget:
        w = _styled_plot("Torque Spline Profile", "Gait Phase (%)", "Torque (Nm)")
        w.setXRange(0, 100)
        w.setYRange(-8, 8)
        # Zero line
        w.addLine(y=0, pen=pg.mkPen(theme.BORDER, width=1, style=Qt.DashLine))
        # Spline curve
        self._spline_curve = w.plot(
            pen=pg.mkPen(theme.ACCENT_GREEN, width=2.5), name="Profile"
        )
        # Control points
        self._spline_dots = w.plot(
            pen=None, symbol="o", symbolSize=9,
            symbolBrush=pg.mkBrush(theme.ACCENT_ORANGE),
            symbolPen=pg.mkPen(theme.BG_DEEP, width=1.5),
        )
        # Current phase indicator
        self._phase_line = w.addLine(
            x=0, pen=pg.mkPen(theme.ACCENT_RED, width=1.5, style=Qt.DashLine)
        )
        w.getPlotItem().addLegend(offset=(10, 10))
        self._spline_plot_widget = w
        return w

    # ── Bottom data plot ──────────────────────────────────────────────────────

    def _build_data_plot(self) -> QWidget:
        container = QWidget()
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(4)

        row = QHBoxLayout()
        sel_lbl = QLabel("Signal:")
        sel_lbl.setStyleSheet(f"color:{theme.TEXT_SECONDARY};")
        row.addWidget(sel_lbl)

        self._data_selector = QComboBox()
        self._data_selector.addItems([
            "Motor Position (L/R)",
            "Motor Velocity (L/R)",
            "Motor Commands (L/R)",
            "Gait Phase (L/R)",
        ])
        self._data_selector.setFixedWidth(200)
        self._data_selector.currentIndexChanged.connect(self._rebuild_data_plot)
        row.addWidget(self._data_selector)
        row.addStretch()
        vbox.addLayout(row)

        self._data_widget = _styled_plot("Motor Position (L/R)", "Time (s)", "Value")
        self._data_widget.setXRange(0, self.TIME_WINDOW)
        self._data_widget.getPlotItem().addLegend(offset=(10, 10))
        self._data_plot_L = self._data_widget.plot(
            pen=pg.mkPen(theme.PLOT_LEFT_PEN, width=2), name="Left"
        )
        self._data_plot_R = self._data_widget.plot(
            pen=pg.mkPen(theme.PLOT_RIGHT_PEN, width=2), name="Right"
        )
        vbox.addWidget(self._data_widget)
        return container

    # ── Right control panel ───────────────────────────────────────────────────

    def _build_control_panel(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(340)
        vbox = QVBoxLayout(panel)
        vbox.setContentsMargins(6, 0, 0, 0)
        vbox.setSpacing(10)

        # Spline control points group
        spline_grp = QGroupBox("Spline Control Points")
        grid = QGridLayout(spline_grp)
        grid.setSpacing(6)
        grid.setContentsMargins(10, 18, 10, 10)

        headers = ["Control Point", "Phase (%)", "Torque (Nm)"]
        for col, h in enumerate(headers):
            lbl = QLabel(h)
            lbl.setStyleSheet(
                f"color:{theme.TEXT_SECONDARY}; font-size:11px; font-weight:600;"
                " text-transform:uppercase; letter-spacing:0.4px;"
            )
            grid.addWidget(lbl, 0, col)

        # Each row: label, phase spin, torque spin, is_peak
        rows = [
            ("Extension Start", "ext_start_phase",  "ext_start_torque",  False),
            ("Extension Peak",  "ext_max_phase",     "ext_max_torque",    True),
            ("Extension End",   "ext_end_phase",     "ext_end_torque",    False),
            ("Flexion Start",   "flex_start_phase",  "flex_start_torque", False),
            ("Flexion Peak",    "flex_max_phase",    "flex_max_torque",   True),
            ("Flexion End",     "flex_end_phase",    "flex_end_torque",   False),
        ]

        self._phase_spins  = {}
        self._torque_spins = {}

        for i, (label, phase_attr, torque_attr, is_peak) in enumerate(rows, start=1):
            name_lbl = QLabel(label)
            if is_peak:
                name_lbl.setStyleSheet(f"color:{theme.ACCENT_BLUE}; font-weight:600;")
            else:
                name_lbl.setStyleSheet(f"color:{theme.TEXT_PRIMARY};")
            grid.addWidget(name_lbl, i, 0)

            ps = SplineSpinBox(getattr(self, phase_attr),  0.0, 100.0, 1.0, 1)
            ts = SplineSpinBox(getattr(self, torque_attr), -20.0, 20.0, 0.5, 2)
            ps.valueChanged.connect(self._on_spin_changed)
            ts.valueChanged.connect(self._on_spin_changed)
            self._phase_spins[phase_attr]   = ps
            self._torque_spins[torque_attr] = ts
            grid.addWidget(ps, i, 1)
            grid.addWidget(ts, i, 2)

        vbox.addWidget(spline_grp)

        # Live torque readout
        readout_grp = QGroupBox("Live Torque Command")
        readout_layout = QHBoxLayout(readout_grp)
        self._torque_lbl_L = QLabel("L: — Nm")
        self._torque_lbl_R = QLabel("R: — Nm")
        for lbl in (self._torque_lbl_L, self._torque_lbl_R):
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(
                f"color:{theme.ACCENT_GREEN}; font-size:16px; font-weight:700;"
                f" background:{theme.BG_INPUT}; border-radius:6px; padding:6px;"
            )
        readout_layout.addWidget(self._torque_lbl_L)
        readout_layout.addWidget(self._torque_lbl_R)
        vbox.addWidget(readout_grp)

        vbox.addStretch()
        return panel

    # ── Status row ────────────────────────────────────────────────────────────

    def _build_status_row(self) -> QWidget:
        row = QFrame()
        row.setStyleSheet(
            f"QFrame {{ background:{theme.BG_CARD}; border-radius:6px;"
            f" border:1px solid {theme.BORDER}; }}"
        )
        row.setFixedHeight(32)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(12, 0, 12, 0)

        self._conn_badge = _badge("●  Disconnected", theme.ACCENT_RED)
        layout.addWidget(self._conn_badge)
        layout.addSpacing(12)

        self._status_lbl = QLabel("Waiting for data…")
        self._status_lbl.setStyleSheet(f"color:{theme.TEXT_SECONDARY}; font-size:12px;")
        layout.addWidget(self._status_lbl)
        layout.addStretch()

        self._mode_badge = _badge("No Controller", theme.TEXT_SECONDARY)
        layout.addWidget(self._mode_badge)
        return row

    # ── Spline Logic ──────────────────────────────────────────────────────────

    def _on_spin_changed(self):
        for attr, spin in self._phase_spins.items():
            setattr(self, attr, spin.value())
        for attr, spin in self._torque_spins.items():
            setattr(self, attr, spin.value())
        self._rebuild_spline()
        self._update_spline_plot()

    def _rebuild_spline(self):
        self._spline_x = np.array([
            self.ext_start_phase, self.ext_max_phase, self.ext_end_phase,
            self.flex_start_phase, self.flex_max_phase, self.flex_end_phase, 100,
        ])
        self._spline_y = np.array([
            self.ext_start_torque, self.ext_max_torque, self.ext_end_torque,
            self.flex_start_torque, self.flex_max_torque, self.flex_end_torque,
            self.ext_start_torque,
        ])
        idx = np.argsort(self._spline_x)
        self._spline_x = self._spline_x[idx]
        self._spline_y = self._spline_y[idx]
        dydx = np.zeros_like(self._spline_y)
        try:
            self._spline = CubicHermiteSpline(
                self._spline_x, self._spline_y, dydx, extrapolate="periodic"
            )
        except Exception as e:
            print(f"[SplinePanel] Spline error: {e}")
            self._spline = None

    def _update_spline_plot(self):
        if self._spline is not None:
            xs = np.linspace(0, 100, 500)
            try:
                ys = self._spline(xs)
                self._spline_curve.setData(xs, ys)
            except Exception:
                self._spline_curve.setData([0, 100], [0, 0])
        ctrl_x = self._spline_x[:-1]
        ctrl_y = self._spline_y[:-1]
        self._spline_dots.setData(ctrl_x, ctrl_y)

    # ── Data Handling ─────────────────────────────────────────────────────────

    def _on_data(self, var: str, ts: float, val: float):
        t = self._t_idx / self.SAMPLE_RATE
        if var == "mtr_pos_L":
            self._pos_L.append(val)
            self._time.append(t)
            self._t_idx += 1
        elif var == "mtr_pos_R":
            self._pos_R.append(val)
        elif var == "mtr_vel_L":
            self._vel_L.append(val)
        elif var == "mtr_vel_R":
            self._vel_R.append(val)
        elif var in ("mtr_cmd_L", "cmd_L"):
            self._cmd_L.append(val)
            self._torque_lbl_L.setText(f"L: {val:+.2f} Nm")
        elif var in ("mtr_cmd_R", "cmd_R"):
            self._cmd_R.append(val)
            self._torque_lbl_R.setText(f"R: {val:+.2f} Nm")
        elif var in ("gait_pct_L", "phase_L_%"):
            self._gait_L.append(val)
            if self._leg_combo.currentText() == "Left Leg":
                self._latest_gait = val
        elif var in ("gait_pct_R", "phase_R_%"):
            self._gait_R.append(val)
            if self._leg_combo.currentText() == "Right Leg":
                self._latest_gait = val

    def _on_conn_status(self, ok: bool, msg: str):
        self._connected = ok
        if ok:
            self._conn_badge.setText("●  Connected")
            self._conn_badge.setStyleSheet(
                f"background:{theme.ACCENT_GREEN}22; color:{theme.ACCENT_GREEN};"
                f" border:1px solid {theme.ACCENT_GREEN}55; border-radius:10px;"
                " padding:2px 10px; font-size:11px; font-weight:600;"
            )
        else:
            self._conn_badge.setText("●  Disconnected")
            self._conn_badge.setStyleSheet(
                f"background:{theme.ACCENT_RED}22; color:{theme.ACCENT_RED};"
                f" border:1px solid {theme.ACCENT_RED}55; border-radius:10px;"
                " padding:2px 10px; font-size:11px; font-weight:600;"
            )
        self._status_lbl.setText(msg)
        self.status_changed.emit(msg, theme.ACCENT_GREEN if ok else theme.ACCENT_RED)

    # ── Plot Refresh ──────────────────────────────────────────────────────────

    def _refresh_plots(self):
        if not self._time:
            return
        t_arr = np.array(self._time)
        cur_t = t_arr[-1]
        x_min = max(0.0, cur_t - self.TIME_WINDOW)
        x_max = max(float(self.TIME_WINDOW), cur_t)

        # Gait phase
        gait = self._gait_L if self._leg_combo.currentText() == "Left Leg" else self._gait_R
        if gait:
            n = min(len(t_arr), len(gait))
            self._gait_curve.setData(t_arr[-n:], np.array(list(gait)[-n:]))
            self._phase_line.setValue(self._latest_gait)
        self._gait_plot_widget.setXRange(x_min, x_max, padding=0)

        # Data plot
        self._refresh_data_plot(t_arr, x_min, x_max)

    def _rebuild_data_plot(self):
        idx = self._data_selector.currentIndex()
        titles = [
            ("Motor Position (L/R)",  "Position (deg)"),
            ("Motor Velocity (L/R)",  "Velocity (deg/s)"),
            ("Motor Commands (L/R)",  "Torque (Nm)"),
            ("Gait Phase (L/R)",      "Gait Phase (%)"),
        ]
        title, y_label = titles[idx]
        self._data_widget.setTitle(title)
        self._data_widget.setLabel("left", y_label)
        self._data_widget.enableAutoRange(axis="y", enable=True)

    def _refresh_data_plot(self, t_arr, x_min, x_max):
        idx = self._data_selector.currentIndex()
        datasets = [
            (self._pos_L,  self._pos_R,  180.0 / np.pi, True),   # pos (negate left)
            (self._vel_L,  self._vel_R,  180.0 / np.pi, True),
            (self._cmd_L,  self._cmd_R,  1.0,            False),
            (self._gait_L, self._gait_R, 1.0,            False),
        ]
        dL, dR, scale, negate_L = datasets[idx]
        if dL:
            n = min(len(t_arr), len(dL))
            arr = np.array(list(dL)[-n:]) * scale
            if negate_L:
                arr = -arr
            self._data_plot_L.setData(t_arr[-n:], arr)
        if dR:
            n = min(len(t_arr), len(dR))
            arr = np.array(list(dR)[-n:]) * scale
            self._data_plot_R.setData(t_arr[-n:], arr)
        self._data_widget.setXRange(x_min, x_max, padding=0)

    # ── Controller Management ─────────────────────────────────────────────────

    def _toggle_controller(self):
        if self._controller_proc is None or self._controller_proc.poll() is not None:
            self._start_controller()
        else:
            self._stop_controller()

    def _start_controller(self):
        mode      = self._mode_combo.currentText()
        base_path = "/home/kaustubh-meta/hip_exo/Ryan_Hridayam"
        script    = "run_exo_exp_TBE.py" if "TBE" in mode else "spline_controller_batch2.py"
        path      = os.path.join(base_path, script)
        if not os.path.exists(path):
            QMessageBox.warning(
                self, "Script Not Found",
                f"Controller script not found:\n{path}\n\n"
                "Update the path in spline_panel.py → _start_controller()."
            )
            return
        try:
            self._controller_proc = subprocess.Popen(
                [sys.executable, script], cwd=base_path,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                universal_newlines=True, bufsize=1, env=os.environ.copy(),
            )
            self._controller_mode = mode
            self._ctrl_btn.setText("■  Stop Controller")
            self._ctrl_btn.setStyleSheet(theme.BTN_RED)
            self._mode_badge.setText(f"  {mode}")
            self._mode_badge.setStyleSheet(
                f"background:{theme.ACCENT_GREEN}22; color:{theme.ACCENT_GREEN};"
                f" border:1px solid {theme.ACCENT_GREEN}55; border-radius:10px;"
                " padding:2px 10px; font-size:11px; font-weight:600;"
            )
            threading.Thread(
                target=self._monitor_proc, daemon=True
            ).start()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start controller:\n{e}")

    def _stop_controller(self):
        if not self._controller_proc:
            return
        try:
            self._controller_proc.terminate()
            try:
                self._controller_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._controller_proc.kill()
                self._controller_proc.wait()
            self._controller_proc = None
        except Exception as e:
            QMessageBox.warning(self, "Warning", f"Error stopping controller:\n{e}")
        self._ctrl_btn.setText("▶  Start Controller")
        self._ctrl_btn.setStyleSheet(theme.BTN_GREEN)
        self._mode_badge.setText("No Controller")
        self._mode_badge.setStyleSheet(
            f"background:{theme.TEXT_SECONDARY}22; color:{theme.TEXT_SECONDARY};"
            f" border:1px solid {theme.TEXT_SECONDARY}55; border-radius:10px;"
            " padding:2px 10px; font-size:11px; font-weight:600;"
        )

    def _monitor_proc(self):
        if not self._controller_proc:
            return
        for line in self._controller_proc.stdout:
            print(f"[Spline Ctrl] {line.rstrip()}")
        self._controller_proc.wait()
        QTimer.singleShot(0, self._on_proc_stopped)

    def _on_proc_stopped(self):
        if self._controller_proc and self._controller_proc.poll() is not None:
            rc = self._controller_proc.returncode
            self._controller_proc = None
            self._ctrl_btn.setText("▶  Start Controller")
            self._ctrl_btn.setStyleSheet(theme.BTN_GREEN)
            msg = (
                f"{self._controller_mode} stopped (exit {rc})"
                if rc else f"{self._controller_mode} stopped"
            )
            self._status_lbl.setText(msg)
            self._controller_mode = None

    # ── Reset ─────────────────────────────────────────────────────────────────

    def _reset_data(self):
        self._t_idx = 0
        for buf in (
            self._time, self._gait_L, self._gait_R,
            self._pos_L, self._pos_R, self._vel_L, self._vel_R,
            self._cmd_L, self._cmd_R,
        ):
            buf.clear()
        self._latest_gait = 0.0
        self._gait_plot_widget.setXRange(0, self.TIME_WINDOW)
        self._data_widget.setXRange(0, self.TIME_WINDOW)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def shutdown(self):
        """Call when the panel is being closed/switched away from."""
        if self._controller_proc and self._controller_proc.poll() is None:
            self._stop_controller()
        self._receiver.stop()
        self._timer.stop()
