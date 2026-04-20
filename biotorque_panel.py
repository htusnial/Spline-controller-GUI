"""
Biotorque Controller Panel – MetaMobility Unified GUI
Improved redesign of new_biotorque_gui.py
"""

import sys
import os
import json
import subprocess
import threading
import time
from collections import deque
from datetime import datetime

import numpy as np
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QComboBox, QLineEdit, QGroupBox,
    QSplitter, QSizePolicy, QFrame, QDoubleSpinBox, QSpinBox,
    QCheckBox, QTabWidget, QFileDialog, QMessageBox, QScrollArea
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont
import pyqtgraph as pg

from data_receiver import ExoDataReceiver
import theme


# ── pyqtgraph config ──────────────────────────────────────────────────────────
pg.setConfigOption("background", theme.PLOT_BG)
pg.setConfigOption("foreground", theme.PLOT_FG)
pg.setConfigOptions(antialias=True)


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _plot(title: str, x_lbl: str, y_lbl: str) -> pg.PlotWidget:
    w = pg.PlotWidget()
    w.setLabel("left",   y_lbl)
    w.setLabel("bottom", x_lbl)
    w.showGrid(x=True, y=True, alpha=0.15)
    w.getPlotItem().getViewBox().setBackgroundColor(theme.PLOT_BG)
    w.getPlotItem().titleLabel.setText(
        title, color=theme.TEXT_SECONDARY, size="10pt"
    )
    for ax in ("left", "bottom"):
        w.getPlotItem().getAxis(ax).setPen(pg.mkPen(theme.BORDER))
        w.getPlotItem().getAxis(ax).setTextPen(pg.mkPen(theme.TEXT_SECONDARY))
    return w


def _metric_card(title: str) -> tuple[QFrame, QLabel]:
    """Returns (frame, value_label)."""
    card = QFrame()
    card.setStyleSheet(
        f"QFrame {{ background:{theme.BG_INPUT}; border-radius:8px;"
        f" border:1px solid {theme.BORDER}; }}"
    )
    vbox = QVBoxLayout(card)
    vbox.setContentsMargins(10, 8, 10, 8)
    vbox.setSpacing(2)
    t = QLabel(title)
    t.setStyleSheet(
        f"color:{theme.TEXT_SECONDARY}; font-size:10px; font-weight:600;"
        " text-transform:uppercase; letter-spacing:0.5px; border:none;"
    )
    v = QLabel("—")
    v.setStyleSheet(
        f"color:{theme.ACCENT_BLUE}; font-size:20px; font-weight:700; border:none;"
    )
    v.setAlignment(Qt.AlignCenter)
    vbox.addWidget(t, alignment=Qt.AlignCenter)
    vbox.addWidget(v)
    return card, v


def _badge(text: str, color: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"background:{color}22; color:{color}; border:1px solid {color}55;"
        " border-radius:10px; padding:2px 10px; font-size:11px; font-weight:600;"
        " background-color:transparent;"
    )
    lbl.setFixedHeight(22)
    return lbl


# ─────────────────────────────────────────────────────────────────────────────
#  BiotorqueControllerPanel
# ─────────────────────────────────────────────────────────────────────────────

