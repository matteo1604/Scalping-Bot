"""Test per l'entry point del bot."""

from src.main import parse_args


def test_parse_args_default_mode():
    """Senza argomenti, il mode deve essere 'paper'."""
    args = parse_args([])
    assert args.mode == "paper"


def test_parse_args_paper_mode():
    """--mode paper deve impostare mode='paper'."""
    args = parse_args(["--mode", "paper"])
    assert args.mode == "paper"


def test_parse_args_live_mode():
    """--mode live deve impostare mode='live'."""
    args = parse_args(["--mode", "live"])
    assert args.mode == "live"
