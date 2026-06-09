# Configuration simple de l'application Botata Client.

import json
from dataclasses import dataclass
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
class AppConfig:
    robot: RobotConfig | None = None
    window_width: int = 1024
    window_height: int = 680

    def __post_init__(self) -> None:
        self.robot = self.robot or RobotConfig()

    def save(self, path: Path = CONFIG_FILE) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "robot": {
                "default_ip": self.robot.default_ip,
                "connection_timeout": self.robot.connection_timeout,
                "reconnect_delay": self.robot.reconnect_delay,
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
                window_width=data.get("window_width", 1024),
                window_height=data.get("window_height", 680),
            )
        except Exception as error:
            print(f"Erreur de chargement, utilisation des paramètres par défaut : {error}")
            return cls()
