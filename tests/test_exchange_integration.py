"""Test di integrazione per il fetch OHLCV da Binance.

Questi test chiamano le API pubbliche di Binance (no API key richiesta per OHLCV).
Segnati come 'integration' per poterli saltare in CI.
"""

import pandas as pd
import pytest

from src.exchange import BinanceExchange


@pytest.mark.integration
def test_fetch_ohlcv_live():
    """Verifica che il fetch OHLCV da Binance funzioni con dati reali."""
    exchange = BinanceExchange(api_key="", api_secret="")
    df = exchange.fetch_ohlcv(symbol="BTC/USDT", timeframe="5m", limit=10)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 10
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert isinstance(df.index, pd.DatetimeIndex)
    # Prezzi BTC devono essere ragionevoli (> $1000)
    assert df["close"].iloc[-1] > 1000.0
