"""Logging strutturato per il bot.

Configura logging con output su file (logs/) e console.
Formato: timestamp | livello | modulo | messaggio.
"""

import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logger(
    name: str,
    level: str = "INFO",
    log_dir: str = "logs",
) -> logging.Logger:
    """Crea e configura un logger con output su console e file.

    Args:
        name: Nome del logger.
        level: Livello di logging (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_dir: Directory per i file di log.

    Returns:
        Logger configurato.
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Evita duplicazione handler se chiamato più volte
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler
    os.makedirs(log_dir, exist_ok=True)
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, f"{name}.log"),
        maxBytes=5_000_000,  # 5 MB
        backupCount=3,
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
