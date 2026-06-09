# Service de détection automatique des robots Marty sur le réseau local

from PyQt6.QtCore import QThread, pyqtSignal
from botata_client.models.robot import RobotInfo
from botata_client.utils.logger import log


class DiscoveryWorker(QThread):
    robot_found = pyqtSignal(object)
    scan_finished = pyqtSignal(list)
    scan_error = pyqtSignal(str)

    def __init__(self, timeout: float = 2.0):
        super().__init__()
        self.timeout = timeout

    def run(self):
        found_robots: list[RobotInfo] = []
        self._discover_marty(found_robots)
        self.scan_finished.emit(found_robots)

    def _discover_marty(self, found_robots: list[RobotInfo]) -> None:
        try:
            import martypy

            discovered = []
            if hasattr(martypy, "discover"):
                try:
                    discovered = martypy.discover(timeout=int(self.timeout))
                except TypeError:
                    discovered = martypy.discover()
            elif hasattr(martypy, "ClientMV1"):
                discovered = martypy.ClientMV1._discover(timeout=int(self.timeout))
            elif hasattr(martypy, "SocketClient"):
                discovered = martypy.SocketClient.discover(timeout=int(self.timeout))
            else:
                self.scan_error.emit(
                    "Découverte réseau non supportée par cette version de martypy."
                )
                return

            for item in discovered or []:
                ip = item.split(" - ", 1)[0].strip() if isinstance(item, str) else str(item).strip()
                self._add_robot(RobotInfo(ip=ip, name="Marty Robot", is_marty=True), found_robots)
        except ImportError:
            self.scan_error.emit("martypy non installé. Installez martypy pour activer le scan.")
        except Exception as error:
            self.scan_error.emit(f"Erreur recherche Marty : {error}")

    def _add_robot(self, robot: RobotInfo, found_robots: list[RobotInfo]) -> None:
        if robot not in found_robots:
            found_robots.append(robot)
            self.robot_found.emit(robot)
