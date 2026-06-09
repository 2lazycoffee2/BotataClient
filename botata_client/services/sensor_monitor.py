# Service de monitoring capteur et batterie via QTimer
#
# Écoute les données télémétriques du RobotConnection et émet des
# signaux structurés pour l'UI (batterie, couleur brute, couleur standard).

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from botata_client.models.act_rules import ColorMapper, StandardColor
from botata_client.utils.logger import log

if TYPE_CHECKING:
    from botata_client.services.robot_connection import RobotConnection
    from botata_client.utils.config import AppConfig


@dataclass
class ColorReading:
    """Un relevé couleur horodaté."""
    raw_rgb: list[int]
    hex_value: str
    raw_name: str
    standard: StandardColor
    confidence: float
    timestamp: str = ""


@dataclass
class BatteryReading:
    """Un relevé batterie."""
    level: int = 0         # pourcentage
    voltage: float = 0.0   # volts


class SensorMonitor(QObject):
    """Moniteur de capteurs avec polling via QTimer.

    Se branche sur RobotConnection.data_received pour filtrer et
    redistribuer les données capteur avec le bon rythme de mise à jour.
    """

    # Signaux
    battery_updated = pyqtSignal(int, float)            # (level%, voltage)
    battery_low = pyqtSignal(int)                        # (level%)
    color_updated = pyqtSignal(str, str, list)           # (nom brut, hex, rgb[])
    standard_color_detected = pyqtSignal(object)         # StandardColor
    color_reading_added = pyqtSignal(object)             # ColorReading

    # Historique max
    MAX_HISTORY = 20

    def __init__(
        self,
        connection: RobotConnection,
        config: AppConfig | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._connection = connection
        self._config = config

        # Configuration
        if config and config.monitoring:
            self._battery_interval = int(config.monitoring.battery_poll_interval * 1000)
            self._color_interval = int(config.monitoring.color_poll_interval * 1000)
            self._battery_threshold = config.monitoring.battery_low_threshold
        else:
            self._battery_interval = 10_000
            self._color_interval = 2_000
            self._battery_threshold = 20

        tolerance = config.color.tolerance if config and config.color else 120.0
        self._color_mapper = ColorMapper(tolerance=tolerance)

        # État courant
        self._battery = BatteryReading()
        self._last_color: StandardColor | None = None
        self._color_history: deque[ColorReading] = deque(maxlen=self.MAX_HISTORY)

        # Données brutes en attente de traitement par les timers
        self._pending_data: dict | None = None

        # Timers
        self._battery_timer = QTimer(self)
        self._battery_timer.setInterval(self._battery_interval)
        self._battery_timer.timeout.connect(self._process_battery)

        self._color_timer = QTimer(self)
        self._color_timer.setInterval(self._color_interval)
        self._color_timer.timeout.connect(self._process_color)

        # Écouter les données du worker
        self._connection.data_received.connect(self._on_data_received)

    # ── Contrôle ──────────────────────────────────────────────────────

    def start(self) -> None:
        """Démarre le monitoring."""
        self._battery_timer.start()
        self._color_timer.start()
        log.info(
            f"SensorMonitor démarré — batterie: {self._battery_interval}ms, "
            f"couleur: {self._color_interval}ms"
        )

    def stop(self) -> None:
        """Arrête le monitoring."""
        self._battery_timer.stop()
        self._color_timer.stop()
        log.info("SensorMonitor arrêté.")

    @property
    def battery(self) -> BatteryReading:
        return self._battery

    @property
    def last_color(self) -> StandardColor | None:
        return self._last_color

    @property
    def color_history(self) -> list[ColorReading]:
        return list(self._color_history)

    # ── Réception données brutes ──────────────────────────────────────

    def _on_data_received(self, data: dict) -> None:
        """Stocke les dernières données pour traitement par les timers."""
        self._pending_data = data

    # ── Traitement batterie ───────────────────────────────────────────

    def _process_battery(self) -> None:
        """Traite les données batterie à l'intervalle configuré."""
        if not self._pending_data:
            return

        level = self._pending_data.get("battery_level", 0)
        voltage = self._pending_data.get("battery_voltage", 0.0)

        self._battery = BatteryReading(level=level, voltage=voltage)
        self.battery_updated.emit(level, voltage)

        if level <= self._battery_threshold:
            self.battery_low.emit(level)
            log.warning(f"Batterie faible : {level}%")

    # ── Traitement couleur ────────────────────────────────────────────

    def _process_color(self) -> None:
        """Traite les données couleur à l'intervalle configuré."""
        if not self._pending_data:
            return

        raw_name = self._pending_data.get("color", "unknown")
        hex_value = self._pending_data.get("color_hex", "#000000")
        raw_rgb = self._pending_data.get("color_rgb", [0, 0, 0])

        if not isinstance(raw_rgb, (list, tuple)) or len(raw_rgb) < 3:
            raw_rgb = [0, 0, 0]

        # Mapper vers couleur standard
        std_color, confidence = self._color_mapper.map_color_with_confidence(raw_rgb)

        # Créer le relevé
        from datetime import datetime
        reading = ColorReading(
            raw_rgb=list(raw_rgb[:3]),
            hex_value=hex_value,
            raw_name=raw_name,
            standard=std_color,
            confidence=confidence,
            timestamp=datetime.now().strftime("%H:%M:%S"),
        )
        self._color_history.appendleft(reading)

        # Émettre les signaux
        self.color_updated.emit(raw_name, hex_value, list(raw_rgb[:3]))
        self.color_reading_added.emit(reading)

        if std_color != self._last_color:
            self._last_color = std_color
            self.standard_color_detected.emit(std_color)
            log.info(
                f"Couleur détectée : {raw_name} ({raw_rgb}) → "
                f"{std_color.display_name} (confiance: {confidence:.1%})"
            )
