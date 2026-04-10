"""Risk management: stop-loss, take-profit, position sizing.

Responsabilita':
- Calcolare SL/TP dinamici (ATR-based) con fallback percentuale
- Trailing stop ATR-based
- Position sizing a rischio fisso con modulazione sentiment
- Limiti giornalieri (max loss, max trades)
"""

from __future__ import annotations

from config.settings import (
    LOSS_COOLDOWN_BASE_CANDLES,
    LOSS_COOLDOWN_MAX_CANDLES,
    LOSS_COOLDOWN_MULTIPLIER,
    MAX_CONSECUTIVE_LOSSES,
    MAX_DAILY_LOSS_PCT,
    MAX_DAILY_TRADES,
    MAX_POSITION_SIZE_PCT,
    MIN_ORDER_SIZE_USDT,
    RISK_PER_TRADE_PCT,
    SL_ATR_MULTIPLIER,
    STOP_LOSS_PCT,
    TAKE_PROFIT_PCT,
    TP_ATR_MULTIPLIER,
    TRAILING_ATR_MULTIPLIER,
)
from typing import TYPE_CHECKING

from src.utils.logger import setup_logger

if TYPE_CHECKING:
    from src.sentiment.claude_sentiment import SentimentResult

logger = setup_logger("risk")


class RiskManager:
    """Gestore del rischio per il bot di scalping.

    Calcola livelli SL/TP/trailing basati su ATR, position sizing
    a rischio fisso, e applica limiti giornalieri.

    Args:
        risk_per_trade_pct: Percentuale del capitale rischiata per trade.
        sl_atr_multiplier: Moltiplicatore ATR per stop-loss.
        tp_atr_multiplier: Moltiplicatore ATR per take-profit.
        trailing_atr_multiplier: Moltiplicatore ATR per trailing stop.
        max_position_size_pct: Cap massimo position size come % del capitale.
        min_order_size: Ordine minimo in USDT.
        max_daily_trades: Numero massimo di trade giornalieri.
        max_daily_loss_pct: Perdita massima giornaliera come % del capitale.
        stop_loss_pct: Fallback SL percentuale (senza ATR).
        take_profit_pct: Fallback TP percentuale (senza ATR).
        loss_cooldown_base: Candele di cooldown dopo la prima loss.
        loss_cooldown_multiplier: Moltiplicatore progressivo del cooldown.
        loss_cooldown_max: Cap massimo candele di cooldown.
        max_consecutive_losses: Loss consecutive prima dello streak stop.
    """

    def __init__(
        self,
        risk_per_trade_pct: float = RISK_PER_TRADE_PCT,
        sl_atr_multiplier: float = SL_ATR_MULTIPLIER,
        tp_atr_multiplier: float = TP_ATR_MULTIPLIER,
        trailing_atr_multiplier: float = TRAILING_ATR_MULTIPLIER,
        max_position_size_pct: float = MAX_POSITION_SIZE_PCT,
        min_order_size: float = MIN_ORDER_SIZE_USDT,
        max_daily_trades: int = MAX_DAILY_TRADES,
        max_daily_loss_pct: float = MAX_DAILY_LOSS_PCT,
        stop_loss_pct: float = STOP_LOSS_PCT,
        take_profit_pct: float = TAKE_PROFIT_PCT,
        loss_cooldown_base: int = LOSS_COOLDOWN_BASE_CANDLES,
        loss_cooldown_multiplier: float = LOSS_COOLDOWN_MULTIPLIER,
        loss_cooldown_max: int = LOSS_COOLDOWN_MAX_CANDLES,
        max_consecutive_losses: int = MAX_CONSECUTIVE_LOSSES,
    ) -> None:
        self.risk_per_trade_pct = risk_per_trade_pct
        self.sl_atr_multiplier = sl_atr_multiplier
        self.tp_atr_multiplier = tp_atr_multiplier
        self.trailing_atr_multiplier = trailing_atr_multiplier
        self.max_position_size_pct = max_position_size_pct
        self.min_order_size = min_order_size
        self.max_daily_trades = max_daily_trades
        self.max_daily_loss_pct = max_daily_loss_pct
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct

        # Contatori giornalieri
        self._daily_trades: int = 0
        self._daily_pnl: float = 0.0

        # Loss cooldown
        self.loss_cooldown_base = loss_cooldown_base
        self.loss_cooldown_multiplier = loss_cooldown_multiplier
        self.loss_cooldown_max = loss_cooldown_max
        self.max_consecutive_losses = max_consecutive_losses
        self._consecutive_losses: int = 0
        self._cooldown_remaining: int = 0
        self._streak_stopped: bool = False  # True se 5+ loss → stop giornaliero

    def calculate_levels(
        self,
        entry_price: float,
        side: str,
        atr: float | None = None,
    ) -> dict[str, float]:
        """Calcola stop-loss, take-profit e trailing stop per un trade.

        Se ATR e' disponibile (> 0), usa moltiplicatori ATR.
        Altrimenti usa percentuali fisse come fallback.

        Args:
            entry_price: Prezzo di ingresso.
            side: "LONG" o "SHORT".
            atr: Average True Range corrente (None per fallback).

        Returns:
            Dict con chiavi "stop_loss", "take_profit", "trailing_stop".
        """
        if side not in ("LONG", "SHORT"):
            raise ValueError(f"Invalid side: {side!r}. Must be 'LONG' or 'SHORT'.")

        if atr is not None and atr > 0:
            sl_dist = atr * self.sl_atr_multiplier
            tp_dist = atr * self.tp_atr_multiplier
            trail_dist = atr * self.trailing_atr_multiplier
        else:
            sl_dist = entry_price * self.stop_loss_pct / 100.0
            tp_dist = entry_price * self.take_profit_pct / 100.0
            trail_dist = sl_dist  # trailing = SL distance as fallback

        if side == "LONG":
            sl = entry_price - sl_dist
            tp = entry_price + tp_dist
            trailing = entry_price - trail_dist
        else:  # SHORT
            sl = entry_price + sl_dist
            tp = entry_price - tp_dist
            trailing = entry_price + trail_dist

        logger.debug(
            "Levels %s @ %.2f: SL=%.2f TP=%.2f Trail=%.2f",
            side, entry_price, sl, tp, trailing,
        )
        return {"stop_loss": sl, "take_profit": tp, "trailing_stop": trailing}

    def calculate_position_size(
        self,
        capital: float,
        entry_price: float,
        sl_price: float,
        sentiment: SentimentResult | None = None,
    ) -> float:
        """Calcola la dimensione della posizione in USDT.

        Usa il metodo del rischio fisso: rischia una % fissa del capitale per trade.
        La size e' inversamente proporzionale alla distanza dello SL.
        Il sentiment modula la size tramite confidence (clamp [0.5, 1.0]).

        Args:
            capital: Capitale disponibile in USDT.
            entry_price: Prezzo di ingresso.
            sl_price: Prezzo dello stop-loss.
            sentiment: Risultato sentiment (opzionale).

        Returns:
            Size in USDT. 0.0 se sotto il minimo exchange o input invalidi.
        """
        if capital <= 0 or entry_price <= 0:
            return 0.0

        sl_distance = abs(entry_price - sl_price) / entry_price
        if sl_distance == 0:
            return 0.0

        confidence_multiplier = 1.0
        if sentiment is not None:
            confidence_multiplier = max(0.5, min(1.0, sentiment.confidence))

        raw_size = (capital * self.risk_per_trade_pct / 100.0) * confidence_multiplier / sl_distance
        size = min(raw_size, capital * self.max_position_size_pct / 100.0)

        if size < self.min_order_size:
            return 0.0

        logger.debug(
            "Position size: %.2f USDT (capital=%.0f, sl_dist=%.4f, conf=%.2f)",
            size, capital, sl_distance, confidence_multiplier,
        )
        return size

    def update_trailing_stop(
        self,
        side: str,
        current_price: float,
        current_trailing: float,
        atr: float,
    ) -> float:
        """Aggiorna il trailing stop in base al prezzo corrente.

        Il trailing si muove solo a favore della posizione:
        - LONG: sale (max) ma mai scende
        - SHORT: scende (min) ma mai sale

        Args:
            side: "LONG" o "SHORT".
            current_price: Prezzo di mercato corrente.
            current_trailing: Trailing stop attuale.
            atr: Average True Range corrente.

        Returns:
            Nuovo trailing stop price.
        """
        if side not in ("LONG", "SHORT"):
            raise ValueError(f"Invalid side: {side!r}. Must be 'LONG' or 'SHORT'.")

        trail_dist = atr * self.trailing_atr_multiplier

        if side == "LONG":
            candidate = current_price - trail_dist
            return max(candidate, current_trailing)
        else:  # SHORT
            candidate = current_price + trail_dist
            return min(candidate, current_trailing)

    def can_trade(self, capital: float) -> bool:
        """Verifica se i limiti giornalieri consentono un nuovo trade.

        Controlla: trade giornalieri, perdita giornaliera, cooldown, streak stop.

        Args:
            capital: Capitale corrente in USDT.

        Returns:
            True se il trade e' consentito.
        """
        if capital <= 0:
            return False

        if self._streak_stopped:
            logger.debug("Trading sospeso: streak stop attivo (%d loss consecutive)", self._consecutive_losses)
            return False

        if self._cooldown_remaining > 0:
            logger.debug("Trading in cooldown: %d candele rimanenti", self._cooldown_remaining)
            return False

        if self._daily_trades >= self.max_daily_trades:
            logger.debug("Trading sospeso: max daily trades raggiunto (%d)", self.max_daily_trades)
            return False

        if capital > 0:
            max_loss = capital * self.max_daily_loss_pct / 100.0
            if self._daily_pnl <= -max_loss:
                logger.debug("Trading sospeso: max daily loss raggiunto (%.2f)", self._daily_pnl)
                return False

        return True

    def record_trade(self, pnl: float) -> None:
        """Registra un trade completato per il tracking giornaliero.

        Args:
            pnl: Profitto/perdita del trade in USDT.
        """
        self._daily_trades += 1
        self._daily_pnl += pnl
        logger.debug("Trade #%d registrato: PnL=%.2f, Totale=%.2f",
                      self._daily_trades, pnl, self._daily_pnl)

    def record_trade_result(self, pnl: float) -> None:
        """Registra il risultato di un trade e aggiorna il cooldown.

        Se il trade e' in perdita, incrementa le loss consecutive e attiva il cooldown.
        Se il trade e' in profitto, resetta le loss consecutive e il cooldown.

        Args:
            pnl: Profitto/perdita del trade.
        """
        if pnl < 0:
            self._consecutive_losses += 1

            if self._consecutive_losses >= self.max_consecutive_losses:
                self._streak_stopped = True
                logger.warning(
                    "STREAK STOP: %d loss consecutive, trading sospeso per la giornata",
                    self._consecutive_losses,
                )
            else:
                # Cooldown progressivo: base × multiplier^(losses-1)
                cooldown = int(
                    self.loss_cooldown_base
                    * (self.loss_cooldown_multiplier ** (self._consecutive_losses - 1))
                )
                self._cooldown_remaining = min(cooldown, self.loss_cooldown_max)
                logger.info(
                    "Loss #%d consecutiva — cooldown %d candele (%.0f min)",
                    self._consecutive_losses,
                    self._cooldown_remaining,
                    self._cooldown_remaining * 5,
                )
        else:
            if self._consecutive_losses > 0:
                logger.info(
                    "Win dopo %d loss consecutive — cooldown resettato",
                    self._consecutive_losses,
                )
            self._consecutive_losses = 0
            self._cooldown_remaining = 0

    def tick_cooldown(self) -> None:
        """Decrementa il cooldown di 1 candela. Chiamato ad ogni tick."""
        if self._cooldown_remaining > 0:
            self._cooldown_remaining -= 1
            if self._cooldown_remaining == 0:
                logger.info("Cooldown terminato — trading riabilitato")

    @property
    def consecutive_losses(self) -> int:
        """Numero di loss consecutive correnti."""
        return self._consecutive_losses

    @property
    def cooldown_remaining(self) -> int:
        """Candele di cooldown rimanenti."""
        return self._cooldown_remaining

    @property
    def streak_stopped(self) -> bool:
        """True se il trading e' sospeso per streak di loss."""
        return self._streak_stopped

    def reset_daily(self) -> None:
        """Resetta tutti i contatori giornalieri."""
        logger.info("Daily reset: contatori e cooldown azzerati")
        self._daily_trades = 0
        self._daily_pnl = 0.0
        self._consecutive_losses = 0
        self._cooldown_remaining = 0
        self._streak_stopped = False
