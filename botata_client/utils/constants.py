# Informations sur l'application
APP_NAME = "Botata Client"
APP_VERSION = "0.1.0"

# Configuration par défaut du protocole de découverte UDP
DISCOVERY_PORT = 9559                      # Port UDP pour la découverte
DISCOVERY_BROADCAST_ADDR = "255.255.255.255"  # Adresse de broadcast universelle
DISCOVERY_TIMEOUT = 2.0                    # Durée max d'attente d'une réponse (secondes)
DISCOVERY_MESSAGE = b"BOTATA_DISCOVER"     # Message envoyé pour chercher le robot
DISCOVERY_RESPONSE = b"BOTATA_HERE"        # Réponse attendue du robot
