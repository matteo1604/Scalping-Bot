"""Scrittura e lettura del file di stato del bot.

Responsabilita':
- Scrivere lo stato corrente in formato JSON (atomicamente)
- Leggere lo stato precedente per recovery dopo crash
"""

from __future__ import annotations

import json
import os
import tempfile

from src.utils.logger import setup_logger

logger = setup_logger("status")


class StatusWriter:
    """Gestore del file di stato JSON del bot.

    Scrive lo stato ad ogni tick (overwrite atomico) e lo legge per recovery.

    Args:
        output_path: Path del file di stato JSON.
    """

    def __init__(self, output_path: str = "data/paper_status.json") -> None:
        self._path = output_path

    def write(self, data: dict) -> None:
        """Scrive lo stato corrente su file JSON.

        Usa scrittura atomica: scrive su file temporaneo, poi rinomina.

        Args:
            data: Dizionario con lo stato corrente del bot.
        """
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        dir_name = os.path.dirname(self._path) or "."
        tmp_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2, default=str)
            os.replace(tmp_path, self._path)
        except Exception:
            logger.exception("Errore scrittura status file")
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def read(self) -> dict | None:
        """Legge lo stato precedente dal file JSON.

        Returns:
            Dict con lo stato, o None se il file non esiste o e' corrotto.
        """
        if not os.path.exists(self._path):
            return None
        try:
            with open(self._path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            logger.warning("Status file corrotto o illeggibile: %s", self._path)
            return None
