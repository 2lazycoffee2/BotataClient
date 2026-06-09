# Configuration simple de l'application Botata Client.

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_FILE = PROJECT_ROOT / "config.json"


@dataclass
class RobotConfig:
    default_ip: str = "127.0.0.1"
    connection_timeout: float = 3.0
    reconnect_delay: float = 3.0

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None = None) -> "RobotConfig":
        data = data or {}
        return cls(
            default_ip=data.get("default_ip", "127.0.0.1"),
            connection_timeout=data.get("connection_timeout", 3.0),
            reconnect_delay=data.get("reconnect_delay", 3.0),
        )


@dataclass
class MonitoringConfig:
    """Configuration du polling capteur et batterie (QTimers)."""
    battery_poll_interval: float = 10.0   # secondes
    color_poll_interval: float = 2.0      # secondes
    battery_low_threshold: int = 20       # pourcentage

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None = None) -> "MonitoringConfig":
        data = data or {}
        return cls(
            battery_poll_interval=data.get("battery_poll_interval", 10.0),
            color_poll_interval=data.get("color_poll_interval", 2.0),
            battery_low_threshold=data.get("battery_low_threshold", 20),
        )


@dataclass
class ColorConfig:
    """Configuration de la correspondance couleur brute → standard."""
    tolerance: float = 30.0
    calibration_file: str = "calibration.json"
    references: dict[str, list[int]] = field(default_factory=lambda: {
        "R": [255, 0, 0],
        "O": [255, 165, 0],
        "Y": [255, 255, 0],
        "G": [0, 255, 0],
        "B": [0, 0, 255],
        "I": [75, 0, 130],
        "V": [238, 130, 238],
        "N": [0, 0, 0],
        "W": [255, 255, 255],
    })

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None = None) -> "ColorConfig":
        data = data or {}
        return cls(
            tolerance=data.get("tolerance", 30.0),
            calibration_file=data.get("calibration_file", "calibration.json"),
            references=data.get("references", {
                "R": [255, 0, 0],
                "O": [255, 165, 0],
                "Y": [255, 255, 0],
                "G": [0, 255, 0],
                "B": [0, 0, 255],
                "I": [75, 0, 130],
                "V": [238, 130, 238],
                "N": [0, 0, 0],
                "W": [255, 255, 255],
            }),
        )


@dataclass
class AppConfig:
    robot: RobotConfig | None = None
    monitoring: MonitoringConfig | None = None
    color: ColorConfig | None = None
    window_width: int = 1024
    window_height: int = 680

    def __post_init__(self) -> None:
        self.robot = self.robot or RobotConfig()
        self.monitoring = self.monitoring or MonitoringConfig()
        self.color = self.color or ColorConfig()

    def save(self, path: Path = CONFIG_FILE) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "robot": {
                "default_ip": self.robot.default_ip,
                "connection_timeout": self.robot.connection_timeout,
                "reconnect_delay": self.robot.reconnect_delay,
            },
            "monitoring": {
                "battery_poll_interval": self.monitoring.battery_poll_interval,
                "color_poll_interval": self.monitoring.color_poll_interval,
                "battery_low_threshold": self.monitoring.battery_low_threshold,
            },
            "color": {
                "tolerance": self.color.tolerance,
                "calibration_file": self.color.calibration_file,
                "references": self.color.references,
            },
            "window_width": self.window_width,
            "window_height": self.window_height,
        }

        try:
            with path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as error:
            print(f"Erreur de sauvegarde de la configuration : {error}")

    @classmethod
    def load(cls, path: Path = CONFIG_FILE) -> "AppConfig":
        if not path.exists():
            config = cls()
            config.save(path)
            return config

        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)

            return cls(
                robot=RobotConfig.from_dict(data.get("robot", {})),
                monitoring=MonitoringConfig.from_dict(data.get("monitoring", {})),
                color=ColorConfig.from_dict(data.get("color", {})),
                window_width=data.get("window_width", 1024),
                window_height=data.get("window_height", 680),
            )
        except Exception as error:
            print(f"Erreur de chargement, utilisation des paramètres par défaut : {error}")
            return cls()
