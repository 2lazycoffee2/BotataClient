#Service simplifié de connexion au robot

import socket
import json
import time
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QThread
from botata_client.models.robot import ConnectionState
from botata_client.utils.config import AppConfig
from botata_client.utils.logger import log


class ConnectionWorker(QThread):
    #Thread secondaire qui gère la connexion réseau pour ne pas bloquer l'interface

    # Signaux pour communiquer avec le gestionnaire principal
    connected = pyqtSignal(str)
    disconnected = pyqtSignal()
    error = pyqtSignal(str)
    data_received = pyqtSignal(dict)

    def __init__(self, ip: str, port: int, use_marty: bool = False, timeout: float = 3.0):
        super().__init__()
        self.ip = ip
        self.port = port
        self.use_marty = use_marty
        self.timeout = timeout
        self._socket = None
        self._marty = None
        self._running = False

    def run(self):
        #Démarre la connexion réseau
        self._running = True

        # Tenter d'utiliser Marty si demandé
        if self.use_marty:
            self._run_marty()
        else:
            self._run_tcp_socket()

    def _run_tcp_socket(self):
        #Se connecte en TCP standard
        try:
            # Création et connexion du socket
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(self.timeout)
            self._socket.connect((self.ip, self.port))
            self._socket.settimeout(1.0)  # Timeout court pour les lectures répétées

            self.connected.emit(self.ip)
            log.info(f"Connecté en TCP à {self.ip}:{self.port}")

            # Boucle de réception des données
            buffer = ""
            while self._running:
                try:
                    data = self._socket.recv(1024)
                    if not data:
                        break  # Déconnexion propre du serveur

                    buffer += data.decode("utf-8", errors="ignore")
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if line:
                            # Décodage du message JSON de télémétrie
                            msg = json.loads(line)
                            self.data_received.emit(msg)
                except socket.timeout:
                    continue  # C'est normal on réessaye
                except Exception:
                    break

        except Exception as e:
            self.error.emit(str(e))
        finally:
            self._cleanup()
            self.disconnected.emit()

    def _run_marty(self):
        #Se connecte à Marty Robot
        try:
            import martypy
            log.info(f"Connexion Marty WiFi à {self.ip}...")
            self._marty = martypy.Marty("wifi", self.ip)
            self._marty.hello()
            self.connected.emit(self.ip)

            # Boucle d'envoi périodique de télémétrie mockée de base
            while self._running:
                battery = self._marty.get_battery_remaining()
                state = {
                    "battery_level": int(battery) if battery is not None else 100,
                    "detected_color_name": "aucune",
                    "current_color": [0, 0, 0],
                    "is_moving": self._marty.is_moving()
                }
                self.data_received.emit(state)
                time.sleep(2.0)
        except Exception as e:
            self.error.emit(f"Erreur Marty: {e}")
        finally:
            self._cleanup()
            self.disconnected.emit()

    def send(self, data: dict) -> bool:
        #Envoie une commande au robot
        # Cas Marty
        if self._marty:
            try:
                cmd = data.get("command")
                if cmd == "stop":
                    self._marty.stop()
                elif cmd == "move":
                    direction = data.get("direction", "forward")
                    speed = int(data.get("speed", 50))
                    if direction == "forward":
                        self._marty.walk(num_steps=1, speed=speed)
                    elif direction == "backward":
                        self._marty.walk(num_steps=1, step_length=-40, speed=speed)
                return True
            except Exception as e:
                log.error(f"Erreur d'envoi Marty : {e}")
                return False

        # Cas TCP standard
        if not self._socket:
            return False
        try:
            msg = json.dumps(data) + "\n"
            self._socket.sendall(msg.encode("utf-8"))
            return True
        except Exception as e:
            log.error(f"Erreur d'envoi TCP : {e}")
            return False

    def _cleanup(self):
        #Ferme tous les flux réseau
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None

        if self._marty:
            try:
                self._marty.close()
            except Exception:
                pass
            self._marty = None

    def stop(self):
        #Demande l'arrêt de la boucle de réception
        self._running = False
        self._cleanup()


class RobotConnection(QObject):
    #connexion avec le robot et gère les reconnexions

    # Signaux Qt pour notifier l'interface principale
    connection_changed = pyqtSignal(object)  # Émet un ConnectionState
    data_received = pyqtSignal(dict)         # Émet la télémétrie reçue
    error_occurred = pyqtSignal(str)         # Émet le texte de l'erreur

    def __init__(self, config: AppConfig | None = None, parent=None):
        super().__init__(parent)
        self._config = config or AppConfig()
        self._worker = None
        self._state = ConnectionState.DISCONNECTED
        self._current_ip = ""
        self._current_port = 0
        self._use_marty = False

        # Timer simple pour la reconnexion automatique
        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.timeout.connect(self._attempt_reconnect)
        self._auto_reconnect = False

    @property
    def state(self) -> ConnectionState:
        return self._state

    @property
    def is_connected(self) -> bool:
        return self._state == ConnectionState.CONNECTED

    def connect_to_robot(self, ip: str, port: int | None = None, use_marty: bool = False):
        #Initialise et lance le thread de connexion réseau
        self.disconnect_from_robot()

        self._current_ip = ip
        self._current_port = port or self._config.robot.default_port
        self._use_marty = use_marty
        self._auto_reconnect = True

        self._set_state(ConnectionState.CONNECTING)

        # Création et démarrage du thread secondaire
        self._worker = ConnectionWorker(
            ip=self._current_ip,
            port=self._current_port,
            use_marty=self._use_marty,
            timeout=self._config.robot.connection_timeout
        )
        self._worker.connected.connect(self._on_connected)
        self._worker.disconnected.connect(self._on_disconnected)
        self._worker.error.connect(self._on_error)
        self._worker.data_received.connect(self.data_received)
        self._worker.start()

    def disconnect_from_robot(self):
        #Arrête la connexion et désactive les tentatives automatiques
        self._auto_reconnect = False
        self._reconnect_timer.stop()

        if self._worker:
            self._worker.stop()
            self._worker.wait(1000)  # Attend la fin du thread
            self._worker = None

        self._set_state(ConnectionState.DISCONNECTED)

    def send_command(self, command: str, **params) -> bool:
        #Envoie une commande JSON au robot
        if not self.is_connected or not self._worker:
            return False
        data = {"command": command, **params}
        return self._worker.send(data)

    def _set_state(self, state: ConnectionState):
        #Met à jour l'état de connexion et prévient l'interface
        self._state = state
        self.connection_changed.emit(state)

    def _on_connected(self, ip: str):
        self._reconnect_timer.stop()
        self._set_state(ConnectionState.CONNECTED)

    def _on_disconnected(self):
        if self._state == ConnectionState.CONNECTED:
            self._set_state(ConnectionState.DISCONNECTED)

        # Si la connexion a été coupée anormalement, on tente de se reconnecter
        if self._auto_reconnect:
            self._reconnect_timer.start(int(self._config.robot.reconnect_delay * 1000))

    def _on_error(self, message: str):
        self._set_state(ConnectionState.ERROR)
        self.error_occurred.emit(message)

        if self._auto_reconnect:
            self._reconnect_timer.start(int(self._config.robot.reconnect_delay * 1000))

    def _attempt_reconnect(self):
        #Déclenché par le timer pour retenter de joindre le robot
        self._reconnect_timer.stop()
        if self._current_ip:
            log.info("Tentative de reconnexion automatique...")
            self.connect_to_robot(self._current_ip, self._current_port, use_marty=self._use_marty)
