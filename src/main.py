"""Entry point del bot di scalping.

Avvia il loop principale del bot in modalita' paper o live.
Gestisce il ciclo: fetch dati -> calcolo indicatori -> segnale -> sentiment -> esecuzione.
"""

from __future__ import annotations

import argparse
import os
import signal
import time
from datetime import date, datetime, timezone

from config.settings import (
    ADX_TREND_THRESHOLD,
    BINANCE_API_KEY,
    BINANCE_API_SECRET,
    HTF_CANDLES,
    HTF_TIMEFRAME,
    KILL_SWITCH_PATH,
    LIVE_CAPITAL_USDT,
    LOG_LEVEL,
    MIN_ORDER_SIZE_USDT,
    SLACK_WEBHOOK_URL,
    SYMBOL,
    TIMEFRAME,
    TRADE_AMOUNT_USDT,
)
from src.exchange import BinanceExchange
from src.indicators.htf_filter import HTFFilter
from src.indicators.technical import add_indicators, add_prev_indicators
from src.risk.manager import RiskManager
from src.sentiment.claude_sentiment import ClaudeSentiment, SentimentResult
from src.strategies.combined import CombinedStrategy
from src.utils.logger import setup_logger
from src.utils.notifier import SlackNotifier
from src.utils.status import StatusWriter

logger = setup_logger("bot", level=LOG_LEVEL)


