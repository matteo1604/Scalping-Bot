"""Calcolo indicatori tecnici: EMA, RSI, Volume MA, Bollinger Bands, ATR, ADX, DI+/DI-.

Responsabilità:
- Calcolare EMA(9) e EMA(21) per compatibilità retroattiva
- Calcolare RSI(14) per segnali mean reversion
- Calcolare media mobile del volume (20 periodi)
- Calcolare Bollinger Bands (20, 2.0) per segnali mean reversion
- Calcolare ATR(14) per risk management dinamico
- Calcolare ADX(14) per filtro regime di mercato
- Calcolare DI+(14) e DI-(14) per direzione del trend
- Restituire un DataFrame arricchito con tutti gli indicatori
"""

import pandas as pd
import ta

from config.settings import (
    ADX_PERIOD,
    ATR_PERIOD,
    BB_PERIOD,
    BB_STD,
    EMA_FAST,
    EMA_SLOW,
    RSI_PERIOD,
    VOLUME_MA_PERIOD,
)


def add_indicators(
    df: pd.DataFrame,
    ema_fast_period: int = EMA_FAST,
    ema_slow_period: int = EMA_SLOW,
    rsi_period: int = RSI_PERIOD,
    volume_ma_period: int = VOLUME_MA_PERIOD,
    bb_period: int = BB_PERIOD,
    bb_std: float = BB_STD,
    atr_period: int = ATR_PERIOD,
    adx_period: int = ADX_PERIOD,
) -> pd.DataFrame:
    """Arricchisce un DataFrame OHLCV con indicatori tecnici.

    Aggiunge: ema_fast, ema_slow, rsi, volume_ma, bb_upper, bb_middle,
    bb_lower, atr, adx, di_plus, di_minus.

    Args:
        df: DataFrame con colonne [open, high, low, close, volume].
        ema_fast_period: Periodo EMA veloce (default: 9).
        ema_slow_period: Periodo EMA lenta (default: 21).
        rsi_period: Periodo RSI (default: 14).
        volume_ma_period: Periodo media mobile volume (default: 20).
        bb_period: Periodo Bollinger Bands (default: 20).
        bb_std: Deviazioni standard Bollinger Bands (default: 2.0).
        atr_period: Periodo ATR (default: 14).
        adx_period: Periodo ADX (default: 14).

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

    # Bollinger Bands
    bb = ta.volatility.BollingerBands(result["close"], window=bb_period, window_dev=bb_std)
    result["bb_upper"] = bb.bollinger_hband()
    result["bb_middle"] = bb.bollinger_mavg()
    result["bb_lower"] = bb.bollinger_lband()

    # ATR
    result["atr"] = ta.volatility.average_true_range(
        result["high"], result["low"], result["close"], window=atr_period
    )

    # ADX
    result["adx"] = ta.trend.adx(
        result["high"], result["low"], result["close"], window=adx_period
    )

    # DI+ / DI- — indicatori direzionali per trend following
    result["di_plus"] = ta.trend.adx_pos(
        result["high"], result["low"], result["close"], window=adx_period
    )
    result["di_minus"] = ta.trend.adx_neg(
        result["high"], result["low"], result["close"], window=adx_period
    )

    return result


def add_prev_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Aggiunge colonne con valori degli indicatori della candela precedente.

    Necessario per rilevare crossover (confronto tra candela corrente e precedente).

    Args:
        df: DataFrame con colonne ema_fast e ema_slow.

    Returns:
        DataFrame con colonne ema_fast_prev e ema_slow_prev aggiunte.
    """
    result = df.copy()
    result["ema_fast_prev"] = result["ema_fast"].shift(1)
    result["ema_slow_prev"] = result["ema_slow"].shift(1)
    return result
