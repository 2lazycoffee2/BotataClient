# Interface de correspondance : "Couleur brute captée" ↔ "Couleur standard (R, G, B, N)"
#
# Affiche un tableau temps réel avec l'historique des lectures couleur,
# les pastilles visuelles brute et standard côte-à-côte.

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from botata_client.models.act_rules import StandardColor

if TYPE_CHECKING:
    from botata_client.services.sensor_monitor import ColorReading


# Correspondance couleur standard → style d'affichage
_STD_STYLES: dict[StandardColor, tuple[str, str]] = {
    StandardColor.R: ("#ff4444", "Rouge"),
    StandardColor.G: ("#44cc44", "Vert"),
    StandardColor.B: ("#4488ff", "Bleu"),
    StandardColor.N: ("#888888", "Noir"),
}


class ColorMappingPanel(QWidget):
    """Panneau de correspondance couleur brute ↔ couleur standard."""

    MAX_ROWS = 20

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    # ── Construction UI ───────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)

        # ── Légende ──
        legend_group = QGroupBox("📖 Légende des couleurs standard")
        legend_group.setStyleSheet(
            "QGroupBox { font-weight: bold; font-size: 13px; "
            "border: 1px solid #444; border-radius: 6px; margin-top: 8px; padding-top: 16px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 12px; }"
        )
        legend_layout = QHBoxLayout(legend_group)
        for std_color in [StandardColor.R, StandardColor.G, StandardColor.B, StandardColor.N]:
            hex_color, name = _STD_STYLES[std_color]
            lbl = QLabel(f"  ● {std_color.name} = {name}  ")
            lbl.setStyleSheet(f"color: {hex_color}; font-weight: bold; font-size: 12px;")
            legend_layout.addWidget(lbl)
        legend_layout.addStretch()
        layout.addWidget(legend_group)

        # ── Dernière lecture ──
        current_group = QGroupBox("📡 Dernière lecture")
        current_group.setStyleSheet(
            "QGroupBox { font-weight: bold; font-size: 13px; "
            "border: 1px solid #444; border-radius: 6px; margin-top: 8px; padding-top: 16px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 12px; }"
        )
        current_layout = QHBoxLayout(current_group)

        self._current_raw_label = QLabel("RGB brut : —")
        self._current_raw_label.setFont(QFont("Consolas", 11))
        current_layout.addWidget(self._current_raw_label)

        self._current_hex_label = QLabel("Hex : —")
        self._current_hex_label.setFont(QFont("Consolas", 11))
        current_layout.addWidget(self._current_hex_label)

        arrow = QLabel("  →  ")
        arrow.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        current_layout.addWidget(arrow)

        self._current_std_label = QLabel("Standard : —")
        self._current_std_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        current_layout.addWidget(self._current_std_label)

        self._current_confidence_label = QLabel("")
        self._current_confidence_label.setFont(QFont("Segoe UI", 10))
        self._current_confidence_label.setStyleSheet("color: #888;")
        current_layout.addWidget(self._current_confidence_label)

        current_layout.addStretch()
        layout.addWidget(current_group)

        # ── Historique ──
        history_group = QGroupBox("📋 Historique des relevés")
        history_group.setStyleSheet(
            "QGroupBox { font-weight: bold; font-size: 13px; "
            "border: 1px solid #444; border-radius: 6px; margin-top: 8px; padding-top: 16px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 12px; }"
        )
        history_layout = QVBoxLayout(history_group)

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels([
            "Heure", "RGB brut", "Hex", "Nom capteur", "→ Standard", "Confiance"
        ])
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(
            "QTableWidget { background-color: #1e1e1e; alternate-background-color: #252525; "
            "gridline-color: #333; }"
            "QTableWidget::item { padding: 4px; }"
            "QHeaderView::section { background-color: #333; color: white; "
            "border: 1px solid #444; padding: 4px; font-weight: bold; }"
        )

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

        history_layout.addWidget(self._table)
        layout.addWidget(history_group)

    # ── Mise à jour ───────────────────────────────────────────────────

    def add_reading(self, reading: ColorReading) -> None:
        """Ajoute un nouveau relevé couleur au tableau."""
        # Mettre à jour la dernière lecture
        r, g, b = reading.raw_rgb[:3] if len(reading.raw_rgb) >= 3 else (0, 0, 0)
        self._current_raw_label.setText(f"RGB brut : ({r}, {g}, {b})")
        self._current_hex_label.setText(f"Hex : {reading.hex_value}")

        hex_color, name = _STD_STYLES.get(reading.standard, ("#888", "?"))
        self._current_std_label.setText(f"Standard : {reading.standard.name} ({name})")
        self._current_std_label.setStyleSheet(f"color: {hex_color}; font-weight: bold;")
        self._current_confidence_label.setText(f"({reading.confidence:.0%})")

        # Insérer dans le tableau (en haut)
        if self._table.rowCount() >= self.MAX_ROWS:
            self._table.removeRow(self._table.rowCount() - 1)

        self._table.insertRow(0)

        # Heure
        self._table.setItem(0, 0, QTableWidgetItem(reading.timestamp))

        # RGB brut — coloré
        rgb_item = QTableWidgetItem(f"({r}, {g}, {b})")
        rgb_item.setForeground(QColor(r, g, b))
        rgb_item.setFont(QFont("Consolas", 9))
        self._table.setItem(0, 1, rgb_item)

        # Hex
        hex_item = QTableWidgetItem(reading.hex_value)
        hex_item.setForeground(QColor(reading.hex_value) if reading.hex_value.startswith("#") else QColor("#888"))
        self._table.setItem(0, 2, hex_item)

        # Nom capteur
        self._table.setItem(0, 3, QTableWidgetItem(reading.raw_name))

        # Standard — coloré
        std_item = QTableWidgetItem(f" {reading.standard.name} — {name}")
        std_item.setForeground(QColor(hex_color))
        std_item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._table.setItem(0, 4, std_item)

        # Confiance
        conf_item = QTableWidgetItem(f"{reading.confidence:.0%}")
        if reading.confidence >= 0.7:
            conf_item.setForeground(QColor("#4caf50"))
        elif reading.confidence >= 0.4:
            conf_item.setForeground(QColor("#ff9800"))
        else:
            conf_item.setForeground(QColor("#f44336"))
        self._table.setItem(0, 5, conf_item)
