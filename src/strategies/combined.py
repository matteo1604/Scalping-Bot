"""Strategia combinata: EMA Crossover + RSI + Volume + Sentiment.

Logica segnali:
- LONG: EMA9 > EMA21 (cross up) + RSI < 70 + Volume > media + Sentiment > threshold
- SHORT: EMA9 < EMA21 (cross down) + RSI > 30 + Volume > media + Sentiment < -threshold
- Il sentiment modifica anche il position sizing
"""

from __future__ import annotations

import pandas as pd

from config.settings import RSI_OVERBOUGHT, RSI_OVERSOLD, SENTIMENT_THRESHOLD
from src.sentiment.claude_sentiment import SentimentResult
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
        sentiment_threshold: float = SENTIMENT_THRESHOLD,
        sentiment_min_confidence: float = 0.5,
    ) -> None:
        self.rsi_overbought = rsi_overbought
        self.rsi_oversold = rsi_oversold
        self.sentiment_threshold = sentiment_threshold
        self.sentiment_min_confidence = sentiment_min_confidence

    def generate_signal(
        self,
        df: pd.DataFrame,
        sentiment: SentimentResult | None = None,
    ) -> str | None:
        """Genera un segnale di trading dall'ultima riga del DataFrame.

        Il DataFrame deve contenere le colonne:
        ema_fast, ema_slow, ema_fast_prev, ema_slow_prev, rsi, volume, volume_ma.

        Se fornito, il sentiment filtra il segnale tecnico:
        - LONG bloccato se sentiment bearish (con confidence sufficiente)
        - SHORT bloccato se sentiment bullish (con confidence sufficiente)

        Args:
            df: DataFrame con indicatori calcolati.
            sentiment: Risultato analisi sentiment (opzionale).

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
            if not self._sentiment_allows(sentiment, "LONG"):
                logger.info("LONG bloccato dal sentiment (score=%.2f)", sentiment.sentiment_score)
                return None
            logger.info("Segnale LONG: EMA cross up, RSI=%.1f, Vol=%.1f", rsi, volume)
            return "LONG"

        # SHORT
        if bearish_cross and rsi > self.rsi_oversold and volume_ok:
            if not self._sentiment_allows(sentiment, "SHORT"):
                logger.info("SHORT bloccato dal sentiment (score=%.2f)", sentiment.sentiment_score)
                return None
            logger.info("Segnale SHORT: EMA cross down, RSI=%.1f, Vol=%.1f", rsi, volume)
            return "SHORT"

        return None

    def _sentiment_allows(self, sentiment: SentimentResult | None, direction: str) -> bool:
        """Verifica se il sentiment consente il segnale nella direzione data.

        Se sentiment è None o ha confidence bassa, il segnale passa senza filtro.

        Args:
            sentiment: Risultato sentiment (può essere None).
            direction: "LONG" o "SHORT".

        Returns:
            True se il segnale è consentito.
        """
        if sentiment is None:
            return True
        if sentiment.confidence < self.sentiment_min_confidence:
            return True
        if direction == "LONG":
            return not sentiment.is_bearish(
                threshold=self.sentiment_threshold,
                min_confidence=self.sentiment_min_confidence,
            )
        # SHORT
        return not sentiment.is_bullish(
            threshold=self.sentiment_threshold,
            min_confidence=self.sentiment_min_confidence,
        )
