#Fenêtre principale de l'application Botata Client

from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QLabel,
    QWidget, QVBoxLayout, QMessageBox, QFileDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction

from botata_client.models.robot import ConnectionState
from botata_client.services.robot_connection import RobotConnection
from botata_client.ui.connection_panel import ConnectionPanel
from botata_client.utils.config import AppConfig
from botata_client.utils.constants import APP_NAME, APP_VERSION
from botata_client.utils.logger import log


class MainWindow(QMainWindow):

    def __init__(self, config: AppConfig | None = None, parent=None):
        super().__init__(parent)
        self._config = config or AppConfig()
        
        # Configuration basique de la fenêtre
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(1024, 680)
        self.resize(self._config.window_width, self._config.window_height)

        # Service de connexion réseau partagé par l'application
        self.robot_connection = RobotConnection(self._config, parent=self)
        
        # Connexion des signaux de télémétrie et d'état du robot
        self.robot_connection.connection_changed.connect(self._on_connection_state_changed)
        self.robot_connection.data_received.connect(self._on_data_received)

        # Construction des 3 composants graphiques principaux
        self._setup_menu_bar()
        self._setup_central_widget()
        self._setup_status_bar()

    def _setup_menu_bar(self):
        menubar = self.menuBar()

        # Menu Fichier
        file_menu = menubar.addMenu("&Fichier")
        self.action_open_dance = QAction("Ouvrir un fichier .dance...", self)
        self.action_open_dance.setShortcut("Ctrl+O")
        self.action_open_dance.triggered.connect(self._on_open_dance)
        file_menu.addAction(self.action_open_dance)
        
        file_menu.addSeparator()
        
        action_quit = QAction("Quitter", self)
        action_quit.setShortcut("Ctrl+Q")
        action_quit.triggered.connect(self.close)
        file_menu.addAction(action_quit)

        # Menu Robot
        robot_menu = menubar.addMenu("&Robot")
        
        self.action_connect = QAction("Connecter...", self)
        self.action_connect.setShortcut("Ctrl+K")
        self.action_connect.triggered.connect(lambda: self.tabs.setCurrentIndex(0))
        robot_menu.addAction(self.action_connect)
        
        self.action_disconnect = QAction("Déconnecter", self)
        self.action_disconnect.setEnabled(False)
        self.action_disconnect.triggered.connect(self.robot_connection.disconnect_from_robot)
        robot_menu.addAction(self.action_disconnect)
        
        robot_menu.addSeparator()
        
        self.action_scan = QAction("Scanner le réseau", self)
        self.action_scan.triggered.connect(self._on_menu_scan)
        robot_menu.addAction(self.action_scan)
        
        robot_menu.addSeparator()
        
        self.action_emergency_stop = QAction("STOP D'URGENCE", self)
        self.action_emergency_stop.setShortcut("Escape")
        self.action_emergency_stop.triggered.connect(self._on_emergency_stop)
        robot_menu.addAction(self.action_emergency_stop)

        # Menu Outils
        tools_menu = menubar.addMenu("&Outils")
        self.action_calibrate = QAction("Calibration couleurs...", self)
        tools_menu.addAction(self.action_calibrate)

        # Menu Aide
        help_menu = menubar.addMenu("&Aide")
        action_about = QAction("À propos", self)
        action_about.triggered.connect(self._on_about)
        help_menu.addAction(action_about)

    def _setup_central_widget(self):
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs.setDocumentMode(True)
        self.connection_panel = ConnectionPanel(
            connection=self.robot_connection,
            config=self._config,
        )
        self.tabs.addTab(self.connection_panel, "Connexion")

        placeholders = [
            ("Contrôle", "Déplacements, vitesse et expressions"),
            ("Couleurs", "Calibration couleur captée -> standard"),
            ("Danse", "Charger et exécuter un fichier .dance"),
        ]

        for title, desc in placeholders:
            widget = self._create_placeholder_tab(title, desc)
            self.tabs.addTab(widget, title)

        self.setCentralWidget(self.tabs)

    def _create_placeholder_tab(self, title: str, desc: str) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_title = QLabel(title)
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_title.setStyleSheet("font-size: 28px; font-weight: bold;")

        lbl_desc = QLabel(desc)
        lbl_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_wip = QLabel("En cours de développement...")
        lbl_wip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_wip.setStyleSheet("font-style: italic; color: #64748b;")

        layout.addWidget(lbl_title)
        layout.addSpacing(12)
        layout.addWidget(lbl_desc)
        layout.addSpacing(20)
        layout.addWidget(lbl_wip)

        return widget

    def _setup_status_bar(self):
        sb = QStatusBar()
        self.setStatusBar(sb)

        self.status_connection = QLabel("Déconnecté")
        self.status_connection.setStyleSheet("color: #64748b; padding: 0 8px;")
        sb.addWidget(self.status_connection)

        sb.addWidget(QLabel("│"))

        self.status_battery = QLabel("Batterie: ---%")
        self.status_battery.setStyleSheet("color: #64748b; padding: 0 8px;")
        sb.addWidget(self.status_battery)

        sb.addWidget(QLabel("│"))

        self.status_color = QLabel("Couleur: aucune")
        self.status_color.setStyleSheet("color: #64748b; padding: 0 8px;")
        sb.addWidget(self.status_color)

        sb.addPermanentWidget(QWidget(), 1)

        self.status_server = QLabel("Serveur: --")
        self.status_server.setStyleSheet("color: #64748b; padding: 0 8px;")
        sb.addPermanentWidget(self.status_server)

    def _on_connection_state_changed(self, state: ConnectionState):
        if state == ConnectionState.CONNECTED:
            ip = self.robot_connection._current_ip
            self.status_connection.setText(f"Connecté ({ip})")
            self.status_connection.setStyleSheet("color: green; padding: 0 8px; font-weight: bold;")
            self.action_disconnect.setEnabled(True)
            self.statusBar().showMessage(f"Connecté au robot {ip}", 3000)

        elif state == ConnectionState.CONNECTING:
            self.status_connection.setText("Connexion...")
            self.status_connection.setStyleSheet("color: orange; padding: 0 8px;")
            self.action_disconnect.setEnabled(False)

        elif state == ConnectionState.ERROR:
            self.status_connection.setText("Erreur")
            self.status_connection.setStyleSheet("color: red; padding: 0 8px; font-weight: bold;")
            self.action_disconnect.setEnabled(False)

        else:
            self.status_connection.setText("Déconnecté")
            self.status_connection.setStyleSheet("color: #64748b; padding: 0 8px;")
            self.action_disconnect.setEnabled(False)

    def _on_data_received(self, data: dict):
        # Lecture du niveau de batterie
        if "battery_level" in data:
            level = data["battery_level"]
            color = "green" if level > 50 else ("orange" if level > 20 else "red")
            self.status_battery.setText(f"Batterie: {level}%")
            self.status_battery.setStyleSheet(f"color: {color}; padding: 0 8px; font-weight: bold;")

        # Lecture de la couleur captée par la plaque
        if "detected_color_name" in data:
            color_name = data["detected_color_name"]
            rgb = data.get("current_color")
            if rgb:
                r, g, b = rgb
                self.status_color.setText(f"Couleur: {color_name}")
                self.status_color.setStyleSheet(
                    f"color: rgb({r},{g},{b}); padding: 0 8px; font-weight: bold;"
                )
            else:
                self.status_color.setText("Couleur: aucune")
                self.status_color.setStyleSheet("color: #64748b; padding: 0 8px;")

    def _on_menu_scan(self):
        self.tabs.setCurrentIndex(0)
        self.connection_panel.btn_scan.click()

    def _on_emergency_stop(self):
        if self.robot_connection.is_connected:
            self.robot_connection.send_command("stop")
            self.statusBar().showMessage("STOP D'URGENCE envoyé !", 3000)
            log.warning("STOP D'URGENCE envoyé au robot !")
        else:
            self.statusBar().showMessage("Aucun robot connecté.", 3000)

    def _on_open_dance(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Ouvrir une chorégraphie", "",
            "Fichiers Dance (*.dance);;Tous (*)",
        )
        if path:
            self.statusBar().showMessage(f"Fichier chargé : {path}", 5000)

    def _on_about(self):
        #Affiche la boîte de dialogue À propos
        QMessageBox.about(
            self, f"À propos de {APP_NAME}",
            f"<h2>{APP_NAME}</h2><p>Version {APP_VERSION}</p>"
            f"<p>© 2026 AlifBaTA</p>",
        )