class TradingLoop:
    """Loop principale del bot di scalping.

    Orchestrare tutti i componenti in un ciclo continuo sincronizzato
    alle candele 5min. Supporta paper trading (nessun ordine reale)
    e live trading.

    Args:
        mode: "paper" o "live".
        status_path: Path del file di stato JSON.
    """

    def __init__(
        self,
        mode: str = "paper",
        status_path: str = "data/paper_status.json",
        kill_switch_path: str = KILL_SWITCH_PATH,
    ) -> None:
        self.mode = mode
        self._running = False
        self._kill_switch_path = kill_switch_path

        # Componenti
        self._exchange = BinanceExchange(
            api_key=BINANCE_API_KEY, api_secret=BINANCE_API_SECRET,
            sandbox=(mode == "paper"),
        )
        self._strategy = CombinedStrategy()
        self._sentiment = ClaudeSentiment()
        self._risk = RiskManager()
        self._status = StatusWriter(output_path=status_path)
        self._notifier = SlackNotifier(webhook_url=SLACK_WEBHOOK_URL)

        # HTF filter
        self._htf_filter = HTFFilter()
        self._htf_data: dict = {"rsi_1h": None, "trend_1h": "NEUTRAL"}

        # Stato posizione
        self._position: dict | None = None
        self._last_signal: str | None = None
        self._last_sentiment: SentimentResult | None = None

        # Contatori giornalieri (paralleli a RiskManager per status file)
        self._daily_trades: int = 0
        self._daily_wins: int = 0
        self._daily_pnl: float = 0.0
        self._last_date: date = date.today()

        # Recovery
        self._recover_position()

    def run(self) -> None:
        """Esegue il loop principale con graceful shutdown."""
        self._running = True
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

        if not self._preflight_checks():
            logger.error("Pre-flight checks falliti — bot non avviato")
            self._running = False
            return

        logger.info("Bot avviato in modalita': %s", self.mode)
        self._notifier.notify("Bot avviato in modalita': %s" % self.mode)

        while self._running:
            try:
                self._wait_for_candle()
                if not self._running:
                    break
                self._tick()
            except Exception:
                logger.exception("Errore nel tick, riprovo al prossimo ciclo")

        logger.info("Bot fermato.")
        self._notifier.notify("Bot fermato")

    def _handle_shutdown(self, signum: int, frame) -> None:
        """Handler per SIGINT/SIGTERM."""
        logger.info("Shutdown richiesto (signal=%d)", signum)
        self._running = False

    def _check_kill_switch(self) -> bool:
        """Controlla se il kill switch file e' presente.

        Returns:
            True se il kill switch e' attivo (bot deve fermarsi).
        """
        if not os.path.exists(self._kill_switch_path):
            return False

        logger.warning("KILL SWITCH attivato: %s", self._kill_switch_path)
        self._notifier.notify("KILL SWITCH attivato — bot fermato", level="warning")

        if self._position is not None:
            logger.warning(
                "Posizione aperta rimasta: %s @ %.2f (size=%.2f USDT)",
                self._position["side"],
                self._position["entry_price"],
                self._position["size_usdt"],
            )
            self._notifier.notify(
                "Posizione aperta rimasta: %s @ %.2f" % (
                    self._position["side"], self._position["entry_price"],
                ),
                level="warning",
            )

        self._running = False
        return True

    def _preflight_checks(self) -> bool:
        """Esegue verifiche di sicurezza prima di avviare il loop live.

        Returns:
            True se tutti i check passano.
        """
        if self.mode != "live":
            return True

        # 1. API keys
        if not BINANCE_API_KEY or not BINANCE_API_SECRET:
            logger.error("Pre-flight FAIL: API keys Binance mancanti")
            return False

        # 2. Connessione exchange e balance
        try:
            balance = self._exchange.get_balance("USDT")
        except Exception:
            logger.exception("Pre-flight FAIL: impossibile connettersi a Binance")
            return False

        # 3. Balance minimo
        if balance < MIN_ORDER_SIZE_USDT:
            logger.error(
                "Pre-flight FAIL: balance %.2f USDT < minimo %.2f USDT",
                balance, MIN_ORDER_SIZE_USDT,
            )
            return False

        # 4. Kill switch
        if os.path.exists(self._kill_switch_path):
            logger.error("Pre-flight FAIL: kill switch gia' attivo (%s)", self._kill_switch_path)
            return False

        # 5. Slack (opzionale)
        if self._notifier.enabled:
            self._notifier.notify("Pre-flight OK — bot in avvio")
        else:
            logger.warning("Slack webhook non configurato — notifiche disabilitate")

        logger.info("Pre-flight checks superati (balance=%.2f USDT)", balance)
        return True

    def _wait_for_candle(self) -> None:
        """Attende la chiusura della prossima candela 5min."""
        now = time.time()
        interval = 300  # 5 minuti
        seconds_to_next = interval - (now % interval) + 5  # 5s buffer
        logger.debug("Attesa prossima candela: %.0f secondi", seconds_to_next)
        # Sleep in blocchi da 1s per controllare _running
        end_time = now + seconds_to_next
        while time.time() < end_time and self._running:
            time.sleep(1)

    def _tick(self) -> None:
        """Esegue un singolo ciclo del bot."""
        if self._check_kill_switch():
            return

        self._check_daily_reset()

        # Fetch dati 1h per filtro multi-timeframe
        try:
            df_1h = self._exchange.fetch_ohlcv(SYMBOL, HTF_TIMEFRAME, limit=HTF_CANDLES)
            self._htf_data = self._htf_filter.compute_indicators(df_1h)
        except Exception:
            logger.warning("Errore fetch 1h, HTF filter disabilitato per questo tick")
            self._htf_data = {"rsi_1h": None, "trend_1h": "NEUTRAL"}

        # Fetch dati
        try:
            df = self._exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, limit=100)
        except Exception:
            logger.exception("Errore fetch OHLCV, skip tick")
            return

        # Indicatori
        df = add_indicators(df)
        df = add_prev_indicators(df)
        df = df.dropna()
        if len(df) < 2:
            logger.warning("Dati insufficienti dopo dropna")
            return

        row = df.iloc[-1]

        # ATR da indicatore (ATR 14-period calcolato da add_indicators)
        atr = row["atr"]

        # Check posizione aperta
        if self._position is not None:
            self._position["trailing_stop"] = self._risk.update_trailing_stop(
                side=self._position["side"],
                current_price=row["close"],
                current_trailing=self._position["trailing_stop"],
                atr=atr,
            )
            self._check_open_position(row)
        else:
            # Genera segnale
            signal_raw = self._strategy.generate_signal(df)
            self._last_signal = signal_raw

            if signal_raw is not None:
                # Sentiment con cooldown
                sentiment = self._sentiment.analyze()
                self._last_sentiment = sentiment

                # Rigenera con filtro sentiment
                signal_filtered = self._strategy.generate_signal(df, sentiment=sentiment)

                if signal_filtered is not None and self._risk.can_trade(
                    capital=LIVE_CAPITAL_USDT,
                ):
                    # Determina il tipo di strategia dal contesto
                    strategy_mode = "trend" if row["adx"] > ADX_TREND_THRESHOLD else "reversion"

                    # Filtro multi-timeframe
                    if not self._htf_filter.allows_signal(signal_filtered, strategy_mode, self._htf_data):
                        self._last_signal = None  # segnale bloccato da HTF
                    else:
                        self._open_position(signal_filtered, row, sentiment, atr)

        # Aggiorna status
        self._write_status(row)

    def _check_open_position(self, row) -> None:
        """Controlla se la posizione aperta ha raggiunto SL/TP/trailing.

        Ordine conservativo: SL -> trailing -> TP.
        Usa high/low della candela per check realistici.

        Args:
            row: Ultima riga del DataFrame con high, low, close.
        """
        pos = self._position
        if pos is None:
            return

        high = row["high"]
        low = row["low"]

        if pos["side"] == "LONG":
            if low <= pos["stop_loss"]:
                self._close_position(row, "stop_loss")
            elif low <= pos["trailing_stop"]:
                self._close_position(row, "trailing_stop")
            elif high >= pos["take_profit"]:
                self._close_position(row, "take_profit")
        else:  # SHORT
            if high >= pos["stop_loss"]:
                self._close_position(row, "stop_loss")
            elif high >= pos["trailing_stop"]:
                self._close_position(row, "trailing_stop")
            elif low <= pos["take_profit"]:
                self._close_position(row, "take_profit")

    def _open_position(self, signal: str, row, sentiment: SentimentResult, atr: float) -> None:
        """Apre una nuova posizione (paper o live).

        Args:
            signal: "LONG" o "SHORT".
            row: Ultima riga del DataFrame.
            sentiment: Risultato sentiment corrente.
            atr: ATR corrente.
        """
        # SHORT ignorato in live (spot only)
        if self.mode == "live" and signal == "SHORT":
            logger.info("SHORT ignorato in live mode (spot only)")
            return

        entry_price = row["close"]

        # Modalità strategia: trend following usa ATR moltiplicatore più ampio
        try:
            adx_val = float(row["adx"])
        except (KeyError, TypeError, ValueError):
            adx_val = 0.0
        strategy_type = "trend" if adx_val > ADX_TREND_THRESHOLD else "mean_reversion"
        effective_atr = atr * 1.5 if strategy_type == "trend" else atr

        # Capitale: balance reale in live, simulato in paper
        if self.mode == "live":
            try:
                capital = self._exchange.get_balance("USDT")
            except Exception:
                logger.exception("Errore fetch balance, skip apertura")
                self._notifier.notify("Errore fetch balance — trade non aperto", level="error")
                return
        else:
            capital = LIVE_CAPITAL_USDT

        levels = self._risk.calculate_levels(entry_price, signal, effective_atr)
        size = self._risk.calculate_position_size(
            capital=capital,
            entry_price=entry_price,
            sl_price=levels["stop_loss"],
            sentiment=sentiment,
        )

        if size == 0.0:
            logger.info("Position size troppo piccola, skip trade")
            return

        # Ordine live
        if self.mode == "live":
            amount_btc = size / entry_price
            try:
                order = self._exchange.create_order(
                    symbol=SYMBOL,
                    side="buy",
                    amount=amount_btc,
                )
                logger.info("Ordine live eseguito: %s", order.get("id"))
            except Exception:
                logger.exception("Errore ordine live — posizione non aperta")
                self._notifier.notify(
                    "ERRORE ordine %s @ %.2f — non aperto" % (signal, entry_price),
                    level="error",
                )
                return

        self._position = {
            "side": signal,
            "strategy": strategy_type,
            "entry_price": entry_price,
            "entry_time": str(row.name),
            "stop_loss": levels["stop_loss"],
            "take_profit": levels["take_profit"],
            "trailing_stop": levels["trailing_stop"],
            "size_usdt": size,
        }

        msg = "APERTA %s @ %.2f | SL=%.2f TP=%.2f Trail=%.2f | Size=%.2f USDT" % (
            signal, entry_price, levels["stop_loss"], levels["take_profit"],
            levels["trailing_stop"], size,
        )
        logger.info(msg)
        self._notifier.notify(msg)

    def _close_position(self, row, reason: str) -> None:
        """Chiude la posizione aperta.

        Args:
            row: Ultima riga del DataFrame.
            reason: "stop_loss", "take_profit", "trailing_stop".
        """
        pos = self._position
        if pos is None:
            return

        exit_price = row["close"]
        entry_price = pos["entry_price"]

        # Ordine live di chiusura
        if self.mode == "live":
            amount_btc = pos["size_usdt"] / entry_price
            try:
                order = self._exchange.create_order(
                    symbol=SYMBOL,
                    side="sell",
                    amount=amount_btc,
                )
                logger.info("Ordine chiusura live eseguito: %s", order.get("id"))
            except Exception:
                logger.exception("Errore ordine chiusura live — posizione resta aperta")
                self._notifier.notify(
                    "ERRORE chiusura %s @ %.2f — posizione resta aperta" % (
                        pos["side"], exit_price,
                    ),
                    level="error",
                )
                return  # NON cancella la posizione

        if pos["side"] == "LONG":
            pnl_pct = ((exit_price - entry_price) / entry_price) * 100.0
        else:
            pnl_pct = ((entry_price - exit_price) / entry_price) * 100.0

        pnl = (pnl_pct / 100.0) * pos["size_usdt"]

        msg = "CHIUSA %s @ %.2f | Reason=%s | PnL=%.2f%% (%.2f USDT)" % (
            pos["side"], exit_price, reason, pnl_pct, pnl,
        )
        logger.info(msg)
        self._notifier.notify(msg)

        self._risk.record_trade(pnl)
        self._daily_trades += 1
        self._daily_pnl += pnl
        if pnl > 0:
            self._daily_wins += 1

        self._position = None

    def _recover_position(self) -> None:
        """Ripristina la posizione aperta dal file di stato."""
        data = self._status.read()
        if data is None:
            return

        pos = data.get("position")
        if pos is not None and isinstance(pos, dict) and "side" in pos:
            self._position = pos
            logger.info("Posizione recuperata: %s @ %.2f", pos["side"], pos["entry_price"])

    def _check_daily_reset(self) -> None:
        """Resetta i contatori se la data e' cambiata."""
        today = date.today()
        if today != self._last_date:
            logger.info("Nuovo giorno: reset contatori giornalieri")
            self._risk.reset_daily()
            self._daily_trades = 0
            self._daily_wins = 0
            self._daily_pnl = 0.0
            self._last_date = today

    def _write_status(self, row) -> None:
        """Scrive il file di stato JSON."""
        pos_data = None
        if self._position is not None:
            entry = self._position["entry_price"]
            current = row["close"]
            if self._position["side"] == "LONG":
                unrealized = ((current - entry) / entry) * 100.0
            else:
                unrealized = ((entry - current) / entry) * 100.0

            pos_data = {**self._position, "unrealized_pnl_pct": round(unrealized, 4)}

        win_rate = 0.0
        if self._daily_trades > 0:
            win_rate = round((self._daily_wins / self._daily_trades) * 100.0, 1)

        sentiment_data = None
        if self._last_sentiment is not None:
            sentiment_data = {
                "score": self._last_sentiment.sentiment_score,
                "confidence": self._last_sentiment.confidence,
                "recommendation": self._last_sentiment.recommendation,
            }

        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": self.mode,
            "position": pos_data,
            "daily": {
                "trades": self._daily_trades,
                "pnl": round(self._daily_pnl, 2),
                "win_rate": win_rate,
            },
            "last_signal": self._last_signal,
            "last_sentiment": sentiment_data,
            "htf": {
                "rsi_1h": self._htf_data.get("rsi_1h"),
                "trend_1h": self._htf_data.get("trend_1h"),
            },
        }

        try:
            self._status.write(data)
        except Exception:
            logger.exception("Errore scrittura status")


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

    if args.mode == "live":
        logger.warning("MODALITA' LIVE - Ordini reali saranno piazzati!")

    loop = TradingLoop(mode=args.mode)
    loop.run()


if __name__ == "__main__":
    main()
