# Règles ACT : correspondance couleur → expression + mouvement
#
# Codes utilisés :
#   Pas   : 1U = 1 pas avant, 2B = 2 pas arrière
#   Bras  : ALU = bras gauche levé, ARB = bras droit baissé
#   Neutre: XNT = retour position neutre (tous joints à 0)
#   Yeux  : LED RGB via disco_color
#   Sourcils : angle servo eyebrows

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ─── Couleurs standard ────────────────────────────────────────────────

class StandardColor(Enum):
    """Couleurs standard reconnues par le système ACT."""
    R = "Rouge"
    G = "Vert"
    B = "Bleu"
    N = "Noir"

    @property
    def display_name(self) -> str:
        return self.value

    @property
    def rgb(self) -> tuple[int, int, int]:
        """Couleur de référence pour le mapping."""
        return _REFERENCE_COLORS[self]


# Couleurs de référence utilisées par le ColorMapper
_REFERENCE_COLORS: dict[StandardColor, tuple[int, int, int]] = {
    StandardColor.R: (255, 0, 0),
    StandardColor.G: (0, 255, 0),
    StandardColor.B: (0, 0, 255),
    StandardColor.N: (0, 0, 0),
}


# ─── Règle ACT ────────────────────────────────────────────────────────

@dataclass
class ArmAction:
    """Action sur un bras / joint du robot."""
    joint_name: str   # ex: "left arm", "right arm", "eyebrows"
    angle: int        # angle cible en degrés
    move_time: int = 1000  # durée du mouvement en ms

    @property
    def code(self) -> str:
        """Code lisible (ALU, ARB, etc.)."""
        codes = {
            ("left arm", 1): "ALU",   # Arm Left Up
            ("left arm", -1): "ALB",  # Arm Left Down (Below)
            ("right arm", 1): "ARU",  # Arm Right Up
            ("right arm", -1): "ARB", # Arm Right Down (Below)
        }
        direction = 1 if self.angle >= 0 else -1
        return codes.get((self.joint_name, direction), f"{self.joint_name}:{self.angle}")


@dataclass
class StepAction:
    """Action de marche."""
    num_steps: int = 1
    step_length: int = 25  # positif = avant, négatif = arrière

    @property
    def code(self) -> str:
        """Code lisible (1U, 2B, etc.)."""
        direction = "U" if self.step_length >= 0 else "B"
        return f"{self.num_steps}{direction}"


@dataclass
class ActRule:
    """Règle ACT complète : couleur → expression + mouvement."""
    color: StandardColor
    eye_color: tuple[int, int, int]     # RGB pour les LED yeux
    eyebrow_angle: int                   # angle servo sourcils
    arm_actions: list[ArmAction] = field(default_factory=list)
    step_action: Optional[StepAction] = None

    @property
    def description(self) -> str:
        """Description lisible de la règle."""
        parts = [f"Yeux={self.eye_color}", f"Sourcils={self.eyebrow_angle}°"]
        for arm in self.arm_actions:
            parts.append(arm.code)
        if self.step_action:
            parts.append(self.step_action.code)
        return " | ".join(parts)


# ─── Règles ACT par défaut ────────────────────────────────────────────

DEFAULT_ACT_RULES: dict[StandardColor, ActRule] = {
    StandardColor.R: ActRule(
        color=StandardColor.R,
        eye_color=(255, 0, 0),
        eyebrow_angle=-30,          # expression colère
        arm_actions=[
            ArmAction("left arm", 90, 1000),   # ALU
        ],
        step_action=StepAction(1, 25),         # 1U
    ),
    StandardColor.G: ActRule(
        color=StandardColor.G,
        eye_color=(0, 255, 0),
        eyebrow_angle=30,           # expression content
        arm_actions=[
            ArmAction("right arm", -90, 1000), # ARB
        ],
        step_action=StepAction(2, -25),        # 2B
    ),
    StandardColor.B: ActRule(
        color=StandardColor.B,
        eye_color=(0, 0, 255),
        eyebrow_angle=50,           # expression surpris
        arm_actions=[
            ArmAction("left arm", 90, 1000),   # ALU
            ArmAction("right arm", -90, 1000), # ARB
        ],
        step_action=StepAction(1, 25),         # 1U
    ),
    StandardColor.N: ActRule(
        color=StandardColor.N,
        eye_color=(255, 255, 255),
        eyebrow_angle=0,            # neutre
        arm_actions=[],             # XNT uniquement
        step_action=None,           # pas de marche
    ),
}


# ─── ColorMapper ──────────────────────────────────────────────────────

class ColorMapper:
    """Convertit une couleur brute RGB en StandardColor.

    Utilise la distance euclidienne dans l'espace RGB pour trouver
    la couleur de référence la plus proche, avec un seuil de tolérance.
    """

    def __init__(self, tolerance: float = 120.0):
        self.tolerance = tolerance

    @staticmethod
    def _distance(c1: tuple[int, int, int], c2: tuple[int, int, int]) -> float:
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(c1, c2)))

    def map_color(self, rgb: tuple[int, int, int] | list[int]) -> StandardColor:
        """Mappe une couleur brute RGB vers une StandardColor.

        Retourne StandardColor.N si aucune couleur n'est assez proche.
        """
        if isinstance(rgb, list):
            rgb = tuple(rgb[:3])

        best_color = StandardColor.N
        best_dist = float("inf")

        for std_color, ref_rgb in _REFERENCE_COLORS.items():
            dist = self._distance(rgb, ref_rgb)
            if dist < best_dist:
                best_dist = dist
                best_color = std_color

        return best_color

    def map_color_with_confidence(
        self, rgb: tuple[int, int, int] | list[int]
    ) -> tuple[StandardColor, float]:
        """Mappe avec un score de confiance (0.0 = loin, 1.0 = exact)."""
        if isinstance(rgb, list):
            rgb = tuple(rgb[:3])

        best_color = StandardColor.N
        best_dist = float("inf")

        for std_color, ref_rgb in _REFERENCE_COLORS.items():
            dist = self._distance(rgb, ref_rgb)
            if dist < best_dist:
                best_dist = dist
                best_color = std_color

        # Confiance : 1.0 quand dist=0, décroît vers 0 à max_dist (~441 = sqrt(255²*3))
        max_dist = 441.67
        confidence = max(0.0, 1.0 - (best_dist / max_dist))
        return best_color, round(confidence, 3)
