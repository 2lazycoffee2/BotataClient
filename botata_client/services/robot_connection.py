import queue
import time
from typing import Any
from PyQt6.QtCore import QObject, pyqtSignal, QThread
from botata_client.models.robot import ConnectionState
from botata_client.utils.config import AppConfig
from botata_client.utils.logger import log


class _Worker(QThread):
    data = pyqtSignal(dict)
    connected = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, ip: str, timeout: float = 3.0):
        super().__init__()
        self.ip = ip
        self.timeout = timeout
        self._stop = False
        self._command_queue: queue.Queue[tuple[str, dict[str, Any]]] = queue.Queue()
        self._client: Any | None = None

    def run(self):
        try:
            import martypy
            m = martypy.Marty("wifi", self.ip)
            self._client = m
            if hasattr(m, "hello"):
                m.hello()
            self.connected.emit(self.ip)

            last_poll = 0.0
            while not self._stop:
                now = time.time()
                if now - last_poll >= 2.0:
                    self.data.emit(self._collect_telemetry(m))
                    last_poll = now
                self._drain_commands(m)
                time.sleep(0.1)

            self._close_client()
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self._client = None

    def stop(self):
        self._stop = True

    def enqueue_command(self, command: str, params: dict[str, Any] | None = None) -> None:
        self._command_queue.put((command, params or {}))

    def _drain_commands(self, m: Any) -> None:
        while not self._command_queue.empty():
            try:
                command, params = self._command_queue.get_nowait()
                self._execute_command(m, command, params)
            except queue.Empty:
                break

    def _execute_command(self, m: Any, command: str, params: dict[str, Any]) -> None:
        cmd = command.lower()
        if cmd == "stop" and hasattr(m, "stop"):
            m.stop()
        elif cmd == "move" and hasattr(m, "walk"):
            m.walk(num_steps=int(params.get("steps", 1)), speed=int(params.get("speed", 50)))
        elif cmd == "disco_color" and hasattr(m, "disco_color"):
            m.disco_color()
        elif cmd == "disco_color_eyepicker" and hasattr(m, "disco_color_eyepicker"):
            m.disco_color_eyepicker()

    def _collect_telemetry(self, m: Any) -> dict[str, Any]:
        battery_level = int(_safe(m, "get_battery_remaining", 0))
        battery_voltage = float(_safe(m, "get_battery_voltage", 0.0))
        color = str(_safe(m, "get_color_sensor_color", "unknown"))
        color_hex = str(_safe(m, "get_color_sensor_hex", "#000000"))
        color_rgb = _safe(m, "get_color_sensor_value_by_channel", [])
        if isinstance(color_rgb, (tuple, list)):
            color_rgb = [int(x) for x in color_rgb]

        return {
            "battery_level": battery_level,
            "battery_voltage": battery_voltage,
            "color": color,
            "color_hex": color_hex,
            "color_rgb": color_rgb,
            "is_moving": bool(_safe(m, "is_moving", False)),
        }

    def _close_client(self) -> None:
        try:
            if self._client and hasattr(self._client, "close"):
                self._client.close()
        except Exception:
            pass


def _safe(obj: Any, name: str, default: Any = None, *a, **k):
    try:
        fn = getattr(obj, name)
        return fn(*a, **k)
    except Exception:
        return default


class RobotConnection(QObject):
    connection_changed = pyqtSignal(object)
    data_received = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, config: AppConfig | None = None, parent=None):
        super().__init__(parent)
        self._config = config or AppConfig()
        self._worker: _Worker | None = None
        self._state = ConnectionState.DISCONNECTED
        self._ip = ""

    @property
    def state(self) -> ConnectionState:
        return self._state

    @property
    def is_connected(self) -> bool:
        return self._state == ConnectionState.CONNECTED

    @property
    def current_ip(self) -> str:
        return self._ip

    def connect_to_robot(self, ip: str) -> None:
        self.disconnect_from_robot()
        self._ip = ip
        self._set_state(ConnectionState.CONNECTING)
        self._worker = _Worker(ip, timeout=self._config.robot.connection_timeout)
        self._worker.connected.connect(self._on_connected)
        self._worker.data.connect(self.data_received)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def disconnect_from_robot(self) -> None:
        if self._worker:
            self._worker.stop()
            self._worker.wait(500)
            self._worker = None
        self._set_state(ConnectionState.DISCONNECTED)

    def send_command(self, command: str, **params: Any) -> bool:
        if not self.is_connected or not self._worker:
            return False
        try:
            self._worker.enqueue_command(command, params)
            return True
        except Exception as e:
            self.error_occurred.emit(str(e))
            return False

    def _set_state(self, state: ConnectionState) -> None:
        self._state = state
        self.connection_changed.emit(state)

    def _on_connected(self, ip: str) -> None:
        self._set_state(ConnectionState.CONNECTED)

    def _on_error(self, message: str) -> None:
        self._set_state(ConnectionState.ERROR)
        self.error_occurred.emit(message)
