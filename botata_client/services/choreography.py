# Moteur de chorégraphie — exécution séquentielle des règles ACT
#
# Enchaîne : Expression (yeux LED + sourcils) → Bras → Pas → XNT (neutre)
# Toutes les commandes transitent par RobotConnection.send_command() (thread-safe).

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from botata_client.models.act_rules import ActRule, DEFAULT_ACT_RULES, StandardColor
from botata_client.utils.logger import log

if TYPE_CHECKING:
    from botata_client.services.robot_connection import RobotConnection


class ChoreographyEngine(QObject):
    """Moteur d'exécution des mouvements ACT.

    Exécute les règles ACT de manière séquentielle via des QTimer
    pour ne pas bloquer le thread principal Qt.
    """

    # Signaux
    step_started = pyqtSignal(int, str)       # (index, description)
    step_completed = pyqtSignal(int)           # (index)
    sequence_finished = pyqtSignal()
    neutral_restored = pyqtSignal()
    state_changed = pyqtSignal(str)            # état lisible pour l'UI

    # Délais entre phases (ms)
    EXPRESSION_DELAY = 500
    ARM_DELAY = 1200
    STEP_DELAY = 2000
    NEUTRAL_DELAY = 800

    def __init__(self, connection: RobotConnection, parent=None):
        super().__init__(parent)
        self._connection = connection
        self._rules: list[ActRule] = []
        self._current_index: int = 0
        self._running: bool = False
        self._auto_mode: bool = False
        self._last_color: StandardColor | None = None
        self._phase_timer = QTimer(self)
        self._phase_timer.setSingleShot(True)
        self._phase_timer.timeout.connect(self._next_phase)
        self._current_phase: int = 0  # 0=expression, 1=bras, 2=pas, 3=neutre

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def auto_mode(self) -> bool:
        return self._auto_mode

    @auto_mode.setter
    def auto_mode(self, value: bool) -> None:
        self._auto_mode = value
        log.info(f"Mode auto chorégraphie : {'ON' if value else 'OFF'}")

    # ── API publique ──────────────────────────────────────────────────

    def execute_for_color(self, color: StandardColor) -> None:
        """Exécute la règle ACT correspondant à une couleur."""
        rule = DEFAULT_ACT_RULES.get(color)
        if rule:
            self.execute_act_rule(rule)

    def on_color_detected(self, color: StandardColor) -> None:
        """Appelé par le SensorMonitor quand une couleur est détectée.

        En mode auto, déclenche l'exécution si la couleur a changé.
        """
        if self._auto_mode and color != self._last_color and not self._running:
            self._last_color = color
            self.execute_for_color(color)
        else:
            self._last_color = color

    def execute_act_rule(self, rule: ActRule) -> None:
        """Exécute une règle ACT unique avec enchaînement séquentiel."""
        if self._running:
            log.warning("Chorégraphie déjà en cours, ignoré.")
            return

        self._running = True
        self._current_rule = rule
        self._current_phase = 0
        desc = f"ACT {rule.color.display_name} : {rule.description}"
        self.step_started.emit(0, desc)
        self.state_changed.emit(f"Exécution : {rule.color.display_name}")
        log.info(f"Début chorégraphie : {desc}")
        self._execute_phase()

    def run_sequence(self, rules: list[ActRule]) -> None:
        """Exécute une séquence de règles ACT avec XNT intercalé."""
        if self._running:
            log.warning("Chorégraphie déjà en cours, ignoré.")
            return
        self._rules = list(rules)
        self._current_index = 0
        self._run_next_rule()

    def return_to_neutral(self) -> None:
        """Ramène le robot en position neutre (XNT)."""
        self.state_changed.emit("XNT (retour neutre)")
        log.info("Retour position neutre (XNT)")
        self._connection.send_command("return_neutral", move_time=500)
        # Éteindre les yeux → blanc neutre
        self._connection.send_command(
            "eyes_color", color=(255, 255, 255), add_on="eyes"
        )
        self.neutral_restored.emit()

    def stop(self) -> None:
        """Arrête la chorégraphie en cours."""
        self._phase_timer.stop()
        self._running = False
        self._rules.clear()
        self.state_changed.emit("Arrêté")
        self._connection.send_command("stop")
        log.info("Chorégraphie arrêtée.")

    # ── Exécution séquentielle par phases ─────────────────────────────

    def _execute_phase(self) -> None:
        """Exécute la phase courante de la règle ACT."""
        rule = self._current_rule

        if self._current_phase == 0:
            # Phase 0 : Expression (yeux LED + sourcils)
            self.state_changed.emit(
                f"Expression : yeux={rule.eye_color} sourcils={rule.eyebrow_angle}°"
            )
            self._connection.send_command(
                "eyes_color", color=rule.eye_color, add_on="eyes"
            )
            self._connection.send_command(
                "eyebrows", angle=rule.eyebrow_angle, move_time=500
            )
            self._current_phase = 1
            self._phase_timer.start(self.EXPRESSION_DELAY)

        elif self._current_phase == 1:
            # Phase 1 : Bras (ALU, ARB, etc.)
            if rule.arm_actions:
                arm_codes = " + ".join(a.code for a in rule.arm_actions)
                self.state_changed.emit(f"Bras : {arm_codes}")
                for arm in rule.arm_actions:
                    self._connection.send_command(
                        "move_joint",
                        joint_name=arm.joint_name,
                        angle=arm.angle,
                        move_time=arm.move_time,
                    )
            self._current_phase = 2
            self._phase_timer.start(self.ARM_DELAY)

        elif self._current_phase == 2:
            # Phase 2 : Pas (1U, 2B, etc.)
            if rule.step_action:
                self.state_changed.emit(f"Pas : {rule.step_action.code}")
                self._connection.send_command(
                    "walk",
                    num_steps=rule.step_action.num_steps,
                    step_length=rule.step_action.step_length,
                    move_time=1500,
                )
            self._current_phase = 3
            self._phase_timer.start(self.STEP_DELAY)

        elif self._current_phase == 3:
            # Phase 3 : Retour neutre (XNT)
            self.return_to_neutral()
            self._running = False
            self.step_completed.emit(self._current_index)
            self.state_changed.emit("En attente")
            log.info("Chorégraphie terminée.")

            # Si on est dans une séquence, passer à la règle suivante
            if self._rules:
                self._current_index += 1
                self._phase_timer.start(self.NEUTRAL_DELAY)
                # _next_phase appellera _run_next_rule

    def _next_phase(self) -> None:
        """Callback du QTimer : passe à la phase suivante."""
        if self._running:
            self._execute_phase()
        elif self._rules and self._current_index < len(self._rules):
            self._run_next_rule()
        else:
            if self._rules:
                self._rules.clear()
                self.sequence_finished.emit()
                self.state_changed.emit("Séquence terminée")

    def _run_next_rule(self) -> None:
        """Exécute la prochaine règle dans la séquence."""
        if self._current_index < len(self._rules):
            rule = self._rules[self._current_index]
            self.execute_act_rule(rule)
        else:
            self._rules.clear()
            self.sequence_finished.emit()
            self.state_changed.emit("Séquence terminée")
