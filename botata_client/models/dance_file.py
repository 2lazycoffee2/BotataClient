# Modèle de fichier .dance — format texte pour chorégraphies Marty V2
#
# Structure :
#   NAME: ...
#   MVS: ...
#   TEMPO: ...
#   SEQ: R, G, B, ...
#   ACT: (règles par couleur)
#   KEYFRAMES: (positions articulaires)

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# Articulations disponibles sur Marty V2
JOINT_NAMES: list[str] = [
    "left hip", "right hip",
    "left twist", "right twist",
    "left knee", "right knee",
    "left arm", "right arm",
    "eyes",
]

JOINT_IDS: dict[str, int] = {name: i for i, name in enumerate(JOINT_NAMES)}


@dataclass
class Keyframe:
    """Une position articulaire complète du robot a un instant donne."""
    joints: dict[str, int] = field(default_factory=lambda: {j: 0 for j in JOINT_NAMES})
    move_time: int = 800          # duree du mouvement en ms
    eye_color: tuple[int, int, int] | None = None  # RGB optionnel pour les LED yeux

    def copy(self) -> Keyframe:
        return Keyframe(
            joints=dict(self.joints),
            move_time=self.move_time,
            eye_color=self.eye_color,
        )

    def to_line(self) -> str:
        """Serialise en une ligne de texte."""
        parts = []
        for jname in JOINT_NAMES:
            key = jname.replace(" ", "_")
            parts.append(f"{key}={self.joints.get(jname, 0)}")
        parts.append(f"time={self.move_time}")
        if self.eye_color:
            r, g, b = self.eye_color
            parts.append(f"eyes_rgb=({r},{g},{b})")
        # Joints separated by space, time after pipe
        joint_parts = [p for p in parts if not p.startswith("time=") and not p.startswith("eyes_rgb=")]
        meta_parts = [p for p in parts if p.startswith("time=") or p.startswith("eyes_rgb=")]
        return " ".join(joint_parts) + " | " + " ".join(meta_parts)

    @classmethod
    def from_line(cls, line: str) -> Keyframe:
        """Parse une ligne de texte en Keyframe."""
        kf = cls()

        # Separer joints et metadata par le pipe
        if "|" in line:
            joint_part, meta_part = line.split("|", 1)
        else:
            joint_part = line
            meta_part = ""

        # Parser les joints
        for token in joint_part.strip().split():
            if "=" in token:
                key, val = token.split("=", 1)
                joint_name = key.replace("_", " ")
                if joint_name in JOINT_NAMES:
                    try:
                        kf.joints[joint_name] = int(val)
                    except ValueError:
                        pass

        # Parser les metadata
        for token in meta_part.strip().split():
            if token.startswith("time="):
                try:
                    kf.move_time = int(token.split("=", 1)[1])
                except ValueError:
                    pass
            elif token.startswith("eyes_rgb="):
                match = re.search(r"\((\d+),(\d+),(\d+)\)", token)
                if match:
                    kf.eye_color = (int(match.group(1)), int(match.group(2)), int(match.group(3)))

        return kf


@dataclass
class DanceFile:
    """Representation complete d'un fichier .dance."""
    name: str = "Nouvelle Choregraphie"
    mvs: int = 0                                  # nombre total de mouvements
    tempo: int = 500                              # delai entre keyframes (ms)
    seq: list[str] = field(default_factory=list)  # sequence de couleurs ou noms de keyframes
    act_lines: list[str] = field(default_factory=list)  # lignes ACT brutes
    keyframes: list[Keyframe] = field(default_factory=list)

    def get_expanded_seq(self) -> list[str]:
        """Retourne la sequence expandee selon MVS.

        Si MVS > len(seq), la sequence boucle.
        Si MVS == 0 ou seq vide, retourne seq tel quel.
        """
        if not self.seq or self.mvs <= 0:
            return list(self.seq)

        expanded = []
        for i in range(self.mvs):
            expanded.append(self.seq[i % len(self.seq)])
        return expanded

    def to_text(self) -> str:
        """Serialise le DanceFile en texte .dance."""
        lines = [
            "# Fichier .dance - Botata Client",
            f"NAME: {self.name}",
            f"MVS: {self.mvs}",
            f"TEMPO: {self.tempo}",
            "",
        ]

        if self.seq:
            lines.append(f"SEQ: {', '.join(self.seq)}")
            lines.append("")

        if self.act_lines:
            lines.append("ACT:")
            for act_line in self.act_lines:
                lines.append(f"  {act_line}")
            lines.append("")

        if self.keyframes:
            lines.append("KEYFRAMES:")
            for i, kf in enumerate(self.keyframes, 1):
                lines.append(f"  KF{i}: {kf.to_line()}")
            lines.append("")

        return "\n".join(lines)

    def save(self, path: Path) -> None:
        """Sauvegarde le fichier .dance."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_text(), encoding="utf-8")

    @classmethod
    def from_text(cls, text: str) -> DanceFile:
        """Parse le contenu texte d'un fichier .dance."""
        dance = cls()
        section = None  # "ACT" ou "KEYFRAMES"

        for raw_line in text.splitlines():
            line = raw_line.strip()

            # Commentaires et lignes vides
            if not line or line.startswith("#"):
                continue

            # En-tete
            if line.startswith("NAME:"):
                dance.name = line.split(":", 1)[1].strip()
                section = None
                continue
            if line.startswith("MVS:"):
                try:
                    dance.mvs = int(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
                section = None
                continue
            if line.startswith("TEMPO:"):
                try:
                    dance.tempo = int(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
                section = None
                continue
            if line.startswith("SEQ:"):
                seq_str = line.split(":", 1)[1].strip()
                dance.seq = [s.strip() for s in seq_str.split(",") if s.strip()]
                section = None
                continue

            # Sections
            if line == "ACT:":
                section = "ACT"
                continue
            if line == "KEYFRAMES:":
                section = "KEYFRAMES"
                continue

            # Contenu des sections
            if section == "ACT":
                dance.act_lines.append(line)
            elif section == "KEYFRAMES":
                # Enlever le prefixe KFn:
                kf_match = re.match(r"KF\d+:\s*(.*)", line)
                if kf_match:
                    dance.keyframes.append(Keyframe.from_line(kf_match.group(1)))
                else:
                    dance.keyframes.append(Keyframe.from_line(line))

        return dance

    @classmethod
    def load(cls, path: Path) -> DanceFile:
        """Charge un fichier .dance depuis le disque."""
        text = path.read_text(encoding="utf-8")
        dance = cls.from_text(text)
        if dance.name == "Nouvelle Choregraphie":
            dance.name = path.stem
        return dance
