from __future__ import annotations

import threading
from typing import Any

import requests
from PyQt6.QtCore import QObject, pyqtSignal

from botata_client.models.dance_file import DanceFile
from botata_client.utils.logger import log


class JudgeClient(QObject):
    """Client HTTP vers le serveur arbitre."""

    score_updated = pyqtSignal(int)
    session_started = pyqtSignal(str)
    dance_started = pyqtSignal(int)
    log_message = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, base_url: str, parent=None):
        super().__init__(parent)
        self._base_url = base_url.rstrip("/")
        self._rid: str | None = None
        self._lock = threading.Lock()

    def _log(self, message: str) -> None:
        log.info(message)
        self.log_message.emit(message)

    @property
    def rid(self) -> str | None:
        return self._rid

    @property
    def base_url(self) -> str:
        return self._base_url

    def set_base_url(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._rid = None
        self._log(f"Judge server URL mis à jour : {self._base_url}")

    def establish_session(self) -> None:
        """Établit une session avec le serveur arbitre en envoyant /hello."""
        threading.Thread(target=self._establish_session_worker, daemon=True).start()

    def _establish_session_worker(self) -> None:
        """Établit une session et émet session_started si succès."""
        with self._lock:
            if self._rid:
                return
            rid = self._hello_sync()
            if not rid:
                return
            self._rid = rid
            self.session_started.emit(rid)

    def send_step(self, color: str, arm: str, exp: str) -> None:
        """Envoie un pas d'arbitrage : couleur, action bras, expression."""
        threading.Thread(
            target=self._send_step_worker,
            args=(color, arm, exp),
            daemon=True,
        ).start()

    def bye(self) -> None:
        """Notifie le serveur arbitre que la session est terminée."""
        threading.Thread(target=self._bye_worker, daemon=True).start()

    def start_dance(self, dance: DanceFile) -> None:
        """Envoie le contenu du fichier .dance au serveur et démarre la session."""
        threading.Thread(
            target=self._start_dance_worker,
            args=(dance,),
            daemon=True,
        ).start()

    def request_score(self) -> None:
        threading.Thread(target=self._request_score_worker, daemon=True).start()

    def _send_step_worker(self, color: str, arm: str, exp: str) -> None:
        rid = self._ensure_session()
        if not rid:
            return

        data = {
            "rid": rid,
            "col": color,
            "arm": arm,
            "exp": exp,
        }
        response = self._request("POST", "/step", json_data=data)
        if not isinstance(response, dict):
            return

        score = int(response.get("score", response.get("points", 0)))
        self.score_updated.emit(score)
        self._log(f"Judge step response: score={score}")

    def _start_dance_worker(self, dance: DanceFile) -> None:
        rid = self._ensure_session()
        if not rid:
            return

        data = {
            "rid": rid,
            "dance_name": dance.name,
            "dance": dance.to_text(),
        }
        response = self._request("POST", "/start", json_data=data)
        if not isinstance(response, dict):
            return

        nb_steps = int(response.get("steps", response.get("nb_steps", 0)))
        self.dance_started.emit(nb_steps)
        self._log(f"Judge start response: steps={nb_steps}")

    def _request_score_worker(self) -> None:
        rid = self._rid
        if not rid:
            return

        response = self._request("GET", "/score", params={"rid": rid})
        if not isinstance(response, dict):
            return

        score = int(response.get("points", response.get("score", 0)))
        self.score_updated.emit(score)
        self._log(f"Judge score response: score={score}")

    def _ensure_session(self) -> str | None:
        with self._lock:
            if self._rid:
                return self._rid
            rid = self._hello_sync()
            if not rid:
                return None
            self._rid = rid
            self.session_started.emit(rid)
            return rid

    def _hello_sync(self) -> str | None:
        self._log("Judge request: POST /hello")
        response = self._request("POST", "/hello", json_data={})
        if not isinstance(response, dict):
            return None

        rid = str(response.get("rid", "")).strip()
        if rid:
            self._log(f"Judge session started with rid={rid}")
            return rid

        self.error_occurred.emit("Réponse invalide du serveur arbitre lors de HELLO.")
        return None

    def _bye_worker(self) -> None:
        rid = self._rid
        if not rid:
            return

        self._log("Judge request: POST /bye")
        response = self._request("POST", "/bye", json_data={"rid": rid})
        if not isinstance(response, dict):
            return

        self._log(f"Judge bye response received for rid={rid}")
        self._rid = None

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> Any | None:
        try:
            url = f"{self._base_url}{path}"
            response = requests.request(
                method,
                url,
                params=params,
                json=json_data,
                timeout=3.0,
            )
            response.raise_for_status()
            try:
                json_body = response.json()
                self._log(f"Judge response: {method} {url} -> {json_body}")
                return json_body
            except ValueError:
                message = (
                    f"Réponse JSON invalide du serveur arbitre : {response.text}"
                )
                self._log(message)
                self.error_occurred.emit(message)
                return None
        except requests.RequestException as exc:
            message = f"Erreur serveur arbitre : {exc}"
            log.error(message)
            self.error_occurred.emit(message)
            return None
