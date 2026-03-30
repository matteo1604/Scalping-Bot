"""Entry point del bot di scalping.

Avvia il loop principale del bot in modalità paper o live.
Gestisce il ciclo: fetch dati -> calcolo indicatori -> segnale -> sentiment -> esecuzione.
"""

import argparse

from src.utils.logger import setup_logger
from config.settings import LOG_LEVEL

logger = setup_logger("bot", level=LOG_LEVEL)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parsa gli argomenti della linea di comando.

    Args:
        argv: Lista di argomenti. Se None, usa sys.argv[1:].

    Returns:
        Namespace con gli argomenti parsati.
    """
    parser = argparse.ArgumentParser(description="Scalping Bot - BTC/USDT")
    parser.add_argument(
        "--mode",
        choices=["paper", "live"],
        default="paper",
        help="Modalita' di esecuzione (default: paper)",
    )
    return parser.parse_args(argv)


def main() -> None:
    """Entry point principale del bot."""
    args = parse_args()
    logger.info("Avvio bot in modalita': %s", args.mode)

    if args.mode == "live":
        logger.warning("MODALITA' LIVE - Ordini reali saranno piazzati!")

    # TODO: Fase 2 — Implementare il loop principale del bot
    logger.info("Bot avviato. In attesa di implementazione loop principale (Fase 2).")


if __name__ == "__main__":
    main()
