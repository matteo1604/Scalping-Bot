"""Test per il modulo logger."""

import logging

from src.utils.logger import setup_logger


def test_setup_logger_returns_logger():
    """setup_logger deve restituire un'istanza di logging.Logger."""
    logger = setup_logger("test_bot")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test_bot"


def test_setup_logger_has_console_handler():
    """Il logger deve avere almeno un handler per la console."""
    logger = setup_logger("test_console")
    handler_types = [type(h).__name__ for h in logger.handlers]
    assert "StreamHandler" in handler_types or "RichHandler" in handler_types


def test_setup_logger_has_file_handler(tmp_path):
    """Il logger deve creare un file handler nella directory logs."""
    logger = setup_logger("test_file", log_dir=str(tmp_path))
    handler_types = [type(h).__name__ for h in logger.handlers]
    assert "FileHandler" in handler_types or "RotatingFileHandler" in handler_types


def test_setup_logger_respects_level():
    """Il logger deve rispettare il livello configurato."""
    logger = setup_logger("test_level", level="DEBUG")
    assert logger.level == logging.DEBUG
