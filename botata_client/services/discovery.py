#Service de détection automatique des robots sur le réseau local

import socket
from PyQt6.QtCore import QThread, pyqtSignal
from botata_client.models.robot import RobotInfo
from botata_client.utils.constants import (
    DISCOVERY_PORT,
    DISCOVERY_BROADCAST_ADDR,
    DISCOVERY_TIMEOUT,
    DISCOVERY_MESSAGE,
    DISCOVERY_RESPONSE,
)


class DiscoveryWorker(QThread):
    #Thread de recherche pour ne pas geler l'interface pendant le scan réseau

    # Signaux Qt pour communiquer les résultats à l'interface graphique (UI)
    robot_found = pyqtSignal(object)   # Émis quand un robot est trouvé (RobotInfo)
    scan_finished = pyqtSignal(list)   # Émis à la fin du scan avec la liste complète
    scan_error = pyqtSignal(str)       # Émis en cas de problème technique

    def __init__(self, port: int = DISCOVERY_PORT, timeout: float = DISCOVERY_TIMEOUT):
        super().__init__()
        self.port = port
        self.timeout = timeout
        self._stop_flag = False

    def run(self):
        #Méthode principale du thread qui effectue les recherches
        found_robots = []
        self._stop_flag = False

        # détecter si le Mock Robot tourne en local
        try:
            # On tente de se connecter brièvement à localhost:port
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.2)
            result = sock.connect_ex(("127.0.0.1", self.port))
            sock.close()
            if result == 0:
                robot = RobotInfo(ip="127.0.0.1", port=self.port, name="Simulateur Botata")
                found_robots.append(robot)
                self.robot_found.emit(robot)
        except Exception:
            pass

        #Détecter Marty via la bibliothèque officielle
        try:
            import martypy
            if hasattr(martypy, 'ClientMV1'):
                discovered = martypy.ClientMV1._discover(timeout=int(self.timeout))
            elif hasattr(martypy, 'SocketClient'):
                discovered = martypy.SocketClient.discover(timeout=int(self.timeout))
            else:
                discovered = []

            for item in discovered:
                if isinstance(item, str):
                    ip = item.split(" - ")[0] if " - " in item else item
                    robot = RobotInfo(ip=ip.strip(), port=80, name="Marty Robot", is_marty=True)
                    if robot not in found_robots:
                        found_robots.append(robot)
                        self.robot_found.emit(robot)
        except ImportError:
            # martypy n'est pas installé, c'est normal pour un PoC
            pass
        except Exception as e:
            print(f"Erreur recherche Marty : {e}")

        # Broadcast UDP standard pour d'autres robots
        if not self._stop_flag:
            try:
                # Création du socket UDP avec option Broadcast
                udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                udp_sock.settimeout(self.timeout)

                # Envoi du signal de recherche à tout le monde
                udp_sock.sendto(DISCOVERY_MESSAGE, (DISCOVERY_BROADCAST_ADDR, self.port))

                # Écoute des réponses pendant le temps imparti
                while not self._stop_flag:
                    try:
                        data, addr = udp_sock.recvfrom(1024)
                        if DISCOVERY_RESPONSE in data:
                            robot = RobotInfo(
                                ip=addr[0],
                                port=self.port,
                                name="Robot Botata Réel"
                            )
                            if robot not in found_robots:
                                found_robots.append(robot)
                                self.robot_found.emit(robot)
                    except socket.timeout:
                        break
                udp_sock.close()
            except Exception as e:
                print(f"Échec du broadcast UDP : {e}")

        # Fin du scan
        self.scan_finished.emit(found_robots)

    def stop(self):
        self._stop_flag = True
