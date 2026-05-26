#Interface utilisateur

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QPushButton, QLineEdit, QListWidget,
    QListWidgetItem, QSpinBox, QProgressBar, QCheckBox,
)
from PyQt6.QtCore import Qt, pyqtSignal

from botata_client.models.robot import RobotInfo, ConnectionState
from botata_client.services.discovery import DiscoveryWorker
from botata_client.services.robot_connection import RobotConnection
from botata_client.utils.config import AppConfig


class ConnectionPanel(QWidget):
    #Panneau regroupant les fonctions de détection et de connexion

    # Signaux pour communiquer avec l'UI principale
    connected = pyqtSignal(str)
    disconnected = pyqtSignal()

    def __init__(self, connection: RobotConnection, config: AppConfig | None = None, parent=None):
        super().__init__(parent)
        self._connection = connection
        self._config = config or AppConfig()
        self._discovery_worker = None
        self._found_robots = []

        # Construction et paramétrage de l'interface
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        #Construit visuellement l'interface graphique
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(20, 20, 20, 20)

        #Titre principal du panneau
        title = QLabel("Connexion au Robot")
        title.setObjectName("label_title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = title.font()
        font.setPointSize(20)
        title.setFont(font)
        main_layout.addWidget(title)

        #Section "Recherche automatique"
        scan_group = QGroupBox("Recherche automatique")
        scan_layout = QVBoxLayout(scan_group)

        #Ligne de boutons
        btn_row = QHBoxLayout()
        self.btn_scan = QPushButton("Scanner le réseau")
        self.btn_scan.setMinimumHeight(40)
        btn_row.addWidget(self.btn_scan)

        self.btn_stop_scan = QPushButton("Arrêter")
        self.btn_stop_scan.setEnabled(False)
        self.btn_stop_scan.setMinimumHeight(40)
        btn_row.addWidget(self.btn_stop_scan)
        scan_layout.addLayout(btn_row)

        # Barre de chargement invisible par défaut
        self.scan_progress = QProgressBar()
        self.scan_progress.setRange(0, 0)  # Mode indéterminé
        self.scan_progress.setVisible(False)
        self.scan_progress.setMaximumHeight(6)
        scan_layout.addWidget(self.scan_progress)

        # Liste des robots détectés
        self.robot_list = QListWidget()
        self.robot_list.setMinimumHeight(120)
        scan_layout.addWidget(self.robot_list)

        # Bouton pour connecter le robot sélectionné
        self.btn_connect_selected = QPushButton("Connecter au robot sélectionné")
        self.btn_connect_selected.setEnabled(False)
        scan_layout.addWidget(self.btn_connect_selected)

        main_layout.addWidget(scan_group)

        # Section "Connexion manuelle"
        manual_group = QGroupBox("Connexion manuelle")
        manual_layout = QVBoxLayout(manual_group)

        # Saisie IP et Port
        ip_row = QHBoxLayout()
        ip_row.addWidget(QLabel("Adresse IP :"))
        self.input_ip = QLineEdit()
        self.input_ip.setPlaceholderText(self._config.robot.default_ip)
        ip_row.addWidget(self.input_ip, 2)

        ip_row.addWidget(QLabel("Port :"))
        self.input_port = QSpinBox()
        self.input_port.setRange(1, 65535)
        self.input_port.setValue(self._config.robot.default_port)
        ip_row.addWidget(self.input_port, 1)
        manual_layout.addLayout(ip_row)

        # Case à cocher pour Marty
        self.cb_marty_mode = QCheckBox("Robot Marty réel (WiFi)")
        manual_layout.addWidget(self.cb_marty_mode)

        # Bouton Connexion manuelle
        self.btn_connect_manual = QPushButton("Connecter")
        self.btn_connect_manual.setMinimumHeight(40)
        manual_layout.addWidget(self.btn_connect_manual)

        main_layout.addWidget(manual_group)

        # Section "État de la connexion"
        status_group = QGroupBox("État de la connexion")
        status_layout = QVBoxLayout(status_group)

        self.status_label = QLabel("Déconnecté")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = self.status_label.font()
        font.setPointSize(14)
        self.status_label.setFont(font)
        status_layout.addWidget(self.status_label)

        self.btn_disconnect = QPushButton("Déconnecter")
        self.btn_disconnect.setEnabled(False)
        self.btn_disconnect.setMinimumHeight(36)
        status_layout.addWidget(self.btn_disconnect)

        main_layout.addWidget(status_group)
        main_layout.addStretch()

    def _connect_signals(self):
        #Associe les clics de boutons aux méthodes Python correspondantes
        self.btn_scan.clicked.connect(self._on_scan)
        self.btn_stop_scan.clicked.connect(self._on_stop_scan)
        self.btn_connect_selected.clicked.connect(self._on_connect_selected)
        self.btn_connect_manual.clicked.connect(self._on_connect_manual)
        self.btn_disconnect.clicked.connect(self._on_disconnect)
        self.robot_list.currentRowChanged.connect(self._on_robot_selected)
        self.input_ip.returnPressed.connect(self._on_connect_manual)

        # Brancher les signaux provenant du service réseau RobotConnection
        self._connection.connection_changed.connect(self._on_connection_changed)

    # aCTIONS DE SCAN 

    def _on_scan(self):
        """Lance le scan réseau."""
        self.robot_list.clear()
        self._found_robots.clear()
        self.btn_scan.setEnabled(False)
        self.btn_stop_scan.setEnabled(True)
        self.scan_progress.setVisible(True)

        self._discovery_worker = DiscoveryWorker(port=self.input_port.value())
        self._discovery_worker.robot_found.connect(self._on_robot_found)
        self._discovery_worker.scan_finished.connect(self._on_scan_finished)
        self._discovery_worker.start()

    def _on_stop_scan(self):
        #Demande l'arrêt du scan
        if self._discovery_worker:
            self._discovery_worker.stop()

    def _on_robot_found(self, robot: RobotInfo):
        #Déclenché par le scanneur à chaque robot détecté
        self._found_robots.append(robot)
        item = QListWidgetItem(f"{robot.name} ({robot.address})")
        self.robot_list.addItem(item)

    def _on_scan_finished(self, robots: list):
        #Déclenché quand le scanneur réseau a terminé
        self.btn_scan.setEnabled(True)
        self.btn_stop_scan.setEnabled(False)
        self.scan_progress.setVisible(False)

        if not robots:
            self.robot_list.addItem("Aucun robot trouvé.")
        self._discovery_worker = None

    def _on_robot_selected(self, row: int):
        #Active/désactive le bouton de connexion selon la sélection dans la liste
        self.btn_connect_selected.setEnabled(0 <= row < len(self._found_robots))

    # aCTIONS DE CONNEXION

    def _on_connect_selected(self):
        #Connecte au robot sélectionné dans la liste de scan
        row = self.robot_list.currentRow()
        if 0 <= row < len(self._found_robots):
            robot = self._found_robots[row]
            self._connection.connect_to_robot(robot.ip, robot.port, use_marty=robot.is_marty)

    def _on_connect_manual(self):
        #Connecte manuellement via les saisies de l'utilisateur
        ip = self.input_ip.text().strip() or self._config.robot.default_ip
        port = self.input_port.value()
        use_marty = self.cb_marty_mode.isChecked()
        self._connection.connect_to_robot(ip, port, use_marty=use_marty)

    def _on_disconnect(self):
        #Arrête la connexion en cours
        self._connection.disconnect_from_robot()

    def _on_connection_changed(self, state: ConnectionState):
        #Met à jour l'affichage selon le nouvel état de la connexion réseau
        if state == ConnectionState.CONNECTED:
            self.status_label.setText(f"Connecté à {self._connection._current_ip}")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            self.btn_disconnect.setEnabled(True)
            self.btn_connect_manual.setEnabled(False)
            self.btn_connect_selected.setEnabled(False)
            self.connected.emit(self._connection._current_ip)

        elif state == ConnectionState.CONNECTING:
            self.status_label.setText("Connexion en cours...")
            self.status_label.setStyleSheet("color: orange;")
            self.btn_disconnect.setEnabled(False)
            self.btn_connect_manual.setEnabled(False)
            self.btn_connect_selected.setEnabled(False)

        elif state == ConnectionState.ERROR:
            self.status_label.setText("Erreur de connexion !")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            self.btn_disconnect.setEnabled(False)
            self.btn_connect_manual.setEnabled(True)
            self.btn_connect_selected.setEnabled(self.robot_list.currentRow() >= 0)

        else:  # DISCONNECTED
            self.status_label.setText("Déconnecté")
            self.status_label.setStyleSheet("color: #64748b;")
            self.btn_disconnect.setEnabled(False)
            self.btn_connect_manual.setEnabled(True)
            self.btn_connect_selected.setEnabled(self.robot_list.currentRow() >= 0)
            self.disconnected.emit()
