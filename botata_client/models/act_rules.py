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
from typing import Optional, Any


# ─── Couleurs standard ────────────────────────────────────────────────

class StandardColor(Enum):
    """Couleurs standard reconnues par le système ACT."""
    R = "Rouge"
    O = "Orange"
    Y = "Jaune"
    G = "Vert"
    B = "Bleu"
    I = "Indigo"
    V = "Violet"
    N = "Noir"
    W = "Blanc"

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
    StandardColor.O: (255, 165, 0),
    StandardColor.Y: (255, 255, 0),
    StandardColor.G: (0, 255, 0),
    StandardColor.B: (0, 0, 255),
    StandardColor.I: (75, 0, 130),
    StandardColor.V: (238, 130, 238),
    StandardColor.N: (0, 0, 0),
    StandardColor.W: (255, 255, 255),
}

# ─── Mapping Expression → Couleur des yeux ────────────────────────────

EXPRESSION_EYE_COLORS: dict[str, tuple[int, int, int]] = {
    "XNT": (0, 0, 0),           # Air neutre : Éteints
    "XSD": (0, 0, 255),         # Air triste : Bleus
    "XNG": (255, 0, 0),         # Air énervé : Rouges
    "XHP": (0, 255, 0),         # Air content : Verts
    "XDN": (255, 165, 0),       # Air enjoué : Arc-en-ciel (orange comme approximation)
}

def get_eye_color_for_expression(expression_code: str) -> tuple[int, int, int]:
    """Retourne la couleur des yeux pour un code d'expression."""
    return EXPRESSION_EYE_COLORS.get(expression_code, (0, 0, 0))

def init_references(config: Any) -> None:
    """Initialise les couleurs de référence depuis la configuration."""
    for std_color in StandardColor:
        if std_color.name in config.color.references:
            rgb = config.color.references[std_color.name]
            _REFERENCE_COLORS[std_color] = tuple(rgb)

def update_reference_color(std_color: StandardColor, rgb: tuple[int, int, int]) -> None:
    """Met à jour une couleur de référence en mémoire."""
    _REFERENCE_COLORS[std_color] = rgb


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
# Règle ACT par défaut par couleur
DEFAULT_ACT_RULES: dict[StandardColor, ActRule] = {
    StandardColor.R: ActRule(
        color=StandardColor.R, eye_color=(255, 0, 0), eyebrow_angle=20,
        arm_actions=[ArmAction("left arm", -90)], step_action=StepAction(1, 25)
    ),
    StandardColor.O: ActRule(
        color=StandardColor.O, eye_color=(255, 165, 0), eyebrow_angle=10,
        arm_actions=[], step_action=StepAction(2, 25)
    ),
    StandardColor.Y: ActRule(
        color=StandardColor.Y, eye_color=(255, 255, 0), eyebrow_angle=0,
        arm_actions=[], step_action=StepAction(1, 0)
    ),
    StandardColor.G: ActRule(
        color=StandardColor.G, eye_color=(0, 255, 0), eyebrow_angle=0,
        arm_actions=[ArmAction("right arm", -90)], step_action=StepAction(1, -25)
    ),
    StandardColor.B: ActRule(
        color=StandardColor.B, eye_color=(0, 0, 255), eyebrow_angle=-20,
        arm_actions=[ArmAction("left arm", 90), ArmAction("right arm", 90)], step_action=StepAction(1, 0)
    ),
    StandardColor.I: ActRule(
        color=StandardColor.I, eye_color=(75, 0, 130), eyebrow_angle=-10,
        arm_actions=[], step_action=StepAction(1, 25)
    ),
    StandardColor.V: ActRule(
        color=StandardColor.V, eye_color=(238, 130, 238), eyebrow_angle=0,
        arm_actions=[], step_action=StepAction(2, -25)
    ),
    StandardColor.N: ActRule(
        color=StandardColor.N,
        eye_color=(255, 255, 255),
        eyebrow_angle=0,            # neutre
        arm_actions=[],             # XNT uniquement
        step_action=None,           # pas de marche
    ),
    StandardColor.W: ActRule(
        color=StandardColor.W,
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
