from PyQt6.QtWidgets import QMainWindow, QStatusBar, QLabel, QTabWidget
from PyQt6.QtCore import Qt

from botata_client.models.act_rules import StandardColor, DEFAULT_ACT_RULES
from botata_client.models.dance_file import DanceFile, Keyframe
from botata_client.services.judge_client import JudgeClient
from botata_client.services.robot_connection import RobotConnection
from botata_client.services.sensor_monitor import SensorMonitor
from botata_client.services.choreography import ChoreographyEngine
from botata_client.ui.connection_panel import ConnectionPanel
from botata_client.ui.monitoring_panel import MonitoringPanel
from botata_client.ui.color_mapping_panel import ColorMappingPanel
from botata_client.ui.dance_creator_panel import DanceCreatorPanel
from botata_client.utils.config import AppConfig
from botata_client.utils.logger import log


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig | None = None, parent=None):
        super().__init__(parent)
        self._config = config or AppConfig()
        self.setWindowTitle("Botata Client")
        self.resize(self._config.window_width, self._config.window_height)

        # ── Services ──
        self.robot_connection = RobotConnection(self._config, parent=self)
        self.sensor_monitor = SensorMonitor(
            self.robot_connection, config=self._config, parent=self
        )
        self.choreography = ChoreographyEngine(
            self.robot_connection, parent=self
        )
        self.judge_client = JudgeClient(self._config.judge_server_url, parent=self)

        # ── Onglets ──
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Onglet 1 : Connexion
        self.connection_panel = ConnectionPanel(
            self.robot_connection, config=self._config
        )
        self.tabs.addTab(self.connection_panel, "🔌 Connexion")

        # Onglet 2 : Monitoring
        self.monitoring_panel = MonitoringPanel()
        self.tabs.addTab(self.monitoring_panel, "📊 Monitoring")

        # Onglet 3 : Couleurs
        self.color_mapping_panel = ColorMappingPanel()
        self.tabs.addTab(self.color_mapping_panel, "🎨 Couleurs")

        # Onglet 4 : Créateur de chorégraphie
        self.dance_creator_panel = DanceCreatorPanel()
        self.tabs.addTab(self.dance_creator_panel, "💃 Créateur")

        # ── Barre de statut ──
        sb = QStatusBar()
        self.setStatusBar(sb)
        self.status_connection = QLabel("Déconnecté")
        self.status_battery = QLabel("🔋 —")
        self.status_color = QLabel("🎨 —")
        self.status_score = QLabel("Score : —")
        sb.addWidget(self.status_connection)
        sb.addPermanentWidget(self.status_battery)
        sb.addPermanentWidget(self.status_color)
        sb.addPermanentWidget(self.status_score)

        # ── Câblage des signaux ──
        self._connect_signals()

    def _connect_signals(self) -> None:
        """Connecte tous les signaux entre services et UI."""

        # Connexion
        self.robot_connection.connection_changed.connect(
            self._on_connection_state_changed
        )

        # Sensor Monitor → Monitoring Panel
        self.sensor_monitor.battery_updated.connect(
            self.monitoring_panel.update_battery
        )
        self.sensor_monitor.battery_updated.connect(self._on_battery_updated)

        self.sensor_monitor.color_updated.connect(
            self.monitoring_panel.update_color
        )

        self.sensor_monitor.color_reading_added.connect(
            self._on_color_reading
        )

        self.sensor_monitor.standard_color_detected.connect(
            self._on_standard_color_detected
        )

        # Chorégraphie → Monitoring Panel
        self.choreography.state_changed.connect(
            self.monitoring_panel.update_choreo_state
        )

        # Monitoring Panel → Chorégraphie
        self.monitoring_panel.execute_act_requested.connect(
            self._on_execute_act
        )
        self.monitoring_panel.test_act_requested.connect(
            self.choreography.execute_for_color
        )
        self.monitoring_panel.auto_mode_toggled.connect(
            self._on_auto_mode_toggled
        )
        self.monitoring_panel.neutral_button.clicked.connect(
            self.choreography.return_to_neutral
        )
        
        # Color Mapping Panel → MainWindow
        self.color_mapping_panel.calibration_requested.connect(
            self._on_calibration_requested
        )

        # Dance Creator Panel → MainWindow
        self.dance_creator_panel.play_requested.connect(
            self._on_play_keyframes
        )
        self.dance_creator_panel.send_position_requested.connect(
            self._on_send_position
        )
        self.dance_creator_panel.return_neutral_requested.connect(
            self.choreography.return_to_neutral
        )

        # Choreography → Judge Client
        self.choreography.keyframe_started.connect(
            self._on_keyframe_started
        )

        # Judge Client → UI
        self.judge_client.score_updated.connect(self._on_score_updated)
        self.judge_client.session_started.connect(
            lambda rid: self.status_score.setText(f"Score : — (session {rid})")
        )
        self.judge_client.error_occurred.connect(self._on_judge_error)
        self.judge_client.log_message.connect(
            self.connection_panel.append_server_log
        )
        self.connection_panel.judge_server_url_changed.connect(
            self.judge_client.set_base_url
        )

    # ── Handlers ──────────────────────────────────────────────────────

    def _on_connection_state_changed(self, state) -> None:
        if state.name == "CONNECTED":
            text = "Connecté"
            self.sensor_monitor.start()
            log.info("SensorMonitor démarré après connexion.")
        elif state.name == "CONNECTING":
            text = "Connexion..."
        else:
            text = "Déconnecté"
            self.sensor_monitor.stop()
        self.status_connection.setText(text)

    def _on_battery_updated(self, level: int, voltage: float) -> None:
        icon = "🔋" if level > 20 else "🪫"
        self.status_battery.setText(f"{icon} {level}%  ({voltage:.1f}V)")

    def _on_color_reading(self, reading) -> None:
        """Reçoit un ColorReading et met à jour les deux panneaux."""
        # Panneau couleur : historique
        self.color_mapping_panel.add_reading(reading)

        # Panneau monitoring : standard + confiance
        self.monitoring_panel.update_standard_color(
            reading.standard, reading.confidence
        )

    def _on_standard_color_detected(self, color: StandardColor) -> None:
        """Nouvelle couleur standard détectée — met à jour statut + chorégraphie."""
        self.status_color.setText(f"🎨 {color.name} ({color.display_name})")

        # En mode auto, le moteur de chorégraphie est notifié directement
        self.choreography.on_color_detected(color)

    def _on_execute_act(self) -> None:
        """Bouton 'Exécuter ACT' pressé."""
        color = self.sensor_monitor.last_color
        if color:
            self.choreography.execute_for_color(color)
        else:
            log.warning("Pas de couleur détectée, impossible d'exécuter ACT.")

    def _on_auto_mode_toggled(self, enabled: bool) -> None:
        self.choreography.auto_mode = enabled

    def _on_calibration_requested(self, std_color: StandardColor, rgb: tuple[int, int, int]) -> None:
        """Appelé lorsque l'utilisateur veut calibrer une couleur."""
        from botata_client.models.act_rules import update_reference_color
        update_reference_color(std_color, rgb)
        
        # Sauvegarder dans la configuration
        self._config.color.references[std_color.name] = list(rgb)
        self._config.save()
        
        log.info(f"Calibration enregistrée : {std_color.name} = {rgb}")
        self.status_color.setText(f"🎨 Calibré : {std_color.name} = {rgb}")

    def _on_send_position(self, joints: dict[str, int], move_time: int) -> None:
        """Appelé lorsque le créateur veut envoyer une position absolue."""
        self.robot_connection.send_command(
            "move_joints", joints=joints, move_time=move_time
        )
        color, arm, exp = self._make_step_payload(joints, None)
        self.judge_client.send_step(color, arm, exp)

    def _on_play_keyframes(self, keyframes: list[Keyframe]) -> None:
        dance = DanceFile(
            name="Session Chorégraphie",
            mvs=len(keyframes),
            tempo=keyframes[0].move_time if keyframes else 800,
            keyframes=list(keyframes),
        )
        self.judge_client.start_dance(dance)
        self.choreography.play_keyframes(keyframes)

    def _on_keyframe_started(self, kf: Keyframe) -> None:
        color, arm, exp = self._make_step_payload(kf.joints, kf.eye_color)
        self.judge_client.send_step(color, arm, exp)

    def _make_step_payload(
        self,
        joints: dict[str, int],
        eye_color: tuple[int, int, int] | None,
    ) -> tuple[str, str, str]:
        color = (
            self.sensor_monitor.last_color.name
            if self.sensor_monitor.last_color
            else "N"
        )
        arms: list[str] = []
        left_arm = joints.get("left arm", 0)
        right_arm = joints.get("right arm", 0)
        if left_arm > 0:
            arms.append("ALU")
        elif left_arm < 0:
            arms.append("ALB")
        if right_arm > 0:
            arms.append("ARU")
        elif right_arm < 0:
            arms.append("ARB")
        arm = "+".join(arms) if arms else "XNT"
        exp = "XSD" if eye_color and eye_color != (255, 255, 255) else "XNT"
        return color, arm, exp

    def _on_score_updated(self, score: int) -> None:
        self.status_score.setText(f"Score : {score}")

    def _on_judge_error(self, message: str) -> None:
        log.error(message)
        self.status_score.setText("Score : erreur")

    # ── Nettoyage ─────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        self.sensor_monitor.stop()
        self.choreography.stop()
        self.robot_connection.disconnect_from_robot()
        super().closeEvent(event)
