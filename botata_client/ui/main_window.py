from PyQt6.QtWidgets import QMainWindow, QStatusBar, QLabel
from PyQt6.QtCore import Qt

from botata_client.services.robot_connection import RobotConnection
from botata_client.ui.connection_panel import ConnectionPanel
from botata_client.utils.config import AppConfig


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig | None = None, parent=None):
        super().__init__(parent)
        self._config = config or AppConfig()
        self.setWindowTitle("Botata Client")
        self.resize(self._config.window_width, self._config.window_height)

        self.robot_connection = RobotConnection(self._config, parent=self)
        self.connection_panel = ConnectionPanel(self.robot_connection, config=self._config)
        self.setCentralWidget(self.connection_panel)

        sb = QStatusBar(); self.setStatusBar(sb)
        self.status_connection = QLabel("Déconnecté"); sb.addWidget(self.status_connection)

        self.robot_connection.connection_changed.connect(self._on_connection_state_changed)

    def _on_connection_state_changed(self, state):
        text = "Connecté" if state.name == "CONNECTED" else ("Connexion..." if state.name == "CONNECTING" else "Déconnecté")
        self.status_connection.setText(text)
