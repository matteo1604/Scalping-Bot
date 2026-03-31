"""Notifiche Slack via webhook.

Responsabilita':
- Inviare messaggi al canale Slack configurato
- Non bloccare il bot in caso di errori di rete
- Disabilitarsi silenziosamente se il webhook non e' configurato
"""

from __future__ import annotations

import json
from urllib.request import Request, urlopen

from src.utils.logger import setup_logger

logger = setup_logger("notifier")

_LEVEL_PREFIX = {
    "info": "[INFO]",
    "warning": "[WARNING]",
    "error": "[ERROR]",
}


class SlackNotifier:
    """Invia notifiche a Slack via webhook.

    Se il webhook URL e' vuoto, tutte le chiamate sono silenziosamente ignorate.

    Args:
        webhook_url: URL del webhook Slack.
    """

    def __init__(self, webhook_url: str = "") -> None:
        self._url = webhook_url
        self.enabled = bool(webhook_url)

    def notify(self, message: str, level: str = "info") -> None:
        """Invia un messaggio a Slack.

        Non propaga eccezioni: logga l'errore e continua.

        Args:
            message: Testo del messaggio.
            level: Livello del messaggio ("info", "warning", "error").
        """
        if not self.enabled:
            return

        prefix = _LEVEL_PREFIX.get(level, "[INFO]")
        text = f"{prefix} {message}"

        payload = json.dumps({"text": text}).encode("utf-8")
        request = Request(
            self._url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=10) as response:
                response.read()
            logger.debug("Slack notifica inviata: %s", text)
        except Exception:
            logger.warning("Errore invio notifica Slack: %s", text)
