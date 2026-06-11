# Onglet Créateur de Chorégraphie — contrôle articulaire complet de Marty V2
#
# Permet de :
#   - Régler chaque articulation via des sliders
#   - Envoyer la position au robot en temps réel
#   - Capturer des keyframes dans une timeline
#   - Jouer, sauvegarder et charger des fichiers .dance

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QColorDialog,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from botata_client.models.dance_file import JOINT_NAMES, DanceFile, Keyframe


# Couleur d'affichage par articulation
_JOINT_COLORS: dict[str, str] = {
    "left hip": "#e06666",
    "left twist": "#e69138",
    "left knee": "#f1c232",
    "right hip": "#6fa8dc",
    "right twist": "#8e7cc3",
    "right knee": "#93c47d",
    "left arm": "#cc4125",
    "right arm": "#3c78d8",
    "eyes": "#ffd966",
}


class DanceCreatorPanel(QWidget):
    """Onglet de creation de choregraphie avec controle articulaire."""

    play_requested = pyqtSignal(list)        # list[Keyframe]
    play_dance_requested = pyqtSignal(object)  # DanceFile
    send_position_requested = pyqtSignal(dict, int)  # joints, move_time
    return_neutral_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sliders: dict[str, QSlider] = {}
        self._slider_labels: dict[str, QLabel] = {}
        self._keyframes: list[Keyframe] = []
        self._eye_color: tuple[int, int, int] | None = None
        self._build_ui()

    # ── Construction UI ───────────────────────────────────────────────

    def _build_ui(self) -> None:
        main = QHBoxLayout(self)
        main.setSpacing(12)
        main.setContentsMargins(12, 12, 12, 12)

        # ── Colonne Gauche : Contrôles articulaires ──
        left_col = QVBoxLayout()

        # Nom de la chorégraphie
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Nom :"))
        self._name_edit = QLineEdit("Nouvelle Choregraphie")
        self._name_edit.setStyleSheet("font-size: 13px; padding: 4px;")
        name_row.addWidget(self._name_edit)
        left_col.addLayout(name_row)

        # Groupe articulations
        joints_group = QGroupBox("🦿 Articulations")
        joints_group.setStyleSheet(
            "QGroupBox { font-weight: bold; font-size: 13px; "
            "border: 1px solid #444; border-radius: 6px; margin-top: 8px; padding-top: 16px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 12px; }"
        )
        joints_layout = QGridLayout(joints_group)

        for row, jname in enumerate(JOINT_NAMES):
            color = _JOINT_COLORS.get(jname, "#aaa")

            # Label du nom
            lbl_name = QLabel(jname.title())
            lbl_name.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 11px;")
            lbl_name.setFixedWidth(100)
            joints_layout.addWidget(lbl_name, row, 0)

            # Slider
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(-100, 100)
            slider.setValue(0)
            slider.setTickPosition(QSlider.TickPosition.TicksBelow)
            slider.setTickInterval(25)
            slider.setStyleSheet(
                f"QSlider::groove:horizontal {{ background: #333; height: 6px; border-radius: 3px; }}"
                f"QSlider::handle:horizontal {{ background: {color}; width: 16px; margin: -5px 0; border-radius: 8px; }}"
                f"QSlider::sub-page:horizontal {{ background: {color}; border-radius: 3px; }}"
            )
            joints_layout.addWidget(slider, row, 1)
            self._sliders[jname] = slider

            # Label valeur
            lbl_val = QLabel("0°")
            lbl_val.setFixedWidth(45)
            lbl_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_val.setFont(QFont("Consolas", 10))
            joints_layout.addWidget(lbl_val, row, 2)
            self._slider_labels[jname] = lbl_val

            # Connecter le slider
            slider.valueChanged.connect(
                lambda val, n=jname: self._on_slider_changed(n, val)
            )

        left_col.addWidget(joints_group)

        # Groupe vitesse + yeux
        ctrl_group = QGroupBox("⚙ Parametres")
        ctrl_group.setStyleSheet(
            "QGroupBox { font-weight: bold; font-size: 13px; "
            "border: 1px solid #444; border-radius: 6px; margin-top: 8px; padding-top: 16px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 12px; }"
        )
        ctrl_layout = QGridLayout(ctrl_group)

        # Vitesse
        ctrl_layout.addWidget(QLabel("Vitesse (ms) :"), 0, 0)
        self._speed_spin = QSpinBox()
        self._speed_spin.setRange(100, 5000)
        self._speed_spin.setValue(800)
        self._speed_spin.setSingleStep(100)
        self._speed_spin.setSuffix(" ms")
        ctrl_layout.addWidget(self._speed_spin, 0, 1)

        # Couleur des yeux
        ctrl_layout.addWidget(QLabel("Yeux LED :"), 1, 0)
        self._eye_btn = QPushButton("Choisir couleur")
        self._eye_btn.setStyleSheet(
            "background-color: #333; color: white; border-radius: 4px; padding: 4px 8px;"
        )
        self._eye_btn.clicked.connect(self._pick_eye_color)
        ctrl_layout.addWidget(self._eye_btn, 1, 1)

        self._eye_preview = QLabel("")
        self._eye_preview.setFixedSize(24, 24)
        self._eye_preview.setStyleSheet("background-color: #333; border: 1px solid #555; border-radius: 4px;")
        ctrl_layout.addWidget(self._eye_preview, 1, 2)

        left_col.addWidget(ctrl_group)

        # Boutons d'action rapide
        quick_row = QHBoxLayout()

        btn_send = QPushButton("📤 Envoyer au robot")
        btn_send.setFixedHeight(34)
        btn_send.setStyleSheet(
            "QPushButton { background-color: #2d7d46; color: white; border-radius: 6px; "
            "font-weight: bold; padding: 0 12px; }"
            "QPushButton:hover { background-color: #35915a; }"
        )
        btn_send.clicked.connect(self._on_send_to_robot)
        quick_row.addWidget(btn_send)

        btn_add = QPushButton("➕ Ajouter Keyframe")
        btn_add.setFixedHeight(34)
        btn_add.setStyleSheet(
            "QPushButton { background-color: #0275d8; color: white; border-radius: 6px; "
            "font-weight: bold; padding: 0 12px; }"
            "QPushButton:hover { background-color: #0367bf; }"
        )
        btn_add.clicked.connect(self._on_add_keyframe)
        quick_row.addWidget(btn_add)

        btn_reset = QPushButton("🔄 Reset Sliders")
        btn_reset.setFixedHeight(34)
        btn_reset.setStyleSheet(
            "QPushButton { background-color: #555; color: white; border-radius: 6px; "
            "font-weight: bold; padding: 0 12px; }"
            "QPushButton:hover { background-color: #666; }"
        )
        btn_reset.clicked.connect(self._on_reset_sliders)
        quick_row.addWidget(btn_reset)

        btn_neutral = QPushButton("⏹ XNT (Neutre)")
        btn_neutral.setFixedHeight(34)
        btn_neutral.setStyleSheet(
            "QPushButton { background-color: #444; color: white; border-radius: 6px; "
            "font-weight: bold; padding: 0 12px; }"
            "QPushButton:hover { background-color: #555; }"
        )
        btn_neutral.clicked.connect(self._on_return_neutral)
        quick_row.addWidget(btn_neutral)

        left_col.addLayout(quick_row)
        left_col.addStretch()

        main.addLayout(left_col, stretch=1)

        # ── Colonne Droite : Timeline ──
        right_col = QVBoxLayout()

        timeline_group = QGroupBox("🎬 Timeline")
        timeline_group.setStyleSheet(
            "QGroupBox { font-weight: bold; font-size: 13px; "
            "border: 1px solid #444; border-radius: 6px; margin-top: 8px; padding-top: 16px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 12px; }"
        )
        tl_layout = QVBoxLayout(timeline_group)

        # Tableau timeline
        cols = ["#"] + [j.replace(" ", "\n") for j in JOINT_NAMES] + ["ms", "Yeux", ""]
        self._timeline_table = QTableWidget(0, len(cols))
        self._timeline_table.setHorizontalHeaderLabels(cols)
        self._timeline_table.verticalHeader().setVisible(False)
        self._timeline_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._timeline_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._timeline_table.setAlternatingRowColors(True)
        self._timeline_table.setStyleSheet(
            "QTableWidget { background-color: #1e1e1e; alternate-background-color: #252525; "
            "gridline-color: #333; font-size: 10px; }"
            "QTableWidget::item { padding: 2px; }"
            "QHeaderView::section { background-color: #333; color: white; "
            "border: 1px solid #444; padding: 2px; font-weight: bold; font-size: 9px; }"
        )

        header = self._timeline_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        for i in range(1, len(JOINT_NAMES) + 1):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(len(JOINT_NAMES) + 1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(len(JOINT_NAMES) + 2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(len(JOINT_NAMES) + 3, QHeaderView.ResizeMode.ResizeToContents)

        tl_layout.addWidget(self._timeline_table)

        # Boutons timeline
        tl_btns = QHBoxLayout()

        btn_play = QPushButton("▶ Jouer")
        btn_play.setFixedHeight(34)
        btn_play.setStyleSheet(
            "QPushButton { background-color: #d9534f; color: white; border-radius: 6px; "
            "font-weight: bold; padding: 0 16px; font-size: 13px; }"
            "QPushButton:hover { background-color: #c9302c; }"
        )
        btn_play.clicked.connect(self._on_play)
        tl_btns.addWidget(btn_play)

        btn_clear = QPushButton("🗑 Vider")
        btn_clear.setFixedHeight(34)
        btn_clear.setStyleSheet(
            "QPushButton { background-color: #555; color: white; border-radius: 6px; "
            "font-weight: bold; padding: 0 12px; }"
            "QPushButton:hover { background-color: #666; }"
        )
        btn_clear.clicked.connect(self._on_clear_timeline)
        tl_btns.addWidget(btn_clear)

        tl_layout.addLayout(tl_btns)

        # Boutons fichier
        file_btns = QHBoxLayout()

        btn_save = QPushButton("💾 Sauvegarder .dance")
        btn_save.setFixedHeight(34)
        btn_save.setStyleSheet(
            "QPushButton { background-color: #f0ad4e; color: black; border-radius: 6px; "
            "font-weight: bold; padding: 0 12px; }"
            "QPushButton:hover { background-color: #eea236; }"
        )
        btn_save.clicked.connect(self._on_save_dance)
        file_btns.addWidget(btn_save)

        btn_load = QPushButton("📂 Charger .dance")
        btn_load.setFixedHeight(34)
        btn_load.setStyleSheet(
            "QPushButton { background-color: #5bc0de; color: black; border-radius: 6px; "
            "font-weight: bold; padding: 0 12px; }"
            "QPushButton:hover { background-color: #46b8da; }"
        )
        btn_load.clicked.connect(self._on_load_dance)
        file_btns.addWidget(btn_load)

        tl_layout.addLayout(file_btns)

        right_col.addWidget(timeline_group)
        main.addLayout(right_col, stretch=1)

    # ── Handlers ──────────────────────────────────────────────────────

    def _on_slider_changed(self, joint_name: str, value: int) -> None:
        self._slider_labels[joint_name].setText(f"{value}°")

    def _pick_eye_color(self) -> None:
        initial = QColor(*(self._eye_color or (255, 255, 255)))
        color = QColorDialog.getColor(initial, self, "Couleur des yeux LED")
        if color.isValid():
            self._eye_color = (color.red(), color.green(), color.blue())
            self._eye_preview.setStyleSheet(
                f"background-color: rgb({color.red()},{color.green()},{color.blue()}); "
                f"border: 1px solid #555; border-radius: 4px;"
            )
            self._eye_btn.setText(f"({color.red()}, {color.green()}, {color.blue()})")

    def _get_current_keyframe(self) -> Keyframe:
        """Construit un Keyframe a partir des valeurs actuelles des sliders."""
        kf = Keyframe()
        for jname, slider in self._sliders.items():
            kf.joints[jname] = slider.value()
        kf.move_time = self._speed_spin.value()
        kf.eye_color = self._eye_color
        return kf

    def _on_send_to_robot(self) -> None:
        kf = self._get_current_keyframe()
        self.send_position_requested.emit(kf.joints, kf.move_time)

    def _on_reset_sliders(self) -> None:
        for slider in self._sliders.values():
            slider.setValue(0)
        self._eye_color = None
        self._eye_preview.setStyleSheet("background-color: #333; border: 1px solid #555; border-radius: 4px;")
        self._eye_btn.setText("Choisir couleur")

    def _on_add_keyframe(self) -> None:
        kf = self._get_current_keyframe()
        self._keyframes.append(kf)
        self._add_keyframe_to_table(kf, len(self._keyframes))

    def _on_return_neutral(self) -> None:
        self.return_neutral_requested.emit()

    def _add_keyframe_to_table(self, kf: Keyframe, index: int) -> None:
        row = self._timeline_table.rowCount()
        self._timeline_table.insertRow(row)

        # #
        item_idx = QTableWidgetItem(f"KF{index}")
        item_idx.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item_idx.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        item_idx.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self._timeline_table.setItem(row, 0, item_idx)

        # Angles pour chaque joint
        for col, jname in enumerate(JOINT_NAMES, start=1):
            val = kf.joints.get(jname, 0)
            item = QTableWidgetItem(str(val))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setFont(QFont("Consolas", 9))
            if val != 0:
                color = _JOINT_COLORS.get(jname, "#aaa")
                item.setForeground(QColor(color))
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._timeline_table.setItem(row, col, item)

        # Vitesse (ms)
        item_time = QTableWidgetItem(f"{kf.move_time}")
        item_time.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item_time.setFont(QFont("Consolas", 9))
        item_time.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self._timeline_table.setItem(row, len(JOINT_NAMES) + 1, item_time)

        # Yeux
        if kf.eye_color:
            r, g, b = kf.eye_color
            eye_item = QTableWidgetItem("")
            eye_item.setBackground(QColor(r, g, b))
            eye_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        else:
            eye_item = QTableWidgetItem("-")
            eye_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            eye_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self._timeline_table.setItem(row, len(JOINT_NAMES) + 2, eye_item)

        # Bouton Supprimer
        btn_del = QPushButton("✕")
        btn_del.setFixedSize(28, 28)
        btn_del.setStyleSheet(
            "QPushButton { background-color: #d9534f; color: white; border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background-color: #c9302c; }"
        )
        btn_del.clicked.connect(lambda _, r=row: self._on_delete_keyframe(r))
        self._timeline_table.setCellWidget(row, len(JOINT_NAMES) + 3, btn_del)

    def _on_delete_keyframe(self, row: int) -> None:
        if 0 <= row < len(self._keyframes):
            self._keyframes.pop(row)
            self._rebuild_timeline_table()

    def _rebuild_timeline_table(self) -> None:
        self._timeline_table.setRowCount(0)
        for i, kf in enumerate(self._keyframes):
            self._add_keyframe_to_table(kf, i + 1)

    def _on_clear_timeline(self) -> None:
        self._keyframes.clear()
        self._timeline_table.setRowCount(0)

    def _on_play(self) -> None:
        if self._keyframes:
            self.play_requested.emit(list(self._keyframes))

    def _on_save_dance(self) -> None:
        if not self._keyframes:
            return

        # Dossier par défaut : dances/ dans le projet
        default_dir = Path(__file__).resolve().parents[2] / "dances"
        default_dir.mkdir(parents=True, exist_ok=True)

        path, _ = QFileDialog.getSaveFileName(
            self, "Sauvegarder la chorégraphie",
            str(default_dir / f"{self._name_edit.text()}.dance"),
            "Fichiers Dance (*.dance);;Tous (*)"
        )
        if not path:
            return

        dance = DanceFile(
            name=self._name_edit.text(),
            mvs=len(self._keyframes),
            tempo=self._speed_spin.value(),
            keyframes=list(self._keyframes),
        )
        dance.save(Path(path))

    def _on_load_dance(self) -> None:
        default_dir = Path(__file__).resolve().parents[2] / "dances"
        path, _ = QFileDialog.getOpenFileName(
            self, "Charger une chorégraphie",
            str(default_dir),
            "Fichiers Dance (*.dance);;Tous (*)"
        )
        if not path:
            return

        dance = DanceFile.load(Path(path))
        self._name_edit.setText(dance.name)
        self._speed_spin.setValue(dance.tempo)
        self._keyframes = list(dance.keyframes)
        self._rebuild_timeline_table()