class BiotorqueControllerPanel(QWidget):

    status_changed = pyqtSignal(str, str)
    controller_state_changed = pyqtSignal(bool)

    _DEFAULT_CONFIG = {
        "trial_name":      "AB05_Maria-exo_on_30p-1",
        "trial_start_sec": 5,
        "trial_dur_sec":   30,
        "exo_ON":          True,
        "trigger_type":    "typing",
        "body_mass_kg":    57.0,
        "scale_factor":    0.30,
        "delay_factor":    10,
        "model_path": (
            "/home/metamobility2/Changseob/biotorque_controller/"
            "trained_model/baseline_TCN-wo_AB05_Maria/"
            "baseline_TCN-wo_AB05_Maria.trt"
        ),
    }

    TIME_WINDOW = 30
    SAMPLE_RATE = 100
    PLOT_HZ     = 20

    def __init__(self, parent=None):
        super().__init__(parent)

        max_n = self.TIME_WINDOW * self.SAMPLE_RATE
        self._t_idx = 0
        self._time  = deque(maxlen=max_n)

        self._pos_L       = deque(maxlen=max_n)
        self._pos_R       = deque(maxlen=max_n)
        self._cmd_L       = deque(maxlen=max_n)
        self._cmd_R       = deque(maxlen=max_n)
        self._imu_P       = deque(maxlen=max_n)
        self._imu_L       = deque(maxlen=max_n)
        self._imu_R       = deque(maxlen=max_n)
        self._out_L       = deque(maxlen=max_n)
        self._out_R       = deque(maxlen=max_n)
        self._filt_L      = deque(maxlen=max_n)
        self._filt_R      = deque(maxlen=max_n)
        self._loop_ms     = deque(maxlen=max_n)
        self._infer_ms    = deque(maxlen=max_n)

        self._controller_proc = None
        self._connected       = False

        self._receiver = ExoDataReceiver()
        self._receiver.motor_data_received.connect(self._on_data)
        self._receiver.connection_status.connect(self._on_conn_status)

        self._build_ui()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_plots)
        self._timer.start(1000 // self.PLOT_HZ)

        self._receiver.start()

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 8, 12)
        root.setSpacing(10)

        # ── Left sidebar ──────────────────────────────────────────────────────
        sidebar = self._build_sidebar()
        root.addWidget(sidebar)

        # ── Right plot area ───────────────────────────────────────────────────
        right = QVBoxLayout()
        right.setSpacing(8)

        right.addWidget(self._build_top_bar())

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_motor_tab(),       "⚙  Motor Data")
        self._tabs.addTab(self._build_imu_tab(),         "📡  IMU Data")
        self._tabs.addTab(self._build_torque_tab(),      "⚡  Torque Data")
        self._tabs.addTab(self._build_performance_tab(), "⏱  Performance")
        right.addWidget(self._tabs, stretch=1)

        right.addWidget(self._build_status_row())

        right_w = QWidget()
        right_w.setLayout(right)
        root.addWidget(right_w, stretch=1)

    # ── Sidebar ───────────────────────────────────────────────────────────────

    def _build_sidebar(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(310)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
        )
        inner = QWidget()
        vbox  = QVBoxLayout(inner)
        vbox.setContentsMargins(0, 0, 8, 0)
        vbox.setSpacing(10)

        # ── Metric cards ──────────────────────────────────────────────────────
        cards_grp = QGroupBox("Live Metrics")
        cards_grid = QHBoxLayout(cards_grp)
        cards_grid.setSpacing(6)

        c1, self._loop_val   = _metric_card("Loop")
        c2, self._infer_val  = _metric_card("Inference")
        c3, self._cmd_L_val  = _metric_card("Cmd L")
        c4, self._cmd_R_val  = _metric_card("Cmd R")

        for lbl in (self._loop_val, self._infer_val):
            lbl.setStyleSheet(
                f"color:{theme.ACCENT_CYAN}; font-size:18px; font-weight:700; border:none;"
            )
        for card in (c1, c2, c3, c4):
            cards_grid.addWidget(card)
        vbox.addWidget(cards_grp)

        # ── Trial Config ──────────────────────────────────────────────────────
        trial_grp = QGroupBox("Trial Configuration")
        form = QFormLayout(trial_grp)
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignRight)
        form.setContentsMargins(10, 18, 10, 10)

        cfg = self._DEFAULT_CONFIG

        self._trial_name  = QLineEdit(cfg["trial_name"])
        self._trial_start = QSpinBox()
        self._trial_start.setRange(0, 60);  self._trial_start.setValue(cfg["trial_start_sec"]); self._trial_start.setSuffix(" s")
        self._trial_dur   = QSpinBox()
        self._trial_dur.setRange(1, 600);   self._trial_dur.setValue(cfg["trial_dur_sec"]);    self._trial_dur.setSuffix(" s")
        self._trigger     = QComboBox()
        self._trigger.addItems(["typing", "mocap"])
        self._trigger.setCurrentText(cfg["trigger_type"])

        form.addRow("Trial Name:", self._trial_name)
        form.addRow("Start Delay:", self._trial_start)
        form.addRow("Duration:",   self._trial_dur)
        form.addRow("Trigger:",    self._trigger)
        vbox.addWidget(trial_grp)

        # ── Exo Control ───────────────────────────────────────────────────────
        exo_grp = QGroupBox("Exoskeleton Parameters")
        form2 = QFormLayout(exo_grp)
        form2.setSpacing(8)
        form2.setLabelAlignment(Qt.AlignRight)
        form2.setContentsMargins(10, 18, 10, 10)

        self._exo_on = QCheckBox("Exoskeleton Enabled")
        self._exo_on.setChecked(cfg["exo_ON"])

        self._body_mass = QDoubleSpinBox()
        self._body_mass.setRange(30, 200); self._body_mass.setValue(cfg["body_mass_kg"]); self._body_mass.setSuffix(" kg"); self._body_mass.setDecimals(1)

        self._scale = QDoubleSpinBox()
        self._scale.setRange(0, 1); self._scale.setValue(cfg["scale_factor"]); self._scale.setSingleStep(0.01); self._scale.setDecimals(2)

        self._delay = QSpinBox()
        self._delay.setRange(0, 200); self._delay.setValue(cfg["delay_factor"]); self._delay.setSuffix(" fr")

        form2.addRow(self._exo_on)
        form2.addRow("Body Mass:", self._body_mass)
        form2.addRow("Scale Factor:", self._scale)
        form2.addRow("Delay Factor:", self._delay)
        vbox.addWidget(exo_grp)

        # ── Model / Controller Scripts ────────────────────────────────────────
        model_grp = QGroupBox("Scripts & Model")
        ml = QVBoxLayout(model_grp)
        ml.setContentsMargins(10, 18, 10, 10)
        ml.setSpacing(6)

        # Controller script path (what file gets run)
        ctrl_row = QHBoxLayout()
        self._ctrl_script = QLineEdit("controller_baseline_biotorque.py")
        self._ctrl_script.setPlaceholderText("Path to controller .py script…")
        browse_ctrl_btn = QPushButton("Browse…")
        browse_ctrl_btn.setStyleSheet(theme.BTN_GHOST)
        browse_ctrl_btn.setFixedWidth(72)
        browse_ctrl_btn.clicked.connect(self._browse_script)
        ctrl_row.addWidget(self._ctrl_script)
        ctrl_row.addWidget(browse_ctrl_btn)

        self._model_path = QLineEdit(cfg["model_path"])
        self._model_path.setPlaceholderText("Path to .trt model file…")
        browse_btn = QPushButton("Browse…")
        browse_btn.setStyleSheet(theme.BTN_GHOST)
        browse_btn.clicked.connect(self._browse_model)

        ml.addWidget(QLabel("Controller Script:"))
        ml.addLayout(ctrl_row)
        ml.addSpacing(4)
        ml.addWidget(QLabel("TRT Model Path:"))
        ml.addWidget(self._model_path)
        ml.addWidget(browse_btn)
        vbox.addWidget(model_grp)

        # Config save / load
        cfg_row = QHBoxLayout()
        save_btn = QPushButton("Save Config")
        load_btn = QPushButton("Load Config")
        for b in (save_btn, load_btn):
            b.setStyleSheet(theme.BTN_GHOST)
            b.setFixedHeight(32)
        save_btn.clicked.connect(self._save_config)
        load_btn.clicked.connect(self._load_config)
        cfg_row.addWidget(save_btn)
        cfg_row.addWidget(load_btn)
        vbox.addLayout(cfg_row)

        # Save data
        save_data_btn = QPushButton("💾  Save Recorded Data")
        save_data_btn.setStyleSheet(theme.BTN_GHOST)
        save_data_btn.setFixedHeight(32)
        save_data_btn.clicked.connect(self._save_data)
        vbox.addWidget(save_data_btn)

        vbox.addStretch()

        scroll.setWidget(inner)
        return scroll

    # ── Top Bar ───────────────────────────────────────────────────────────────

    def _build_top_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("btTopBar")
        bar.setStyleSheet(
            f"QFrame#btTopBar {{ background:{theme.BG_CARD}; border-radius:8px;"
            f" border:1px solid {theme.BORDER}; }}"
        )
        bar.setFixedHeight(52)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(12)

        title = QLabel("Biotorque Exoskeleton Controller")
        title.setStyleSheet(f"color:{theme.TEXT_PRIMARY}; font-weight:600; font-size:14px;")
        layout.addWidget(title)

        layout.addStretch()

        reset_btn = QPushButton("↺  Reset Data")
        reset_btn.setStyleSheet(theme.BTN_GHOST)
        reset_btn.setFixedWidth(120)
        reset_btn.clicked.connect(self._reset_data)
        layout.addWidget(reset_btn)

        layout.addSpacing(8)

        # ── Primary Start / Stop button lives here so it's always visible ──
        self._start_btn = QPushButton("▶  Start Controller")
        self._start_btn.setStyleSheet(theme.BTN_GREEN)
        self._start_btn.setFixedWidth(175)
        self._start_btn.setFixedHeight(36)
        self._start_btn.clicked.connect(self._toggle_controller)
        layout.addWidget(self._start_btn)

        return bar

    # ── Plot Tabs ─────────────────────────────────────────────────────────────

    def _build_motor_tab(self) -> QWidget:
        w  = QWidget()
        vb = QVBoxLayout(w)
        vb.setSpacing(6)

        self._pos_widget = _plot("Motor Position", "Time (s)", "Position (°)")
        self._pos_widget.getPlotItem().addLegend(offset=(10, 10))
        self._pos_L_plot = self._pos_widget.plot(
            pen=pg.mkPen(theme.PLOT_LEFT_PEN, width=2), name="Left"
        )
        self._pos_R_plot = self._pos_widget.plot(
            pen=pg.mkPen(theme.PLOT_RIGHT_PEN, width=2), name="Right"
        )

        self._cmd_widget = _plot("Motor Commands", "Time (s)", "Torque (Nm)")
        self._cmd_widget.getPlotItem().addLegend(offset=(10, 10))
        self._cmd_L_plot = self._cmd_widget.plot(
            pen=pg.mkPen(theme.PLOT_LEFT_PEN, width=2), name="Left"
        )
        self._cmd_R_plot = self._cmd_widget.plot(
            pen=pg.mkPen(theme.PLOT_RIGHT_PEN, width=2), name="Right"
        )

        vb.addWidget(self._pos_widget)
        vb.addWidget(self._cmd_widget)
        return w

    def _build_imu_tab(self) -> QWidget:
        w  = QWidget()
        vb = QVBoxLayout(w)

        self._imu_widget = _plot("IMU Accelerometer (X-axis)", "Time (s)", "Acceleration (m/s²)")
        self._imu_widget.getPlotItem().addLegend(offset=(10, 10))
        self._imu_P_plot = self._imu_widget.plot(
            pen=pg.mkPen(theme.PLOT_GREEN_PEN, width=2), name="Pelvis"
        )
        self._imu_L_plot = self._imu_widget.plot(
            pen=pg.mkPen(theme.PLOT_LEFT_PEN,  width=2), name="Left Thigh"
        )
        self._imu_R_plot = self._imu_widget.plot(
            pen=pg.mkPen(theme.PLOT_RIGHT_PEN, width=2), name="Right Thigh"
        )

        vb.addWidget(self._imu_widget)
        return w

    def _build_torque_tab(self) -> QWidget:
        w  = QWidget()
        vb = QVBoxLayout(w)
        vb.setSpacing(6)

        self._model_widget = _plot("Model Output (Normalized)", "Time (s)", "Torque (Nm/kg)")
        self._model_widget.getPlotItem().addLegend(offset=(10, 10))
        self._model_L_plot = self._model_widget.plot(
            pen=pg.mkPen(theme.PLOT_LEFT_PEN, width=2), name="Left"
        )
        self._model_R_plot = self._model_widget.plot(
            pen=pg.mkPen(theme.PLOT_RIGHT_PEN, width=2), name="Right"
        )

        self._filt_widget = _plot("Filtered Torque", "Time (s)", "Torque (Nm)")
        self._filt_widget.getPlotItem().addLegend(offset=(10, 10))
        self._filt_L_plot = self._filt_widget.plot(
            pen=pg.mkPen(theme.PLOT_LEFT_PEN, width=2), name="Left"
        )
        self._filt_R_plot = self._filt_widget.plot(
            pen=pg.mkPen(theme.PLOT_RIGHT_PEN, width=2), name="Right"
        )

        vb.addWidget(self._model_widget)
        vb.addWidget(self._filt_widget)
        return w

    def _build_performance_tab(self) -> QWidget:
        w  = QWidget()
        vb = QVBoxLayout(w)

        self._perf_widget = _plot("System Timing", "Time (s)", "Time (ms)")
        self._perf_widget.getPlotItem().addLegend(offset=(10, 10))
        self._loop_plot  = self._perf_widget.plot(
            pen=pg.mkPen(theme.PLOT_YELLOW_PEN, width=2), name="Loop"
        )
        self._infer_plot = self._perf_widget.plot(
            pen=pg.mkPen(theme.PLOT_CYAN_PEN, width=2), name="Inference"
        )
        # 10 ms target line
        self._perf_widget.addLine(
            y=10, pen=pg.mkPen(theme.BORDER, width=1, style=Qt.DashLine)
        )

        vb.addWidget(self._perf_widget)
        return w

    # ── Status Row ────────────────────────────────────────────────────────────

    def _build_status_row(self) -> QFrame:
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
        layout.addSpacing(10)
        self._status_lbl = QLabel("Waiting for data…")
        self._status_lbl.setStyleSheet(f"color:{theme.TEXT_SECONDARY}; font-size:12px;")
        layout.addWidget(self._status_lbl)
        layout.addStretch()
        self._exo_badge = _badge("EXO OFF", theme.ACCENT_ORANGE)
        layout.addWidget(self._exo_badge)
        return row

    # ── Data Handling ─────────────────────────────────────────────────────────

    def _on_data(self, var: str, ts: float, val: float):
        t = self._t_idx / self.SAMPLE_RATE
        if var == "pos_L":
            self._pos_L.append(val)
            self._time.append(t)
            self._t_idx += 1
        elif var == "pos_R":
            self._pos_R.append(val)
        elif var == "mtr_cmd_L":
            self._cmd_L.append(val)
            self._cmd_L_val.setText(f"{val:+.2f}")
        elif var == "mtr_cmd_R":
            self._cmd_R.append(val)
            self._cmd_R_val.setText(f"{val:+.2f}")
        elif var == "imu_P_Acc_X":
            self._imu_P.append(val)
        elif var == "imu_L_Acc_X":
            self._imu_L.append(val)
        elif var == "imu_R_Acc_X":
            self._imu_R.append(val)
        elif var == "output_L":
            self._out_L.append(val)
        elif var == "output_R":
            self._out_R.append(val)
        elif var == "filtered_torque_L":
            self._filt_L.append(val)
        elif var == "filtered_torque_R":
            self._filt_R.append(val)
        elif var == "loop_time":
            ms = val * 1000
            self._loop_ms.append(ms)
            self._loop_val.setText(f"{ms:.1f}")
        elif var == "inference_time":
            ms = val * 1000
            self._infer_ms.append(ms)
            self._infer_val.setText(f"{ms:.1f}")

    def _on_conn_status(self, ok: bool, msg: str):
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
        t    = np.array(self._time)
        cur  = t[-1]
        xmin = max(0.0, cur - self.TIME_WINDOW)
        xmax = max(float(self.TIME_WINDOW), cur)

        def _set(curve, buf):
            if buf:
                n = min(len(t), len(buf))
                curve.setData(t[-n:], np.array(list(buf)[-n:]))

        _set(self._pos_L_plot,   self._pos_L)
        _set(self._pos_R_plot,   self._pos_R)
        _set(self._cmd_L_plot,   self._cmd_L)
        _set(self._cmd_R_plot,   self._cmd_R)
        _set(self._imu_P_plot,   self._imu_P)
        _set(self._imu_L_plot,   self._imu_L)
        _set(self._imu_R_plot,   self._imu_R)
        _set(self._model_L_plot, self._out_L)
        _set(self._model_R_plot, self._out_R)
        _set(self._filt_L_plot,  self._filt_L)
        _set(self._filt_R_plot,  self._filt_R)
        _set(self._loop_plot,    self._loop_ms)
        _set(self._infer_plot,   self._infer_ms)

        for w in (
            self._pos_widget, self._cmd_widget, self._imu_widget,
            self._model_widget, self._filt_widget, self._perf_widget,
        ):
            w.setXRange(xmin, xmax, padding=0)

    # ── Controller ────────────────────────────────────────────────────────────

    def _toggle_controller(self):
        if self._controller_proc is None or self._controller_proc.poll() is not None:
            self._start_controller()
        else:
            self._stop_controller()

    def _start_controller(self):
        try:
            tmp = self._write_temp_config()
            self._controller_proc = subprocess.Popen(
                [sys.executable, tmp],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            self._start_btn.setText("■  Stop Controller")
            self._start_btn.setStyleSheet(theme.BTN_RED)
            exo_on = self._exo_on.isChecked()
            self._exo_badge.setText("EXO ON" if exo_on else "EXO OFF")
            color = theme.ACCENT_GREEN if exo_on else theme.ACCENT_ORANGE
            self._exo_badge.setStyleSheet(
                f"background:{color}22; color:{color};"
                f" border:1px solid {color}55; border-radius:10px;"
                " padding:2px 10px; font-size:11px; font-weight:600;"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start controller:\n{e}")

    def _stop_controller(self):
        if not self._controller_proc:
            return
        try:
            self._controller_proc.terminate()
            try:
                self._controller_proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._controller_proc.kill()
            self._controller_proc = None
            if os.path.exists("_tmp_biotorque_config.py"):
                os.remove("_tmp_biotorque_config.py")
        except Exception as e:
            QMessageBox.warning(self, "Warning", f"Error stopping controller:\n{e}")
        self._start_btn.setText("▶  Start Controller")
        self._start_btn.setStyleSheet(theme.BTN_GREEN)
        self._exo_badge.setText("EXO OFF")
        self._exo_badge.setStyleSheet(
            f"background:{theme.ACCENT_ORANGE}22; color:{theme.ACCENT_ORANGE};"
            f" border:1px solid {theme.ACCENT_ORANGE}55; border-radius:10px;"
            " padding:2px 10px; font-size:11px; font-weight:600;"
        )

    def _write_temp_config(self) -> str:
        """Write a temporary controller script with updated params and return its path."""
        script = self._ctrl_script.text().strip() or "controller_baseline_biotorque.py"
        if not os.path.exists(script):
            raise FileNotFoundError(
                f"Controller script not found:\n{script}\n\n"
                "Update the path in the 'Scripts & Model' panel on the left."
            )
        with open(script, "r") as f:
            code = f.read()

        updates = {
            "trial_name = ":      f"trial_name = '{self._trial_name.text()}'",
            "trial_start_sec = ": f"trial_start_sec = {self._trial_start.value()}",
            "trial_dur_sec = ":   f"trial_dur_sec = {self._trial_dur.value()}",
            "exo_ON = ":          f"exo_ON = {self._exo_on.isChecked()}",
            "trigger_type = ":    f"trigger_type = '{self._trigger.currentText()}'",
            "body_mass_kg = ":    f"body_mass_kg = {self._body_mass.value()}",
            "trt_engine_path = ": f"trt_engine_path = '{self._model_path.text()}'",
        }
        lines = []
        for line in code.splitlines():
            out = line
            for key, val in updates.items():
                if line.strip().startswith(key):
                    out = val
                    break
            if "self.scale_factor = " in line:
                out = f"        self.scale_factor = {self._scale.value()}"
            elif "self.delay_factor = " in line:
                out = f"        self.delay_factor = {self._delay.value()}"
            lines.append(out)

        tmp = "_tmp_biotorque_config.py"
        with open(tmp, "w") as f:
            f.write("\n".join(lines))
        return tmp

    # ── Config & Data ─────────────────────────────────────────────────────────

    def _browse_model(self):
        fn, _ = QFileDialog.getOpenFileName(
            self, "Select TRT Model", "", "TensorRT Files (*.trt)"
        )
        if fn:
            self._model_path.setText(fn)

    def _browse_script(self):
        fn, _ = QFileDialog.getOpenFileName(
            self, "Select Controller Script", "", "Python Scripts (*.py)"
        )
        if fn:
            self._ctrl_script.setText(fn)

    def _save_config(self):
        fn, _ = QFileDialog.getSaveFileName(self, "Save Config", "", "JSON (*.json)")
        if not fn:
            return
        cfg = {
            "ctrl_script":     self._ctrl_script.text(),
            "trial_name":      self._trial_name.text(),
            "trial_start_sec": self._trial_start.value(),
            "trial_dur_sec":   self._trial_dur.value(),
            "trigger_type":    self._trigger.currentText(),
            "exo_ON":          self._exo_on.isChecked(),
            "body_mass_kg":    self._body_mass.value(),
            "scale_factor":    self._scale.value(),
            "delay_factor":    self._delay.value(),
            "model_path":      self._model_path.text(),
        }
        with open(fn, "w") as f:
            json.dump(cfg, f, indent=4)
        QMessageBox.information(self, "Saved", "Configuration saved.")

    def _load_config(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Load Config", "", "JSON (*.json)")
        if not fn:
            return
        try:
            with open(fn) as f:
                cfg = json.load(f)
            self._ctrl_script.setText(cfg.get("ctrl_script", "controller_baseline_biotorque.py"))
            self._trial_name.setText(cfg.get("trial_name", ""))
            self._trial_start.setValue(cfg.get("trial_start_sec", 5))
            self._trial_dur.setValue(cfg.get("trial_dur_sec", 30))
            self._trigger.setCurrentText(cfg.get("trigger_type", "typing"))
            self._exo_on.setChecked(cfg.get("exo_ON", True))
            self._body_mass.setValue(cfg.get("body_mass_kg", 57))
            self._scale.setValue(cfg.get("scale_factor", 0.3))
            self._delay.setValue(cfg.get("delay_factor", 10))
            self._model_path.setText(cfg.get("model_path", ""))
            QMessageBox.information(self, "Loaded", "Configuration loaded.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load config:\n{e}")

    def _save_data(self):
        if not self._time:
            QMessageBox.warning(self, "No Data", "No data recorded yet.")
            return
        d = QFileDialog.getExistingDirectory(self, "Select Save Directory")
        if not d:
            return
        try:
            import pandas as pd
            ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
            base = f"{self._trial_name.text() or 'biotorque'}_{ts}"
            t    = np.array(self._time)

            def _save_frame(name, cols_vals):
                n = min(len(t), *(len(v) for _, v in cols_vals))
                df = pd.DataFrame(
                    {"time": t[:n], **{c: list(v)[:n] for c, v in cols_vals}}
                )
                df.to_csv(os.path.join(d, f"{base}_{name}.csv"), index=False)

            _save_frame("motor",  [("pos_L", self._pos_L),  ("pos_R", self._pos_R),
                                    ("cmd_L", self._cmd_L),  ("cmd_R", self._cmd_R)])
            _save_frame("imu",    [("P_accX", self._imu_P), ("L_accX", self._imu_L),
                                    ("R_accX", self._imu_R)])
            _save_frame("torque", [("out_L", self._out_L),  ("out_R", self._out_R),
                                    ("filt_L", self._filt_L),("filt_R", self._filt_R)])
            QMessageBox.information(self, "Saved", f"Data saved to:\n{d}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Save failed:\n{e}")

    def _reset_data(self):
        reply = QMessageBox.question(
            self, "Reset", "Clear all recorded data?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self._t_idx = 0
        for buf in (
            self._time, self._pos_L, self._pos_R, self._cmd_L, self._cmd_R,
            self._imu_P, self._imu_L, self._imu_R,
            self._out_L, self._out_R, self._filt_L, self._filt_R,
            self._loop_ms, self._infer_ms,
        ):
            buf.clear()
        for curve in (
            self._pos_L_plot, self._pos_R_plot, self._cmd_L_plot, self._cmd_R_plot,
            self._imu_P_plot, self._imu_L_plot, self._imu_R_plot,
            self._model_L_plot, self._model_R_plot,
            self._filt_L_plot, self._filt_R_plot,
            self._loop_plot, self._infer_plot,
        ):
            curve.setData([], [])
        for w in (
            self._pos_widget, self._cmd_widget, self._imu_widget,
            self._model_widget, self._filt_widget, self._perf_widget,
        ):
            w.setXRange(0, self.TIME_WINDOW)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def shutdown(self):
        if self._controller_proc and self._controller_proc.poll() is None:
            self._stop_controller()
        self._receiver.stop()
        self._timer.stop()