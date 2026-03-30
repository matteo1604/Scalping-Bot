"""Risk management: stop-loss, take-profit, position sizing.

Responsabilita':
- Calcolare SL/TP dinamici (ATR-based) con fallback percentuale
- Trailing stop ATR-based
- Position sizing a rischio fisso con modulazione sentiment
- Limiti giornalieri (max loss, max trades)
"""

from __future__ import annotations

from config.settings import (
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
from src.utils.logger import setup_logger

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
