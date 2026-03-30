"""Strategia combinata: EMA Crossover + RSI + Volume + Sentiment.

Logica segnali:
- LONG: EMA9 > EMA21 (cross up) + RSI < 70 + Volume > media + Sentiment > threshold
- SHORT: EMA9 < EMA21 (cross down) + RSI > 30 + Volume > media + Sentiment < -threshold
- Il sentiment modifica anche il position sizing
"""

import pandas as pd

from config.settings import RSI_OVERBOUGHT, RSI_OVERSOLD
from src.utils.logger import setup_logger

logger = setup_logger("strategy")


class CombinedStrategy:
    """Strategia di scalping basata su EMA crossover con filtri RSI e Volume.

    Args:
        rsi_overbought: Soglia RSI overbought (default: 70).
        rsi_oversold: Soglia RSI oversold (default: 30).
    """

    def __init__(
        self,
        rsi_overbought: float = RSI_OVERBOUGHT,
        rsi_oversold: float = RSI_OVERSOLD,
    ) -> None:
        self.rsi_overbought = rsi_overbought
        self.rsi_oversold = rsi_oversold

    def generate_signal(self, df: pd.DataFrame) -> str | None:
        """Genera un segnale di trading dall'ultima riga del DataFrame.

        Il DataFrame deve contenere le colonne:
        ema_fast, ema_slow, ema_fast_prev, ema_slow_prev, rsi, volume, volume_ma.

        Args:
            df: DataFrame con indicatori calcolati.

        Returns:
            "LONG", "SHORT", o None se nessun segnale.
        """
        row = df.iloc[-1]

        # Controlla NaN
        required = ["ema_fast", "ema_slow", "ema_fast_prev", "ema_slow_prev",
                     "rsi", "volume", "volume_ma"]
        if any(pd.isna(row.get(col)) for col in required):
            return None

        ema_fast = row["ema_fast"]
        ema_slow = row["ema_slow"]
        ema_fast_prev = row["ema_fast_prev"]
        ema_slow_prev = row["ema_slow_prev"]
        rsi = row["rsi"]
        volume = row["volume"]
        volume_ma = row["volume_ma"]

        # Crossover detection
        bullish_cross = ema_fast_prev <= ema_slow_prev and ema_fast > ema_slow
        bearish_cross = ema_fast_prev >= ema_slow_prev and ema_fast < ema_slow

        # Volume filter
        volume_ok = volume > volume_ma

        # LONG
        if bullish_cross and rsi < self.rsi_overbought and volume_ok:
            logger.info("Segnale LONG: EMA cross up, RSI=%.1f, Vol=%.1f", rsi, volume)
            return "LONG"

        # SHORT
        if bearish_cross and rsi > self.rsi_oversold and volume_ok:
            logger.info("Segnale SHORT: EMA cross down, RSI=%.1f, Vol=%.1f", rsi, volume)
            return "SHORT"

        return None
