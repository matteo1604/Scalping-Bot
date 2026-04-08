"""Filtro multi-timeframe: usa il timeframe 1h come semaforo per i segnali 5min.

Il filtro NON genera segnali — conferma o blocca quelli del 5min.
"""

from __future__ import annotations

import pandas as pd
import ta

from config.settings import (
    EMA_FAST,
    EMA_SLOW,
    RSI_PERIOD,
    HTF_RSI_OVERBOUGHT,
    HTF_RSI_OVERSOLD,
)
from src.utils.logger import setup_logger

logger = setup_logger("htf_filter")


class HTFFilter:
    """Filtro basato sul timeframe 1h.

    Calcola RSI e EMA sul 1h e li usa per filtrare i segnali del 5min.

    Args:
        rsi_overbought: RSI 1h sopra questo → blocca LONG (default: 65).
        rsi_oversold: RSI 1h sotto questo → blocca SHORT (default: 35).
        ema_fast: Periodo EMA veloce 1h (default: 9).
        ema_slow: Periodo EMA lenta 1h (default: 21).
    """

    def __init__(
        self,
        rsi_overbought: float = HTF_RSI_OVERBOUGHT,
        rsi_oversold: float = HTF_RSI_OVERSOLD,
        ema_fast: int = EMA_FAST,
        ema_slow: int = EMA_SLOW,
        rsi_period: int = RSI_PERIOD,
    ) -> None:
        self.rsi_overbought = rsi_overbought
        self.rsi_oversold = rsi_oversold
        self.ema_fast_period = ema_fast
        self.ema_slow_period = ema_slow
        self.rsi_period = rsi_period

    def compute_indicators(self, df_1h: pd.DataFrame) -> dict:
        """Calcola RSI e EMA sul DataFrame 1h.

        Args:
            df_1h: DataFrame OHLCV con timeframe 1h.

        Returns:
            Dict con chiavi: rsi_1h, ema_fast_1h, ema_slow_1h, trend_1h.
            trend_1h è "UP", "DOWN", o "NEUTRAL".
        """
        if len(df_1h) < max(self.ema_slow_period, self.rsi_period) + 5:
            logger.warning("Dati 1h insufficienti per calcolare indicatori")
            return {"rsi_1h": None, "ema_fast_1h": None, "ema_slow_1h": None, "trend_1h": "NEUTRAL"}

        rsi = ta.momentum.rsi(df_1h["close"], window=self.rsi_period)
        ema_fast = ta.trend.ema_indicator(df_1h["close"], window=self.ema_fast_period)
        ema_slow = ta.trend.ema_indicator(df_1h["close"], window=self.ema_slow_period)

        rsi_val = rsi.iloc[-1]
        ema_f = ema_fast.iloc[-1]
        ema_s = ema_slow.iloc[-1]

        if pd.isna(rsi_val) or pd.isna(ema_f) or pd.isna(ema_s):
            return {"rsi_1h": None, "ema_fast_1h": None, "ema_slow_1h": None, "trend_1h": "NEUTRAL"}

        if ema_f > ema_s:
            trend = "UP"
        elif ema_f < ema_s:
            trend = "DOWN"
        else:
            trend = "NEUTRAL"

        return {
            "rsi_1h": rsi_val,
            "ema_fast_1h": ema_f,
            "ema_slow_1h": ema_s,
            "trend_1h": trend,
        }

    def allows_signal(self, signal: str, strategy_mode: str, htf_data: dict) -> bool:
        """Verifica se il timeframe 1h permette il segnale.

        Regole:
        MEAN REVERSION:
        - LONG bloccato se RSI 1h >= rsi_overbought (65) — macro overbought
        - SHORT bloccato se RSI 1h <= rsi_oversold (35) — macro oversold
        (Il mean reversion cerca rimbalzi, ma non contro il macro trend estremo)

        TREND FOLLOWING:
        - LONG permesso solo se trend_1h == "UP" o "NEUTRAL"
        - SHORT permesso solo se trend_1h == "DOWN" o "NEUTRAL"
        (Il trend following deve essere allineato al macro trend)

        Args:
            signal: "LONG" o "SHORT".
            strategy_mode: "reversion" o "trend".
            htf_data: Dict da compute_indicators().

        Returns:
            True se il segnale è permesso.
        """
        rsi_1h = htf_data.get("rsi_1h")
        trend_1h = htf_data.get("trend_1h", "NEUTRAL")

        # Se non abbiamo dati 1h, lascia passare (fail-open)
        if rsi_1h is None:
            logger.debug("HTF filter: dati 1h non disponibili, segnale permesso")
            return True

        if strategy_mode == "reversion":
            if signal == "LONG" and rsi_1h >= self.rsi_overbought:
                logger.info(
                    "HTF BLOCK: LONG mean-rev bloccato, RSI 1h=%.1f (>= %.1f)",
                    rsi_1h, self.rsi_overbought,
                )
                return False
            if signal == "SHORT" and rsi_1h <= self.rsi_oversold:
                logger.info(
                    "HTF BLOCK: SHORT mean-rev bloccato, RSI 1h=%.1f (<= %.1f)",
                    rsi_1h, self.rsi_oversold,
                )
                return False

        elif strategy_mode == "trend":
            if signal == "LONG" and trend_1h == "DOWN":
                logger.info(
                    "HTF BLOCK: LONG trend-follow bloccato, trend 1h=DOWN",
                )
                return False
            if signal == "SHORT" and trend_1h == "UP":
                logger.info(
                    "HTF BLOCK: SHORT trend-follow bloccato, trend 1h=UP",
                )
                return False

        logger.debug(
            "HTF PASS: %s %s permesso (RSI 1h=%.1f, trend 1h=%s)",
            signal, strategy_mode, rsi_1h, trend_1h,
        )
        return True
