#Modèles de données simples pour le robot

from dataclasses import dataclass
from enum import Enum


class ConnectionState(Enum):
    """Représente les états possibles de connexion avec le robot."""
    DISCONNECTED = "disconnected"  # Déconnecté
    CONNECTING = "connecting"      # En cours de connexion
    CONNECTED = "connected"        # Connecté
    ERROR = "error"                # Erreur de connexion


@dataclass
class RobotInfo:
    """Informations de base sur un robot trouvé sur le réseau."""
    ip: str              # Adresse IP du robot 
    name: str = "Robot"  # Nom d'affichage du robot
    is_marty: bool = False  # True s'il s'agit d'un robot Marty réel

    @property
    def address(self) -> str:
        """Retourne l'adresse IP du robot."""
        return self.ip
