from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QListWidget, QTextEdit
from PyQt6.QtCore import pyqtSignal

from botata_client.models.robot import RobotInfo, ConnectionState
from botata_client.services.discovery import DiscoveryWorker
from botata_client.services.robot_connection import RobotConnection
from botata_client.utils.config import AppConfig


class ConnectionPanel(QWidget):
    connected = pyqtSignal(str)
    disconnected = pyqtSignal()
    judge_server_url_changed = pyqtSignal(str)

    def __init__(self, connection: RobotConnection, config: AppConfig | None = None, parent=None):
        super().__init__(parent)
        self._connection = connection
        self._config = config or AppConfig()
        self._found = []
        self._worker = None
        self._build()
        self._bind()

    def _build(self):
        l = QVBoxLayout(self)
        hl = QHBoxLayout()
        self.scan = QPushButton("Scanner")
        self.connect_btn = QPushButton("Connecter")
        self.ip = QLineEdit(self._config.robot.default_ip)
        self.server_url = QLineEdit(self._config.judge_server_url)
        self.server_url_apply = QPushButton("Appliquer")
        self.list = QListWidget()
        self.server_log = QTextEdit()
        self.server_log.setReadOnly(True)
        self.server_log.setPlaceholderText("Journal des échanges serveur arbitre...")
        self.server_log.setMinimumHeight(180)

        l.addWidget(QLabel("Connexion Marty"))
        hl.addWidget(self.scan); hl.addWidget(self.ip); hl.addWidget(self.connect_btn)
        l.addLayout(hl)
        l.addWidget(QLabel("Adresse du serveur arbitre"))
        url_layout = QHBoxLayout()
        url_layout.addWidget(self.server_url)
        url_layout.addWidget(self.server_url_apply)
        l.addLayout(url_layout)
        l.addWidget(self.list)
        l.addWidget(QLabel("Journal serveur"))
        l.addWidget(self.server_log)

    def _bind(self):
        self.scan.clicked.connect(self._on_scan)
        self.connect_btn.clicked.connect(self._on_connect_manual)
        self.server_url_apply.clicked.connect(self._on_apply_server_url)
        self._connection.connection_changed.connect(self._on_connection_changed)

    def _on_apply_server_url(self):
        url = self.server_url.text().strip()
        if not url:
            return

        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"http://{url}"

        self.server_url.setText(url)
        self._config.judge_server_url = url
        self._config.save()
        self.judge_server_url_changed.emit(url)
        self.append_server_log(f"Serveur arbitre configuré sur : {url}")

    def _on_scan(self):
        self.list.clear(); self._found.clear()
        self._worker = DiscoveryWorker()
        self._worker.robot_found.connect(self._on_found)
        self._worker.scan_finished.connect(self._on_scan_finished)
        self._worker.scan_error.connect(self._on_scan_error)
        self._worker.start()

    def _on_scan_finished(self, robots: list):
        if not robots and not self._found:
            self.list.addItem("Aucun robot trouvé.")
        self._worker = None

    def _on_scan_error(self, message: str):
        self.list.addItem(f"Erreur de scan: {message}")
        self._worker = None

    def _on_found(self, info: RobotInfo):
        self._found.append(info); self.list.addItem(f"{info.name} ({info.address})")

    def _on_connect_manual(self):
        if self._connection.is_connected:
            self._connection.disconnect_from_robot()
        else:
            ip = self.ip.text().strip() or self._config.robot.default_ip
            self._connection.connect_to_robot(ip)

    def _on_connection_changed(self, state: ConnectionState):
        if state == ConnectionState.CONNECTED:
            self.connect_btn.setText("Déconnecter")
            self.connect_btn.setStyleSheet("background-color: #d9534f; color: white; font-weight: bold;")
            self.connect_btn.setEnabled(True)
        elif state == ConnectionState.CONNECTING:
            self.connect_btn.setText("Connexion...")
            self.connect_btn.setStyleSheet("background-color: #f0ad4e; color: white;")
            self.connect_btn.setEnabled(False)
        else:
            self.connect_btn.setText("Connecter")
            self.connect_btn.setStyleSheet("background-color: #5cb85c; color: white; font-weight: bold;")
            self.connect_btn.setEnabled(True)

    def append_server_log(self, message: str) -> None:
        self.server_log.append(message)
