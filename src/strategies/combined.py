"""Strategia combinata: RSI Mean Reversion + Bollinger Bands + ADX + Sentiment.

Logica segnali:
- FILTRO REGIME: ADX > adx_trend_threshold → nessun segnale (mercato in trend)
- LONG:  RSI <= rsi_entry_oversold (25) + Close <= bb_lower + Volume > volume_ma
- SHORT: RSI >= rsi_entry_overbought (75) + Close >= bb_upper + Volume > volume_ma
- Il sentiment filtra il segnale: LONG bloccato se bearish, SHORT bloccato se bullish
"""

from __future__ import annotations

import pandas as pd

from config.settings import (
    ADX_TREND_THRESHOLD,
    RSI_ENTRY_OVERBOUGHT,
    RSI_ENTRY_OVERSOLD,
    SENTIMENT_THRESHOLD,
)
from src.sentiment.claude_sentiment import SentimentResult
from src.utils.logger import setup_logger

logger = setup_logger("strategy")


class CombinedStrategy:
    """Strategia di scalping basata su RSI mean reversion + Bollinger Bands.

    Il regime di mercato viene filtrato tramite ADX: in presenza di trend forte
    (ADX > adx_trend_threshold) la strategia non emette segnali, poiché il
    mean reversion perde in trend sostenuti.

    Args:
        rsi_entry_oversold: Soglia RSI per segnale LONG (default: 25).
        rsi_entry_overbought: Soglia RSI per segnale SHORT (default: 75).
        adx_trend_threshold: Soglia ADX per filtro regime (default: 25).
        sentiment_threshold: Score minimo per filtro sentiment (default: 0.3).
        sentiment_min_confidence: Confidence minima per applicare filtro (default: 0.5).
    """

    def __init__(
        self,
        rsi_entry_oversold: float = RSI_ENTRY_OVERSOLD,
        rsi_entry_overbought: float = RSI_ENTRY_OVERBOUGHT,
        adx_trend_threshold: float = ADX_TREND_THRESHOLD,
        sentiment_threshold: float = SENTIMENT_THRESHOLD,
        sentiment_min_confidence: float = 0.5,
    ) -> None:
        self.rsi_entry_oversold = rsi_entry_oversold
        self.rsi_entry_overbought = rsi_entry_overbought
        self.adx_trend_threshold = adx_trend_threshold
        self.sentiment_threshold = sentiment_threshold
        self.sentiment_min_confidence = sentiment_min_confidence

    def generate_signal(
        self,
        df: pd.DataFrame,
        sentiment: SentimentResult | None = None,
    ) -> str | None:
        """Genera un segnale di trading dall'ultima riga del DataFrame.

        Il DataFrame deve contenere le colonne:
        rsi, volume, volume_ma, bb_upper, bb_lower, adx, close.

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

        required = ["rsi", "volume", "volume_ma", "bb_upper", "bb_lower", "adx"]
        if any(pd.isna(row.get(col)) for col in required):
            return None

        adx = row["adx"]
        rsi = row["rsi"]
        close = row["close"]
        volume = row["volume"]
        volume_ma = row["volume_ma"]
        bb_upper = row["bb_upper"]
        bb_lower = row["bb_lower"]

        # Filtro regime: mercato in trend forte → no mean reversion
        if adx > self.adx_trend_threshold:
            logger.debug("Nessun segnale: mercato in trend (ADX=%.1f)", adx)
            return None

        # Volume filter
        if volume <= volume_ma:
            return None

        # LONG: RSI oversold + prezzo tocca/buca banda inferiore
        if rsi <= self.rsi_entry_oversold and close <= bb_lower:
            if not self._sentiment_allows(sentiment, "LONG"):
                logger.info(
                    "LONG bloccato dal sentiment (score=%.2f)",
                    sentiment.sentiment_score,  # type: ignore[union-attr]
                )
                return None
            logger.info("Segnale LONG: RSI=%.1f, Close=%.2f <= BB_lower=%.2f", rsi, close, bb_lower)
            return "LONG"

        # SHORT: RSI overbought + prezzo tocca/buca banda superiore
        if rsi >= self.rsi_entry_overbought and close >= bb_upper:
            if not self._sentiment_allows(sentiment, "SHORT"):
                logger.info(
                    "SHORT bloccato dal sentiment (score=%.2f)",
                    sentiment.sentiment_score,  # type: ignore[union-attr]
                )
                return None
            logger.info("Segnale SHORT: RSI=%.1f, Close=%.2f >= BB_upper=%.2f", rsi, close, bb_upper)
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
