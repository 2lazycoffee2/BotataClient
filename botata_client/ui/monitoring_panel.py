# Panneau de monitoring temps réel : batterie, capteur couleur, chorégraphie ACT

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from botata_client.models.act_rules import DEFAULT_ACT_RULES, StandardColor

if TYPE_CHECKING:
    from botata_client.services.choreography import ChoreographyEngine
    from botata_client.services.sensor_monitor import SensorMonitor


class _ColorSwatch(QFrame):
    """Petit carré de couleur."""
    def __init__(self, size: int = 32, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setFrameShape(QFrame.Shape.Box)
        self.setStyleSheet("background-color: #333; border: 1px solid #555; border-radius: 4px;")

    def set_color(self, r: int, g: int, b: int) -> None:
        self.setStyleSheet(
            f"background-color: rgb({r},{g},{b}); border: 1px solid #555; border-radius: 4px;"
        )


class MonitoringPanel(QWidget):
    """Panneau principal de monitoring : batterie + capteur + chorégraphie."""

    execute_act_requested = pyqtSignal()
    auto_mode_toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    # ── Construction UI ───────────────────────────────────────────────

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # ── Section Batterie ──
        battery_group = QGroupBox("🔋 Batterie")
        battery_group.setStyleSheet(
            "QGroupBox { font-weight: bold; font-size: 13px; "
            "border: 1px solid #444; border-radius: 6px; margin-top: 8px; padding-top: 16px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 12px; }"
        )
        bat_layout = QVBoxLayout(battery_group)

        self._battery_bar = QProgressBar()
        self._battery_bar.setRange(0, 100)
        self._battery_bar.setValue(0)
        self._battery_bar.setFormat("%v%")
        self._battery_bar.setFixedHeight(24)
        self._battery_bar.setStyleSheet(
            "QProgressBar { border: 1px solid #555; border-radius: 4px; background: #2a2a2a; text-align: center; color: white; }"
            "QProgressBar::chunk { border-radius: 3px; }"
        )
        bat_layout.addWidget(self._battery_bar)

        bat_info = QHBoxLayout()
        self._battery_level_label = QLabel("Niveau : —")
        self._battery_voltage_label = QLabel("Tension : —")
        self._battery_status = QLabel("●")
        self._battery_status.setStyleSheet("color: #888; font-size: 16px;")
        bat_info.addWidget(self._battery_level_label)
        bat_info.addWidget(self._battery_voltage_label)
        bat_info.addStretch()
        bat_info.addWidget(self._battery_status)
        bat_layout.addLayout(bat_info)

        main_layout.addWidget(battery_group)

        # ── Section Capteur Couleur ──
        color_group = QGroupBox("🎨 Capteur Couleur")
        color_group.setStyleSheet(
            "QGroupBox { font-weight: bold; font-size: 13px; "
            "border: 1px solid #444; border-radius: 6px; margin-top: 8px; padding-top: 16px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 12px; }"
        )
        color_layout = QVBoxLayout(color_group)

        # Ligne couleur brute → standard
        mapping_row = QHBoxLayout()

        # Couleur brute
        brut_frame = QVBoxLayout()
        brut_frame.addWidget(QLabel("Couleur brute :"))
        self._raw_swatch = _ColorSwatch(40)
        self._raw_rgb_label = QLabel("RGB: —")
        self._raw_rgb_label.setFont(QFont("Consolas", 9))
        self._raw_name_label = QLabel("Nom: —")
        brut_frame.addWidget(self._raw_swatch)
        brut_frame.addWidget(self._raw_rgb_label)
        brut_frame.addWidget(self._raw_name_label)
        mapping_row.addLayout(brut_frame)

        # Flèche
        arrow = QLabel("  →  ")
        arrow.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mapping_row.addWidget(arrow)

        # Couleur standard
        std_frame = QVBoxLayout()
        std_frame.addWidget(QLabel("Standard :"))
        self._std_swatch = _ColorSwatch(40)
        self._std_color_label = QLabel("—")
        self._std_color_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self._confidence_label = QLabel("Confiance: —")
        std_frame.addWidget(self._std_swatch)
        std_frame.addWidget(self._std_color_label)
        std_frame.addWidget(self._confidence_label)
        mapping_row.addLayout(std_frame)

        mapping_row.addStretch()
        color_layout.addLayout(mapping_row)

        main_layout.addWidget(color_group)

        # ── Section Chorégraphie ACT ──
        act_group = QGroupBox("🤖 Chorégraphie ACT")
        act_group.setStyleSheet(
            "QGroupBox { font-weight: bold; font-size: 13px; "
            "border: 1px solid #444; border-radius: 6px; margin-top: 8px; padding-top: 16px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 12px; }"
        )
        act_layout = QVBoxLayout(act_group)

        # Tableau de correspondance couleur → actions
        self._act_table = QTableWidget(4, 5)
        self._act_table.setHorizontalHeaderLabels(
            ["Couleur", "Yeux LED", "Sourcils", "Bras", "Pas"]
        )
        self._act_table.verticalHeader().setVisible(False)
        self._act_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._act_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._act_table.setMaximumHeight(160)
        self._act_table.horizontalHeader().setStretchLastSection(True)
        self._populate_act_table()
        act_layout.addWidget(self._act_table)

        # État courant
        state_row = QHBoxLayout()
        state_row.addWidget(QLabel("État :"))
        self._state_label = QLabel("En attente")
        self._state_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._state_label.setStyleSheet("color: #aaa;")
        state_row.addWidget(self._state_label)
        state_row.addStretch()
        act_layout.addLayout(state_row)

        # Boutons
        btn_row = QHBoxLayout()

        self._btn_execute = QPushButton("▶  Exécuter ACT")
        self._btn_execute.setFixedHeight(34)
        self._btn_execute.setStyleSheet(
            "QPushButton { background-color: #2d7d46; color: white; border-radius: 6px; "
            "font-weight: bold; padding: 0 16px; }"
            "QPushButton:hover { background-color: #35915a; }"
            "QPushButton:disabled { background-color: #555; color: #999; }"
        )
        self._btn_execute.clicked.connect(self.execute_act_requested.emit)
        btn_row.addWidget(self._btn_execute)

        self._btn_auto = QPushButton("⚡ Mode Auto : OFF")
        self._btn_auto.setFixedHeight(34)
        self._btn_auto.setCheckable(True)
        self._btn_auto.setStyleSheet(
            "QPushButton { background-color: #555; color: white; border-radius: 6px; "
            "font-weight: bold; padding: 0 16px; }"
            "QPushButton:checked { background-color: #c06000; }"
            "QPushButton:hover { background-color: #666; }"
        )
        self._btn_auto.toggled.connect(self._on_auto_toggled)
        btn_row.addWidget(self._btn_auto)

        self._btn_neutral = QPushButton("⏹ XNT (Neutre)")
        self._btn_neutral.setFixedHeight(34)
        self._btn_neutral.setStyleSheet(
            "QPushButton { background-color: #444; color: white; border-radius: 6px; "
            "font-weight: bold; padding: 0 16px; }"
            "QPushButton:hover { background-color: #555; }"
        )
        btn_row.addWidget(self._btn_neutral)

        act_layout.addLayout(btn_row)
        main_layout.addWidget(act_group)

        main_layout.addStretch()

    def _populate_act_table(self) -> None:
        """Remplit le tableau des règles ACT par défaut."""
        color_styles = {
            StandardColor.R: ("#ff4444", "Rouge"),
            StandardColor.G: ("#44cc44", "Vert"),
            StandardColor.B: ("#4488ff", "Bleu"),
            StandardColor.N: ("#888888", "Noir"),
        }
        for row, std_color in enumerate([StandardColor.R, StandardColor.G, StandardColor.B, StandardColor.N]):
            rule = DEFAULT_ACT_RULES[std_color]
            style_color, name = color_styles[std_color]

            # Couleur
            item_color = QTableWidgetItem(f"  {name}")
            item_color.setForeground(QColor(style_color))
            item_color.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            self._act_table.setItem(row, 0, item_color)

            # Yeux LED
            r, g, b = rule.eye_color
            item_eyes = QTableWidgetItem(f"({r},{g},{b})")
            item_eyes.setForeground(QColor(r, g, b))
            self._act_table.setItem(row, 1, item_eyes)

            # Sourcils
            self._act_table.setItem(row, 2, QTableWidgetItem(f"{rule.eyebrow_angle}°"))

            # Bras
            arm_text = " + ".join(a.code for a in rule.arm_actions) if rule.arm_actions else "XNT"
            self._act_table.setItem(row, 3, QTableWidgetItem(arm_text))

            # Pas
            step_text = rule.step_action.code if rule.step_action else "—"
            self._act_table.setItem(row, 4, QTableWidgetItem(step_text))

    def _on_auto_toggled(self, checked: bool) -> None:
        self._btn_auto.setText(f"⚡ Mode Auto : {'ON' if checked else 'OFF'}")
        self.auto_mode_toggled.emit(checked)

    # ── Slots de mise à jour ──────────────────────────────────────────

    def update_battery(self, level: int, voltage: float) -> None:
        """Met à jour l'affichage batterie."""
        self._battery_bar.setValue(level)
        self._battery_level_label.setText(f"Niveau : {level}%")
        self._battery_voltage_label.setText(f"Tension : {voltage:.2f} V")

        # Style selon le niveau
        if level > 50:
            chunk_color = "#4caf50"
            status_color = "#4caf50"
        elif level > 20:
            chunk_color = "#ff9800"
            status_color = "#ff9800"
        else:
            chunk_color = "#f44336"
            status_color = "#f44336"

        self._battery_bar.setStyleSheet(
            f"QProgressBar {{ border: 1px solid #555; border-radius: 4px; background: #2a2a2a; "
            f"text-align: center; color: white; }}"
            f"QProgressBar::chunk {{ background-color: {chunk_color}; border-radius: 3px; }}"
        )
        self._battery_status.setStyleSheet(f"color: {status_color}; font-size: 16px;")

    def update_color(self, raw_name: str, hex_value: str, raw_rgb: list[int]) -> None:
        """Met à jour l'affichage couleur brute."""
        if len(raw_rgb) >= 3:
            self._raw_swatch.set_color(raw_rgb[0], raw_rgb[1], raw_rgb[2])
        self._raw_rgb_label.setText(f"RGB: ({', '.join(str(v) for v in raw_rgb[:3])})")
        self._raw_name_label.setText(f"Nom: {raw_name}")

    def update_standard_color(self, color: StandardColor, confidence: float = 0.0) -> None:
        """Met à jour l'affichage couleur standard."""
        ref = color.rgb
        self._std_swatch.set_color(*ref)
        self._std_color_label.setText(f"{color.name} — {color.display_name}")

        # Couleur du label selon la standard
        style_map = {
            StandardColor.R: "#ff4444",
            StandardColor.G: "#44cc44",
            StandardColor.B: "#4488ff",
            StandardColor.N: "#aaaaaa",
        }
        self._std_color_label.setStyleSheet(f"color: {style_map.get(color, '#aaa')};")
        self._confidence_label.setText(f"Confiance: {confidence:.0%}")

    def update_choreo_state(self, state_text: str) -> None:
        """Met à jour le label d'état de la chorégraphie."""
        self._state_label.setText(state_text)
        if "Exécution" in state_text:
            self._state_label.setStyleSheet("color: #ff9800; font-weight: bold;")
        elif "attente" in state_text.lower() or "terminée" in state_text.lower():
            self._state_label.setStyleSheet("color: #aaa;")
        elif "XNT" in state_text:
            self._state_label.setStyleSheet("color: #4caf50;")
        else:
            self._state_label.setStyleSheet("color: #ccc;")

    @property
    def neutral_button(self) -> QPushButton:
        return self._btn_neutral
