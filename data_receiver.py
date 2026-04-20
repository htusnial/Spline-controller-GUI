"""
Shared UDP data receiver for MetaMobility exoskeleton GUIs.
Both the Spline and Biotorque controllers use the same Teleplot protocol.
"""

import socket
import threading
from PyQt5.QtCore import QObject, pyqtSignal


class ExoDataReceiver(QObject):
    """
    Listens on a UDP socket for Teleplot-format packets:
        variable_name:timestamp_ms:value|g
    Emits motor_data_received(name, timestamp_sec, value) and
    connection_status(bool, message) signals.
    """

    motor_data_received = pyqtSignal(str, float, float)
    connection_status   = pyqtSignal(bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running    = False
        self._socket    = None
        self._thread    = None
        self.connected  = False

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self, host: str = "127.0.0.1", port: int = 47269) -> bool:
        """Bind and start the receive loop.  Returns True on success."""
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.bind((host, port))
            self._socket.settimeout(0.1)
            self.running = True
            self._thread = threading.Thread(
                target=self._receive_loop, daemon=True
            )
            self._thread.start()
            return True
        except Exception as exc:
            self.connection_status.emit(False, f"Failed to start listener: {exc}")
            return False

    def stop(self):
        self.running   = False
        self.connected = False
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=1.5)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _receive_loop(self):
        self.connection_status.emit(True, "Listening for exoskeleton data…")
        while self.running:
            try:
                data, addr = self._socket.recvfrom(1024)
                msg = data.decode("utf-8").strip()
                if msg.endswith("|g"):
                    msg = msg[:-2]
                    parts = msg.split(":")
                    if len(parts) == 3:
                        var_name  = parts[0]
                        timestamp = float(parts[1]) / 1000.0  # ms → s
                        value     = float(parts[2])
                        self.motor_data_received.emit(var_name, timestamp, value)
                        if not self.connected:
                            self.connected = True
                            self.connection_status.emit(
                                True, f"Receiving data from {addr[0]}:{addr[1]}"
                            )
            except socket.timeout:
                continue
            except Exception as exc:
                if self.running:
                    print(f"[ExoDataReceiver] UDP error: {exc}")
