"""Strategia combinata: RSI Mean Reversion + Bollinger Bands + ADX + Sentiment.

Logica segnali:
- FILTRO REGIME: ADX > adx_trend_threshold → nessun segnale (mercato in trend)
- LONG  cond A: RSI <= rsi_entry_oversold (30) + Close <= bb_lower + Volume ok
- LONG  cond B: RSI < rsi_extreme_oversold (20), basta da solo (+ Volume ok)
- SHORT cond A: RSI >= rsi_entry_overbought (70) + Close >= bb_upper + Volume ok
- SHORT cond B: RSI > rsi_extreme_overbought (80), basta da solo (+ Volume ok)
- Volume ok: volume >= volume_ma * volume_filter_ratio (default 0.8)
- Il sentiment filtra il segnale: LONG bloccato se bearish, SHORT bloccato se bullish
"""

from __future__ import annotations

import pandas as pd

from config.settings import (
    ADX_TREND_THRESHOLD,
    RSI_ENTRY_OVERBOUGHT,
    RSI_ENTRY_OVERSOLD,
    RSI_EXTREME_OVERBOUGHT,
    RSI_EXTREME_OVERSOLD,
    SENTIMENT_THRESHOLD,
    VOLUME_FILTER_RATIO,
)
from src.sentiment.claude_sentiment import SentimentResult
from src.utils.logger import setup_logger

logger = setup_logger("strategy")


class CombinedStrategy:
    """Strategia di scalping basata su RSI mean reversion + Bollinger Bands.

    Il regime di mercato viene filtrato tramite ADX: in presenza di trend forte
    (ADX > adx_trend_threshold) la strategia non emette segnali, poiché il
    mean reversion perde in trend sostenuti.

    Due condizioni di entry per LONG/SHORT:
    - Condizione A (moderata): RSI + BB insieme
    - Condizione B (estrema): solo RSI a livelli estremi, senza BB

    Args:
        rsi_entry_oversold: Soglia RSI cond A LONG (default: 30).
        rsi_entry_overbought: Soglia RSI cond A SHORT (default: 70).
        rsi_extreme_oversold: Soglia RSI cond B LONG senza BB (default: 20).
        rsi_extreme_overbought: Soglia RSI cond B SHORT senza BB (default: 80).
        adx_trend_threshold: Soglia ADX per filtro regime (default: 25).
        volume_filter_ratio: Volume minimo come multiplo della MA (default: 0.8).
        sentiment_threshold: Score minimo per filtro sentiment (default: 0.3).
        sentiment_min_confidence: Confidence minima per applicare filtro (default: 0.5).
    """

    def __init__(
        self,
        rsi_entry_oversold: float = RSI_ENTRY_OVERSOLD,
        rsi_entry_overbought: float = RSI_ENTRY_OVERBOUGHT,
        rsi_extreme_oversold: float = RSI_EXTREME_OVERSOLD,
        rsi_extreme_overbought: float = RSI_EXTREME_OVERBOUGHT,
        adx_trend_threshold: float = ADX_TREND_THRESHOLD,
        volume_filter_ratio: float = VOLUME_FILTER_RATIO,
        sentiment_threshold: float = SENTIMENT_THRESHOLD,
        sentiment_min_confidence: float = 0.5,
    ) -> None:
        self.rsi_entry_oversold = rsi_entry_oversold
        self.rsi_entry_overbought = rsi_entry_overbought
        self.rsi_extreme_oversold = rsi_extreme_oversold
        self.rsi_extreme_overbought = rsi_extreme_overbought
        self.adx_trend_threshold = adx_trend_threshold
        self.volume_filter_ratio = volume_filter_ratio
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

        Condizioni LONG:
        - A: RSI <= rsi_entry_oversold AND close <= bb_lower
        - B: RSI < rsi_extreme_oversold (basta da solo)

        Condizioni SHORT:
        - A: RSI >= rsi_entry_overbought AND close >= bb_upper
        - B: RSI > rsi_extreme_overbought (basta da solo)

        In tutti i casi: volume >= volume_ma * volume_filter_ratio.

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

        # Filtro volume (rilassato: volume >= volume_ma * ratio)
        volume_threshold = volume_ma * self.volume_filter_ratio
        if volume < volume_threshold:
            logger.debug(
                "Nessun segnale: volume insufficiente (%.1f < %.1f)",
                volume, volume_threshold,
            )
            return None

        # LONG: condizione A (moderata) o B (estrema)
        long_cond_a = rsi <= self.rsi_entry_oversold and close <= bb_lower
        long_cond_b = rsi < self.rsi_extreme_oversold
        if long_cond_a or long_cond_b:
            if not self._sentiment_allows(sentiment, "LONG"):
                logger.info(
                    "LONG bloccato dal sentiment (score=%.2f)",
                    sentiment.sentiment_score,  # type: ignore[union-attr]
                )
                return None
            logger.info(
                "Segnale LONG: RSI=%.1f, Close=%.2f, BB_lower=%.2f (cond_%s)",
                rsi, close, bb_lower, "A" if long_cond_a else "B",
            )
            return "LONG"

        # SHORT: condizione A (moderata) o B (estrema)
        short_cond_a = rsi >= self.rsi_entry_overbought and close >= bb_upper
        short_cond_b = rsi > self.rsi_extreme_overbought
        if short_cond_a or short_cond_b:
            if not self._sentiment_allows(sentiment, "SHORT"):
                logger.info(
                    "SHORT bloccato dal sentiment (score=%.2f)",
                    sentiment.sentiment_score,  # type: ignore[union-attr]
                )
                return None
            logger.info(
                "Segnale SHORT: RSI=%.1f, Close=%.2f, BB_upper=%.2f (cond_%s)",
                rsi, close, bb_upper, "A" if short_cond_a else "B",
            )
            return "SHORT"

        logger.debug(
            "No signal: RSI=%.1f, ADX=%.1f, close=%.1f, bb_lower=%.1f, bb_upper=%.1f, vol=%.1f/%.1f",
            rsi, adx, close, bb_lower, bb_upper, volume, volume_ma,
        )
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
