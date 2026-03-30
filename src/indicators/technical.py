"""Calcolo indicatori tecnici: EMA, RSI, Volume MA.

Responsabilità:
- Calcolare EMA(9) e EMA(21) per crossover
- Calcolare RSI(14) per filtro overbought/oversold
- Calcolare media mobile del volume (20 periodi)
- Restituire un DataFrame arricchito con tutti gli indicatori
"""

import pandas as pd
import ta

from config.settings import EMA_FAST, EMA_SLOW, RSI_PERIOD, VOLUME_MA_PERIOD


def add_indicators(
    df: pd.DataFrame,
    ema_fast_period: int = EMA_FAST,
    ema_slow_period: int = EMA_SLOW,
    rsi_period: int = RSI_PERIOD,
    volume_ma_period: int = VOLUME_MA_PERIOD,
) -> pd.DataFrame:
    """Arricchisce un DataFrame OHLCV con indicatori tecnici.

    Aggiunge: ema_fast, ema_slow, rsi, volume_ma.

    Args:
        df: DataFrame con colonne [open, high, low, close, volume].
        ema_fast_period: Periodo EMA veloce (default: 9).
        ema_slow_period: Periodo EMA lenta (default: 21).
        rsi_period: Periodo RSI (default: 14).
        volume_ma_period: Periodo media mobile volume (default: 20).

    Returns:
        DataFrame originale con colonne indicatori aggiunte.
    """
    result = df.copy()

    # EMA
    result["ema_fast"] = ta.trend.ema_indicator(result["close"], window=ema_fast_period)
    result["ema_slow"] = ta.trend.ema_indicator(result["close"], window=ema_slow_period)

    # RSI
    result["rsi"] = ta.momentum.rsi(result["close"], window=rsi_period)

    # Volume MA
    result["volume_ma"] = result["volume"].rolling(window=volume_ma_period).mean()

    return result
