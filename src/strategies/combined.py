"""Strategia combinata: RSI Mean Reversion + Bollinger Bands + ADX + Trend Following + Sentiment.

Logica segnali — modalità selezionata automaticamente da ADX:

MEAN REVERSION (ADX <= adx_trend_threshold):
- LONG  cond A: RSI <= rsi_entry_oversold + Close <= bb_lower + Volume ok
- LONG  cond B: RSI < rsi_extreme_oversold (basta da solo) + Volume ok
- SHORT cond A: RSI >= rsi_entry_overbought + Close >= bb_upper + Volume ok
- SHORT cond B: RSI > rsi_extreme_overbought (basta da solo) + Volume ok

TREND FOLLOWING (ADX > adx_trend_threshold):
- LONG : DI+ > DI- AND close > ema_slow AND RSI in [bull_min, bull_max] AND close > bb_middle + Volume ok
- SHORT: DI- > DI+ AND close < ema_slow AND RSI in [bear_min, bear_max] AND close < bb_middle + Volume ok

- Volume ok: volume >= volume_ma * volume_filter_ratio (default 0.8)
- Il sentiment filtra il segnale: LONG bloccato se bearish, SHORT bloccato se bullish
"""

from __future__ import annotations

import pandas as pd

from config.settings import (
    ADX_TREND_THRESHOLD,
    RSI_ENTRY_OVERBOUGHT,
    RSI_ENTRY_OVERSOLD,
    RSI_EXIT_MEAN_REVERSION,
    RSI_EXTREME_OVERBOUGHT,
    RSI_EXTREME_OVERSOLD,
    SENTIMENT_THRESHOLD,
    TREND_RSI_PULLBACK_BEAR_MAX,
    TREND_RSI_PULLBACK_BEAR_MIN,
    TREND_RSI_PULLBACK_BULL_MAX,
    TREND_RSI_PULLBACK_BULL_MIN,
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
        trend_rsi_bull_min: float = TREND_RSI_PULLBACK_BULL_MIN,
        trend_rsi_bull_max: float = TREND_RSI_PULLBACK_BULL_MAX,
        trend_rsi_bear_min: float = TREND_RSI_PULLBACK_BEAR_MIN,
        trend_rsi_bear_max: float = TREND_RSI_PULLBACK_BEAR_MAX,
    ) -> None:
        self.rsi_entry_oversold = rsi_entry_oversold
        self.rsi_entry_overbought = rsi_entry_overbought
        self.rsi_extreme_oversold = rsi_extreme_oversold
        self.rsi_extreme_overbought = rsi_extreme_overbought
        self.adx_trend_threshold = adx_trend_threshold
        self.volume_filter_ratio = volume_filter_ratio
        self.sentiment_threshold = sentiment_threshold
        self.sentiment_min_confidence = sentiment_min_confidence
        self.trend_rsi_bull_min = trend_rsi_bull_min
        self.trend_rsi_bull_max = trend_rsi_bull_max
        self.trend_rsi_bear_min = trend_rsi_bear_min
        self.trend_rsi_bear_max = trend_rsi_bear_max

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
        volume = row["volume"]
        volume_ma = row["volume_ma"]

        # Filtro volume (comune a entrambe le modalità)
        volume_threshold = volume_ma * self.volume_filter_ratio
        if volume < volume_threshold:
            logger.debug(
                "Nessun segnale: volume insufficiente (%.1f < %.1f)",
                volume, volume_threshold,
            )
            return None

        # Branch sul regime di mercato
        if adx > self.adx_trend_threshold:
            signal = self._trend_following_signal(df)
        else:
            signal = self._mean_reversion_signal(df)

        if signal is None:
            return None

        if not self._sentiment_allows(sentiment, signal):
            logger.info(
                "%s bloccato dal sentiment (score=%.2f)",
                signal,
                sentiment.sentiment_score,  # type: ignore[union-attr]
            )
            return None

        return signal

    def _mean_reversion_signal(self, df: pd.DataFrame) -> str | None:
        """Genera segnale mean reversion (ADX <= threshold).

        Condizioni LONG:
        - A: RSI <= rsi_entry_oversold AND close <= bb_lower AND RSI in risalita
        - B: RSI < rsi_extreme_oversold AND RSI in risalita

        Condizioni SHORT:
        - A: RSI >= rsi_entry_overbought AND close >= bb_upper AND RSI in discesa
        - B: RSI > rsi_extreme_overbought AND RSI in discesa

        Il "turning" richiede almeno 2 candele: len(df) < 2 → None.
        """
        if len(df) < 2:
            return None

        row = df.iloc[-1]
        prev_row = df.iloc[-2]

        rsi = row["rsi"]
        prev_rsi = prev_row["rsi"]
        close = row["close"]
        bb_upper = row["bb_upper"]
        bb_lower = row["bb_lower"]

        rsi_turning_up = rsi > prev_rsi      # RSI risale = momentum esaurito al ribasso
        rsi_turning_down = rsi < prev_rsi    # RSI scende = momentum esaurito al rialzo

        long_cond_a = rsi <= self.rsi_entry_oversold and close <= bb_lower and rsi_turning_up
        long_cond_b = rsi < self.rsi_extreme_oversold and rsi_turning_up
        if long_cond_a or long_cond_b:
            logger.info(
                "Segnale LONG (mean rev): RSI=%.1f (prev=%.1f), Close=%.2f, BB_lower=%.2f (cond_%s)",
                rsi, prev_rsi, close, bb_lower, "A" if long_cond_a else "B",
            )
            return "LONG"

        short_cond_a = rsi >= self.rsi_entry_overbought and close >= bb_upper and rsi_turning_down
        short_cond_b = rsi > self.rsi_extreme_overbought and rsi_turning_down
        if short_cond_a or short_cond_b:
            logger.info(
                "Segnale SHORT (mean rev): RSI=%.1f (prev=%.1f), Close=%.2f, BB_upper=%.2f (cond_%s)",
                rsi, prev_rsi, close, bb_upper, "A" if short_cond_a else "B",
            )
            return "SHORT"

        logger.debug(
            "No signal (mean rev): RSI=%.1f (prev=%.1f), close=%.1f",
            rsi, prev_rsi, close,
        )
        return None

    def _trend_following_signal(self, df: pd.DataFrame) -> str | None:
        """Genera segnale trend following (ADX > threshold).

        LONG: DI+ > DI- AND close > ema_slow AND RSI in [bull_min, bull_max]
              AND close > bb_middle AND DI+ in crescita vs candela precedente.
        SHORT: DI- > DI+ AND close < ema_slow AND RSI in [bear_min, bear_max]
               AND close < bb_middle AND DI- in crescita vs candela precedente.

        len(df) < 2 → None.
        """
        if len(df) < 2:
            return None

        row = df.iloc[-1]
        prev_row = df.iloc[-2]

        rsi = row["rsi"]
        close = row["close"]
        adx = row["adx"]
        di_plus = row.get("di_plus")
        di_minus = row.get("di_minus")
        ema_slow = row.get("ema_slow")
        bb_middle = row.get("bb_middle")
        prev_di_plus = prev_row.get("di_plus")
        prev_di_minus = prev_row.get("di_minus")

        if any(pd.isna(v) for v in [di_plus, di_minus, ema_slow, bb_middle, prev_di_plus, prev_di_minus]):
            logger.debug("Nessun segnale trend: colonne NaN")
            return None

        di_plus_growing = di_plus > prev_di_plus    # trend rialzista si rafforza
        di_minus_growing = di_minus > prev_di_minus  # trend ribassista si rafforza

        uptrend = di_plus > di_minus and close > ema_slow
        if (uptrend and di_plus_growing
                and self.trend_rsi_bull_min <= rsi <= self.trend_rsi_bull_max
                and close > bb_middle):
            logger.info(
                "Segnale LONG (trend): ADX=%.1f, DI+=%.1f (prev=%.1f), DI-=%.1f, RSI=%.1f",
                adx, di_plus, prev_di_plus, di_minus, rsi,
            )
            return "LONG"

        downtrend = di_minus > di_plus and close < ema_slow
        if (downtrend and di_minus_growing
                and self.trend_rsi_bear_min <= rsi <= self.trend_rsi_bear_max
                and close < bb_middle):
            logger.info(
                "Segnale SHORT (trend): ADX=%.1f, DI-=%.1f (prev=%.1f), DI+=%.1f, RSI=%.1f",
                adx, di_minus, prev_di_minus, di_plus, rsi,
            )
            return "SHORT"

        logger.debug(
            "No signal (trend): ADX=%.1f, DI+=%.1f, DI-=%.1f, RSI=%.1f",
            adx, di_plus, di_minus, rsi,
        )
        return None

    def should_exit(self, df: pd.DataFrame, position: dict) -> str | None:
        """Verifica se la posizione aperta dovrebbe essere chiusa su segnale tecnico.

        NON controlla SL/TP/trailing — quelli sono gestiti dal TradingLoop.
        Controlla solo condizioni tecniche di uscita.

        Args:
            df: DataFrame con indicatori calcolati.
            position: Dict della posizione aperta con "side" e "strategy".

        Returns:
            "signal_exit" se la posizione dovrebbe chiudersi, None altrimenti.
        """
        row = df.iloc[-1]

        required = ["rsi", "adx", "di_plus", "di_minus"]
        if any(pd.isna(row.get(col)) for col in required):
            return None

        rsi = row["rsi"]
        side = position["side"]
        strategy = position.get("strategy", "reversion")

        if strategy == "reversion":
            # Mean reversion: chiudi quando RSI torna a 50 (obiettivo raggiunto)
            if side == "LONG" and rsi >= RSI_EXIT_MEAN_REVERSION:
                logger.info("Exit signal (mean-rev): RSI=%.1f ha raggiunto target %.1f", rsi, RSI_EXIT_MEAN_REVERSION)
                return "signal_exit"
            if side == "SHORT" and rsi <= RSI_EXIT_MEAN_REVERSION:
                logger.info("Exit signal (mean-rev): RSI=%.1f ha raggiunto target %.1f", rsi, RSI_EXIT_MEAN_REVERSION)
                return "signal_exit"

        elif strategy == "trend":
            # Trend following: chiudi se DI+/DI- si incrociano nella direzione opposta
            di_plus = row["di_plus"]
            di_minus = row["di_minus"]
            if side == "LONG" and di_minus > di_plus:
                logger.info("Exit signal (trend): DI- (%.1f) > DI+ (%.1f), trend invertito", di_minus, di_plus)
                return "signal_exit"
            if side == "SHORT" and di_plus > di_minus:
                logger.info("Exit signal (trend): DI+ (%.1f) > DI- (%.1f), trend invertito", di_plus, di_minus)
                return "signal_exit"

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
