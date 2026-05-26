#Configuration simple de l'application Botata Client.

import json
from pathlib import Path

# Définition des chemins vers les fichiers du projet
PROJECT_ROOT = Path(__file__).parent.parent.parent
CONFIG_FILE = PROJECT_ROOT / "config.json"


class RobotConfig:
    def __init__(self, **kwargs):
        self.default_ip = kwargs.get("default_ip", "127.0.0.1")
        self.default_port = kwargs.get("default_port", 9559)
        self.connection_timeout = kwargs.get("connection_timeout", 3.0)
        self.reconnect_delay = kwargs.get("reconnect_delay", 3.0)


class AppConfig:
    def __init__(self, robot_data=None, window_width=1024, window_height=680):
        self.robot = RobotConfig(**(robot_data or {}))
        self.window_width = window_width
        self.window_height = window_height

    def save(self, path=CONFIG_FILE):
        try:
            data = {
                "robot": {
                    "default_ip": self.robot.default_ip,
                    "default_port": self.robot.default_port,
                    "connection_timeout": self.robot.connection_timeout,
                    "reconnect_delay": self.robot.reconnect_delay,
                },
                "window_width": self.window_width,
                "window_height": self.window_height,
            }
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Erreur de sauvegarde de la configuration : {e}")

    @classmethod
    def load(cls, path=CONFIG_FILE) -> "AppConfig":
        if not path.exists():
            config = cls()
            config.save(path)
            return config

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(
                robot_data=data.get("robot", {}),
                window_width=data.get("window_width", 1024),
                window_height=data.get("window_height", 680),
            )
        except Exception as e:
            print(f"Erreur de chargement, utilisation des paramètres par défaut : {e}")
            return cls()
