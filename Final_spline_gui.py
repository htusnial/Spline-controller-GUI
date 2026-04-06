
import sys
import numpy as np
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import pyqtgraph as pg
from scipy.interpolate import CubicHermiteSpline
import time
from collections import deque
import socket
import threading
import subprocess
import os
 
# Configure pyqtgraph to use white background
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')

class ExoskeltonDataReceiver(QObject):
    motor_data_received = pyqtSignal(str, float, float)
    connection_status = pyqtSignal(bool, str)
    
    def __init__(self):
        super().__init__()
        self.running = False
        self.udp_socket = None
        self.udp_thread = None
        self.connected = False
        
    def start_teleplot_listener(self, host='127.0.0.1', port=47269):
        try:
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.bind((host, port))
            self.udp_socket.settimeout(0.1)
            self.running = True
            self.udp_thread = threading.Thread(target=self._udp_receive_loop)
            self.udp_thread.start()
            return True
        except Exception as e:
            print(f"Failed to start UDP listener: {e}")
            self.connection_status.emit(False, f"Failed to start listener: {e}")
            return False
    
    def _udp_receive_loop(self):
        print("Listening for Teleplot data...")
        self.connection_status.emit(True, "Listening for exoskeleton data...")
        while self.running:
            try:
                data, addr = self.udp_socket.recvfrom(1024)
                msg = data.decode('utf-8').strip()
                if msg.endswith('|g'):
                    msg = msg[:-2]
                    parts = msg.split(':')
                    if len(parts) == 3:
                        var_name = parts[0]
                        timestamp = float(parts[1]) / 1000.0
                        value = float(parts[2])
                        self.motor_data_received.emit(var_name, timestamp, value)
                        if not self.connected:
                            self.connected = True
                            self.connection_status.emit(True, f"Receiving data from {addr}")
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"UDP receive error: {e}")
                
    def stop(self):
        self.running = False
        if self.udp_socket:
            try:
                self.udp_socket.close()
            except:
                pass
        if self.udp_thread:
            self.udp_thread.join(timeout=1.0)

class GaitPhaseGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gait Phase Controller Interface")
        self.setGeometry(100, 100, 1600, 900)
        
        self.time_window = 10
        self.sample_rate = 100
        self.max_samples = self.time_window * self.sample_rate
        
        self.time_index = 0
        self.time_data = deque(maxlen=self.max_samples)
        self.gait_phase_L = deque(maxlen=self.max_samples)
        self.gait_phase_R = deque(maxlen=self.max_samples)
        self.motor_pos_L = deque(maxlen=self.max_samples)
        self.motor_pos_R = deque(maxlen=self.max_samples)
        self.motor_vel_L = deque(maxlen=self.max_samples)
        self.motor_vel_R = deque(maxlen=self.max_samples)
        self.motor_cmd_L = deque(maxlen=self.max_samples)
        self.motor_cmd_R = deque(maxlen=self.max_samples)
        
        self.latest_gait_phase = 0
        self.controller_process = None
        self.controller_mode = None
        
        self.ext_start_phase = 0
        self.ext_start_torque = 0
        self.ext_max_phase = 15
        self.ext_max_torque = 5.0
        self.ext_end_phase = 30
        self.ext_end_torque = 0
        self.flex_start_phase = 40
        self.flex_start_torque = 0
        self.flex_max_phase = 65
        self.flex_max_torque = -5.0
        self.flex_end_phase = 85
        self.flex_end_torque = 0
        
        self.update_spline()
        
        self.data_receiver = ExoskeltonDataReceiver()
        self.data_receiver.motor_data_received.connect(self.handle_motor_data)
        self.data_receiver.connection_status.connect(self.handle_connection_status)
        
        self.setup_ui()
        
        self.plot_timer = QTimer()
        self.plot_timer.timeout.connect(self.update_plots)
        self.plot_timer.start(50)
        
        self.start_time = time.time()
        self.connected = False
        
        self.data_receiver.start_teleplot_listener()
        
    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        self.create_toolbar()
        
        self.status_label = QLabel("Waiting for data...")
        self.statusBar().addWidget(self.status_label)
        
        pg.setConfigOptions(antialias=True)
        
        # 1. Gait Phase Plot
        self.gait_phase_widget = pg.PlotWidget(title="Gait Phase Estimation")
        self.gait_phase_widget.setLabel('left', 'Gait Phase (%)')
        self.gait_phase_widget.setLabel('bottom', 'Time (s)')
        self.gait_phase_widget.setYRange(0, 100)
        self.gait_phase_widget.setXRange(0, self.time_window)
        self.gait_phase_widget.getPlotItem().getAxis('bottom').setPen('k')
        self.gait_phase_widget.getPlotItem().getAxis('left').setPen('k')
        self.gait_phase_plot = self.gait_phase_widget.plot(pen=pg.mkPen('b', width=3))
        self.gait_phase_widget.showGrid(x=True, y=True, alpha=0.3)
        main_layout.addWidget(self.gait_phase_widget)
        
        # 2. Spline Profile Plot with Controls
        spline_container = QWidget()
        spline_layout = QHBoxLayout(spline_container)
        spline_layout.setContentsMargins(0, 0, 0, 0)
        
        self.spline_widget = pg.PlotWidget(title="Torque Spline Profile")
        self.spline_widget.setLabel('left', 'Torque (Nm)')
        self.spline_widget.setLabel('bottom', 'Gait Phase (%)')
        self.spline_widget.setXRange(0, 100)
        self.spline_widget.setYRange(-8, 8)
        self.spline_widget.getPlotItem().getAxis('bottom').setPen('k')
        self.spline_widget.getPlotItem().getAxis('left').setPen('k')
        self.spline_curve = self.spline_widget.plot(pen='g', width=2)
        self.spline_points = self.spline_widget.plot(pen=None, symbol='o', symbolSize=10,
                                                     symbolBrush='r', symbolPen='r')
        self.phase_indicator = self.spline_widget.addLine(x=0, pen=pg.mkPen('y', width=2))
        
        control_panel = QGroupBox("Spline Control Points")
        control_layout = QGridLayout()
        control_layout.addWidget(QLabel("<b>Control Point</b>"), 0, 0)
        control_layout.addWidget(QLabel("<b>Phase (%)</b>"), 0, 1)
        control_layout.addWidget(QLabel("<b>Torque (Nm)</b>"), 0, 2)
        
        row = 1
        control_layout.addWidget(QLabel("Extension Start"), row, 0)
        self.ext_start_phase_input = QLineEdit(str(self.ext_start_phase))
        self.ext_start_phase_input.setMaximumWidth(60)
        self.ext_start_phase_input.textChanged.connect(self.update_spline_from_inputs)
        control_layout.addWidget(self.ext_start_phase_input, row, 1)
        self.ext_start_torque_input = QLineEdit(str(self.ext_start_torque))
        self.ext_start_torque_input.setMaximumWidth(60)
        self.ext_start_torque_input.textChanged.connect(self.update_spline_from_inputs)
        control_layout.addWidget(self.ext_start_torque_input, row, 2)
        row += 1
        
        control_layout.addWidget(QLabel("<b>Extension Max</b>"), row, 0)
        self.ext_max_phase_input = QLineEdit(str(self.ext_max_phase))
        self.ext_max_phase_input.setMaximumWidth(60)
        self.ext_max_phase_input.textChanged.connect(self.update_spline_from_inputs)
        control_layout.addWidget(self.ext_max_phase_input, row, 1)
        self.ext_max_torque_input = QLineEdit(str(self.ext_max_torque))
        self.ext_max_torque_input.setMaximumWidth(60)
        self.ext_max_torque_input.textChanged.connect(self.update_spline_from_inputs)
        control_layout.addWidget(self.ext_max_torque_input, row, 2)
        row += 1
        
        control_layout.addWidget(QLabel("Extension End"), row, 0)
        self.ext_end_phase_input = QLineEdit(str(self.ext_end_phase))
        self.ext_end_phase_input.setMaximumWidth(60)
        self.ext_end_phase_input.textChanged.connect(self.update_spline_from_inputs)
        control_layout.addWidget(self.ext_end_phase_input, row, 1)
        self.ext_end_torque_input = QLineEdit(str(self.ext_end_torque))
        self.ext_end_torque_input.setMaximumWidth(60)
        self.ext_end_torque_input.textChanged.connect(self.update_spline_from_inputs)
        control_layout.addWidget(self.ext_end_torque_input, row, 2)
        row += 1
        
        control_layout.addWidget(QLabel("Flexion Start"), row, 0)
        self.flex_start_phase_input = QLineEdit(str(self.flex_start_phase))
        self.flex_start_phase_input.setMaximumWidth(60)
        self.flex_start_phase_input.textChanged.connect(self.update_spline_from_inputs)
        control_layout.addWidget(self.flex_start_phase_input, row, 1)
        self.flex_start_torque_input = QLineEdit(str(self.flex_start_torque))
        self.flex_start_torque_input.setMaximumWidth(60)
        self.flex_start_torque_input.textChanged.connect(self.update_spline_from_inputs)
        control_layout.addWidget(self.flex_start_torque_input, row, 2)
        row += 1
        
        control_layout.addWidget(QLabel("<b>Flexion Max</b>"), row, 0)
        self.flex_max_phase_input = QLineEdit(str(self.flex_max_phase))
        self.flex_max_phase_input.setMaximumWidth(60)
        self.flex_max_phase_input.textChanged.connect(self.update_spline_from_inputs)
        control_layout.addWidget(self.flex_max_phase_input, row, 1)
        self.flex_max_torque_input = QLineEdit(str(self.flex_max_torque))
        self.flex_max_torque_input.setMaximumWidth(60)
        self.flex_max_torque_input.textChanged.connect(self.update_spline_from_inputs)
        control_layout.addWidget(self.flex_max_torque_input, row, 2)
        row += 1
        
        control_layout.addWidget(QLabel("Flexion End"), row, 0)
        self.flex_end_phase_input = QLineEdit(str(self.flex_end_phase))
        self.flex_end_phase_input.setMaximumWidth(60)
        self.flex_end_phase_input.textChanged.connect(self.update_spline_from_inputs)
        control_layout.addWidget(self.flex_end_phase_input, row, 1)
        self.flex_end_torque_input = QLineEdit(str(self.flex_end_torque))
        self.flex_end_torque_input.setMaximumWidth(60)
        self.flex_end_torque_input.textChanged.connect(self.update_spline_from_inputs)
        control_layout.addWidget(self.flex_end_torque_input, row, 2)
        
        control_panel.setLayout(control_layout)
        control_panel.setMaximumWidth(400)
        control_panel.setMinimumWidth(380)
        self.spline_widget.setMaximumWidth(800)
        spline_layout.addWidget(self.spline_widget, stretch=2)
        spline_layout.addWidget(control_panel, stretch=3)
        main_layout.addWidget(spline_container)
        
        # 3. Data Plot with dropdown selector
        self.data_plot_widget = pg.PlotWidget()
        self.data_plot_widget.setLabel('left', 'Value')
        self.data_plot_widget.setLabel('bottom', 'Time (s)')
        self.data_plot_widget.setXRange(0, self.time_window)
        self.data_plot_widget.addLegend()
        self.data_plot_widget.getPlotItem().getAxis('bottom').setPen('k')
        self.data_plot_widget.getPlotItem().getAxis('left').setPen('k')
        
        self.plot_selector = QComboBox()
        self.plot_selector.addItems([
            "Motor Position (L/R)",
            "Motor Velocity (L/R)",
            "Motor Commands (L/R)",
            "Gait Phase (L/R)"
        ])
        self.plot_selector.currentIndexChanged.connect(self.update_data_plot)
        
        self.data_plot1 = self.data_plot_widget.plot(pen='b', width=2, name='Left')
        self.data_plot2 = self.data_plot_widget.plot(pen='r', width=2, name='Right')
        
        plot_selector_layout = QHBoxLayout()
        plot_selector_layout.addWidget(QLabel("Display:"))
        plot_selector_layout.addWidget(self.plot_selector)
        plot_selector_layout.addStretch()
        
        main_layout.addLayout(plot_selector_layout)
        main_layout.addWidget(self.data_plot_widget)
        
        self.update_spline_plot()
        
    def create_toolbar(self):
        toolbar = self.addToolBar('Main')
        toolbar.addWidget(QLabel(" Controller: "))
        self.controller_mode_selector = QComboBox()
        self.controller_mode_selector.addItems(['TBE Controller', 'CNN Controller'])
        toolbar.addWidget(self.controller_mode_selector)
        
        self.controller_button = QPushButton('Start Controller')
        self.controller_button.setStyleSheet("""
            QPushButton { background-color: #4CAF50; color: white; font-weight: bold;
                          padding: 5px 15px; border-radius: 3px; }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:pressed { background-color: #3d8b40; }
        """)
        self.controller_button.clicked.connect(self.toggle_controller)
        toolbar.addWidget(self.controller_button)
        toolbar.addSeparator()
        
        reset_action = QAction('Reset Data', self)
        reset_action.triggered.connect(self.reset_data)
        toolbar.addAction(reset_action)
        toolbar.addSeparator()
        
        toolbar.addWidget(QLabel(" Display: "))
        self.display_mode = QComboBox()
        self.display_mode.addItems(['Left Leg', 'Right Leg'])
        toolbar.addWidget(self.display_mode)
        
    def toggle_controller(self):
        if self.controller_process is None or self.controller_process.poll() is not None:
            self.start_controller()
        else:
            self.stop_controller()
    
    def start_controller(self):
        mode = self.controller_mode_selector.currentText()
        base_path = '/home/kaustubh-meta/hip_exo/Ryan_Hridayam'
        script_name = 'run_exo_exp_TBE.py' if mode == 'TBE Controller' else 'spline_controller.py'
        script_path = os.path.join(base_path, script_name)
        
        if not os.path.exists(script_path):
            QMessageBox.warning(self, "Script Not Found", f"Controller script not found at:\n{script_path}")
            return
        
        try:
            self.controller_process = subprocess.Popen(
                [sys.executable, script_name], cwd=base_path,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                universal_newlines=True, bufsize=1, env=os.environ.copy()
            )
            self.controller_button.setText('Stop Controller')
            self.controller_button.setStyleSheet("""
                QPushButton { background-color: #f44336; color: white; font-weight: bold;
                              padding: 5px 15px; border-radius: 3px; }
                QPushButton:hover { background-color: #da190b; }
                QPushButton:pressed { background-color: #c01005; }
            """)
            self.controller_mode = mode
            self.status_label.setText(f"Started {mode} - Listening for data...")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            self.monitor_thread = threading.Thread(target=self.monitor_controller_output)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start controller: {str(e)}")
    
    def stop_controller(self):
        if self.controller_process:
            try:
                self.controller_process.terminate()
                try:
                    self.controller_process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.controller_process.kill()
                    self.controller_process.wait()
                self.controller_process = None
                self.controller_button.setText('Start Controller')
                self.controller_button.setStyleSheet("""
                    QPushButton { background-color: #4CAF50; color: white; font-weight: bold;
                                  padding: 5px 15px; border-radius: 3px; }
                    QPushButton:hover { background-color: #45a049; }
                    QPushButton:pressed { background-color: #3d8b40; }
                """)
                self.status_label.setText(f"Stopped {self.controller_mode}")
                self.status_label.setStyleSheet("color: orange; font-weight: bold;")
                self.controller_mode = None
            except Exception as e:
                QMessageBox.warning(self, "Warning", f"Error stopping controller: {str(e)}")
    
    def monitor_controller_output(self):
        if not self.controller_process:
            return
        try:
            while True:
                line = self.controller_process.stdout.readline()
                if not line:
                    break
                line = line.strip()
                if line:
                    print(f"[Controller]: {line}")
            self.controller_process.wait()
            QTimer.singleShot(0, self.controller_stopped_callback)
        except Exception as e:
            print(f"Monitor thread error: {e}")
    
    def controller_stopped_callback(self):
        if self.controller_process and self.controller_process.poll() is not None:
            return_code = self.controller_process.returncode
            self.controller_process = None
            self.controller_button.setText('Start Controller')
            self.controller_button.setStyleSheet("""
                QPushButton { background-color: #4CAF50; color: white; font-weight: bold;
                              padding: 5px 15px; border-radius: 3px; }
                QPushButton:hover { background-color: #45a049; }
                QPushButton:pressed { background-color: #3d8b40; }
            """)
            if return_code != 0:
                self.status_label.setText(f"{self.controller_mode} stopped with error (code: {return_code})")
                self.status_label.setStyleSheet("color: red; font-weight: bold;")
            else:
                self.status_label.setText(f"{self.controller_mode} stopped")
                self.status_label.setStyleSheet("color: orange; font-weight: bold;")
            self.controller_mode = None

    def update_spline_from_inputs(self):
        try:
            self.ext_start_phase = float(self.ext_start_phase_input.text() or 0)
            self.ext_start_torque = float(self.ext_start_torque_input.text() or 0)
            self.ext_max_phase = float(self.ext_max_phase_input.text() or 15)
            self.ext_max_torque = float(self.ext_max_torque_input.text() or 5)
            self.ext_end_phase = float(self.ext_end_phase_input.text() or 30)
            self.ext_end_torque = float(self.ext_end_torque_input.text() or 0)
            self.flex_start_phase = float(self.flex_start_phase_input.text() or 40)
            self.flex_start_torque = float(self.flex_start_torque_input.text() or 0)
            self.flex_max_phase = float(self.flex_max_phase_input.text() or 65)
            self.flex_max_torque = float(self.flex_max_torque_input.text() or -5)
            self.flex_end_phase = float(self.flex_end_phase_input.text() or 85)
            self.flex_end_torque = float(self.flex_end_torque_input.text() or 0)
            self.update_spline()
            self.update_spline_plot()
        except ValueError:
            pass
            
    def update_spline(self):
        self.spline_x = np.array([
            self.ext_start_phase, self.ext_max_phase, self.ext_end_phase,
            self.flex_start_phase, self.flex_max_phase, self.flex_end_phase, 100
        ])
        self.spline_y = np.array([
            self.ext_start_torque, self.ext_max_torque, self.ext_end_torque,
            self.flex_start_torque, self.flex_max_torque, self.flex_end_torque,
            self.ext_start_torque
        ])
        sort_indices = np.argsort(self.spline_x)
        self.spline_x = self.spline_x[sort_indices]
        self.spline_y = self.spline_y[sort_indices]
        self.spline_dydx = np.zeros_like(self.spline_y)
        try:
            self.spline_controller = CubicHermiteSpline(
                self.spline_x, self.spline_y, self.spline_dydx, extrapolate='periodic'
            )
        except Exception as e:
            print(f"Spline creation error: {e}")
            self.spline_controller = None
        
    def update_spline_plot(self):
        if self.spline_controller is not None:
            x_smooth = np.linspace(0, 100, 500)
            try:
                y_smooth = self.spline_controller(x_smooth)
                self.spline_curve.setData(x_smooth, y_smooth)
            except:
                self.spline_curve.setData([0, 100], [0, 0])
        control_x = self.spline_x[:-1]
        control_y = self.spline_y[:-1]
        self.spline_points.setData(control_x, control_y)
        
    def handle_motor_data(self, var_name, timestamp, value):
        current_time = self.time_index / self.sample_rate
        if var_name == 'mtr_pos_L':
            self.motor_pos_L.append(value)
            self.time_data.append(current_time)
            self.time_index += 1
        elif var_name == 'mtr_pos_R':
            self.motor_pos_R.append(value)
        elif var_name == 'mtr_vel_L':
            self.motor_vel_L.append(value)
        elif var_name == 'mtr_vel_R':
            self.motor_vel_R.append(value)
        elif var_name in ('mtr_cmd_L', 'cmd_L'):
            self.motor_cmd_L.append(value)
        elif var_name in ('mtr_cmd_R', 'cmd_R'):
            self.motor_cmd_R.append(value)
        elif var_name in ('gait_pct_L', 'phase_L_%'):
            self.gait_phase_L.append(value)
            if self.display_mode.currentText() == 'Left Leg':
                self.latest_gait_phase = value
        elif var_name in ('gait_pct_R', 'phase_R_%'):
            self.gait_phase_R.append(value)
            if self.display_mode.currentText() == 'Right Leg':
                self.latest_gait_phase = value
                
    def handle_connection_status(self, connected, message):
        self.connected = connected
        style = "color: green; font-weight: bold;" if connected else "color: red; font-weight: bold;"
        self.status_label.setText(message)
        self.status_label.setStyleSheet(style)
    
    def update_data_plot(self):
        """Update the data plot based on dropdown selection"""
        selection = self.plot_selector.currentIndex()

        if len(self.time_data) > 0:
            time_array = np.array(self.time_data)
        else:
            time_array = np.array([])

        # Clear and recreate legend
        self.data_plot_widget.clear()
        self.data_plot_widget.addLegend()

        # ── KEY FIX: re-enable y auto-range so axis rescales to the new data type ──
        self.data_plot_widget.enableAutoRange(axis='y', enable=True)

        # Recreate plot items
        self.data_plot1 = self.data_plot_widget.plot(pen=pg.mkPen('b', width=2))
        self.data_plot2 = self.data_plot_widget.plot(pen=pg.mkPen('r', width=2))

        if selection == 0:  # Motor Position (L/R)
            self.data_plot_widget.setTitle("Motor Position (L/R)")
            self.data_plot_widget.setLabel('left', 'Position (deg)')
            if len(self.motor_pos_L) > 0:
                min_len = min(len(time_array), len(self.motor_pos_L))
                if min_len > 0:
                    pos_L_deg = np.array(list(self.motor_pos_L)[-min_len:]) * 180.0 / np.pi
                    self.data_plot1.setData(time_array[-min_len:], -pos_L_deg, name='Left')
            if len(self.motor_pos_R) > 0:
                min_len = min(len(time_array), len(self.motor_pos_R))
                if min_len > 0:
                    pos_R_deg = np.array(list(self.motor_pos_R)[-min_len:]) * 180.0 / np.pi
                    self.data_plot2.setData(time_array[-min_len:], pos_R_deg, name='Right')

        elif selection == 1:  # Motor Velocity (L/R)
            self.data_plot_widget.setTitle("Motor Velocity (L/R)")
            self.data_plot_widget.setLabel('left', 'Velocity (deg/s)')
            if len(self.motor_vel_L) > 0:
                min_len = min(len(time_array), len(self.motor_vel_L))
                if min_len > 0:
                    vel_L_deg = np.array(list(self.motor_vel_L)[-min_len:]) * 180.0 / np.pi
                    self.data_plot1.setData(time_array[-min_len:], -vel_L_deg, name='Left Vel')
            if len(self.motor_vel_R) > 0:
                min_len = min(len(time_array), len(self.motor_vel_R))
                if min_len > 0:
                    vel_R_deg = np.array(list(self.motor_vel_R)[-min_len:]) * 180.0 / np.pi
                    self.data_plot2.setData(time_array[-min_len:], vel_R_deg, name='Right Vel')

        elif selection == 2:  # Motor Commands (L/R)
            self.data_plot_widget.setTitle("Motor Commands (L/R)")
            self.data_plot_widget.setLabel('left', 'Torque (Nm)')
            if len(self.motor_cmd_L) > 0:
                min_len = min(len(time_array), len(self.motor_cmd_L))
                if min_len > 0:
                    self.data_plot1.setData(time_array[-min_len:], list(self.motor_cmd_L)[-min_len:], name='Left Cmd')
            if len(self.motor_cmd_R) > 0:
                min_len = min(len(time_array), len(self.motor_cmd_R))
                if min_len > 0:
                    self.data_plot2.setData(time_array[-min_len:], list(self.motor_cmd_R)[-min_len:], name='Right Cmd')

        elif selection == 3:  # Gait Phase (L/R)
            self.data_plot_widget.setTitle("Gait Phase (L/R)")
            self.data_plot_widget.setLabel('left', 'Gait Phase (%)')
            if len(self.gait_phase_L) > 0:
                min_len = min(len(time_array), len(self.gait_phase_L))
                if min_len > 0:
                    self.data_plot1.setData(time_array[-min_len:], list(self.gait_phase_L)[-min_len:], name='Left')
            if len(self.gait_phase_R) > 0:
                min_len = min(len(time_array), len(self.gait_phase_R))
                if min_len > 0:
                    self.data_plot2.setData(time_array[-min_len:], list(self.gait_phase_R)[-min_len:], name='Right')

    def update_plots(self):
        if len(self.time_data) == 0:
            return
            
        time_array = np.array(self.time_data, dtype=np.float64)
        
        if self.display_mode.currentText() == 'Left Leg' and len(self.gait_phase_L) > 0:
            gait_data = self.gait_phase_L
        elif self.display_mode.currentText() == 'Right Leg' and len(self.gait_phase_R) > 0:
            gait_data = self.gait_phase_R
        else:
            gait_data = []
            
        if len(gait_data) > 0:
            try:
                gait_array = np.array(gait_data, dtype=np.float64)
                min_len = min(len(time_array), len(gait_array))
                valid_mask = np.isfinite(time_array[:min_len]) & np.isfinite(gait_array[:min_len])
                if np.any(valid_mask):
                    self.gait_phase_plot.setData(time_array[:min_len][valid_mask], gait_array[:min_len][valid_mask])
                    self.phase_indicator.setValue(self.latest_gait_phase)
            except (ValueError, TypeError) as e:
                print(f"Error converting gait phase data: {e}")
        
        self.update_data_plot()
        
        if len(time_array) > 0:
            current_time = time_array[-1]
            if current_time < self.time_window:
                self.gait_phase_widget.setXRange(0, self.time_window)
                self.data_plot_widget.setXRange(0, self.time_window)
            else:
                self.gait_phase_widget.setXRange(current_time - self.time_window, current_time)
                self.data_plot_widget.setXRange(current_time - self.time_window, current_time)
                    
    def reset_data(self):
        self.time_index = 0
        self.time_data.clear()
        self.gait_phase_L.clear()
        self.gait_phase_R.clear()
        self.motor_pos_L.clear()
        self.motor_pos_R.clear()
        self.motor_vel_L.clear()
        self.motor_vel_R.clear()
        self.motor_cmd_L.clear()
        self.motor_cmd_R.clear()
        self.latest_gait_phase = 0
        self.gait_phase_widget.setXRange(0, self.time_window)
        self.data_plot_widget.setXRange(0, self.time_window)
        
    def closeEvent(self, event):
        if self.controller_process and self.controller_process.poll() is None:
            self.stop_controller()
        self.data_receiver.stop()
        if self.plot_timer.isActive():
            self.plot_timer.stop()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    main_window = GaitPhaseGUI()
    main_window.show()
    sys.exit(app.exec_())
