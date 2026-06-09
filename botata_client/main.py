import sys

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont

from botata_client.ui.main_window import MainWindow
from botata_client.utils.config import AppConfig
from botata_client.utils.logger import log





def main():
    log.info("Démarrage de Botata Client...")

    # Charger la configuration
    config = AppConfig.load()
    log.info("Configuration chargée.")

    from botata_client.models.act_rules import init_references
    init_references(config)

    # Créer l'application Qt
    app = QApplication(sys.argv)
    app.setApplicationName("Botata Client")
    app.setOrganizationName("Botata Team")



    # Police par défaut
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # Créer et afficher la fenêtre principale
    window = MainWindow(config=config)
    window.resize(config.window_width, config.window_height)
    window.show()

    log.info("Application prête.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
