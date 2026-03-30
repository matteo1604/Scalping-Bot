"""Test per la strategia combinata."""

import pandas as pd
import numpy as np
import pytest

from src.strategies.combined import CombinedStrategy


@pytest.fixture
def strategy() -> CombinedStrategy:
    """Crea un'istanza della strategia con parametri di default."""
    return CombinedStrategy()


def _make_df(**overrides) -> pd.DataFrame:
    """Helper: crea un DataFrame a riga singola con indicatori.

    Default: condizioni neutre (nessun segnale).
    """
    defaults = {
        "open": 35000.0,
        "high": 35100.0,
        "low": 34900.0,
        "close": 35050.0,
        "volume": 150.0,
        "ema_fast": 35050.0,
        "ema_slow": 35050.0,
        "ema_fast_prev": 35050.0,
        "ema_slow_prev": 35050.0,
        "rsi": 50.0,
        "volume_ma": 100.0,
    }
    defaults.update(overrides)
    return pd.DataFrame([defaults], index=pd.to_datetime(["2026-01-01"]))


class TestLongSignal:
    """Test per segnali LONG."""

    def test_long_signal_on_bullish_cross(self, strategy):
        """LONG quando EMA fast incrocia sopra EMA slow con RSI e Volume ok."""
        df = _make_df(
            ema_fast=35100.0,
            ema_slow=35050.0,
            ema_fast_prev=35000.0,
            ema_slow_prev=35050.0,
            rsi=55.0,
            volume=150.0,
            volume_ma=100.0,
        )
        signal = strategy.generate_signal(df)
        assert signal == "LONG"

    def test_no_long_when_rsi_overbought(self, strategy):
        """Nessun LONG se RSI >= 70 (overbought)."""
        df = _make_df(
            ema_fast=35100.0,
            ema_slow=35050.0,
            ema_fast_prev=35000.0,
            ema_slow_prev=35050.0,
            rsi=75.0,
            volume=150.0,
            volume_ma=100.0,
        )
        signal = strategy.generate_signal(df)
        assert signal is None

    def test_no_long_when_volume_low(self, strategy):
        """Nessun LONG se volume sotto la media."""
        df = _make_df(
            ema_fast=35100.0,
            ema_slow=35050.0,
            ema_fast_prev=35000.0,
            ema_slow_prev=35050.0,
            rsi=55.0,
            volume=80.0,
            volume_ma=100.0,
        )
        signal = strategy.generate_signal(df)
        assert signal is None


class TestShortSignal:
    """Test per segnali SHORT."""

    def test_short_signal_on_bearish_cross(self, strategy):
        """SHORT quando EMA fast incrocia sotto EMA slow con RSI e Volume ok."""
        df = _make_df(
            ema_fast=35000.0,
            ema_slow=35050.0,
            ema_fast_prev=35100.0,
            ema_slow_prev=35050.0,
            rsi=45.0,
            volume=150.0,
            volume_ma=100.0,
        )
        signal = strategy.generate_signal(df)
        assert signal == "SHORT"

    def test_no_short_when_rsi_oversold(self, strategy):
        """Nessun SHORT se RSI <= 30 (oversold)."""
        df = _make_df(
            ema_fast=35000.0,
            ema_slow=35050.0,
            ema_fast_prev=35100.0,
            ema_slow_prev=35050.0,
            rsi=25.0,
            volume=150.0,
            volume_ma=100.0,
        )
        signal = strategy.generate_signal(df)
        assert signal is None


class TestNoSignal:
    """Test per assenza di segnale."""

    def test_no_signal_when_no_crossover(self, strategy):
        """Nessun segnale se non c'e' crossover."""
        df = _make_df(
            ema_fast=35100.0,
            ema_slow=35050.0,
            ema_fast_prev=35100.0,
            ema_slow_prev=35050.0,
            rsi=55.0,
            volume=150.0,
            volume_ma=100.0,
        )
        signal = strategy.generate_signal(df)
        assert signal is None

    def test_returns_none_with_nan_indicators(self, strategy):
        """Nessun segnale se ci sono NaN negli indicatori."""
        df = _make_df(rsi=float("nan"))
        signal = strategy.generate_signal(df)
        assert signal is None
