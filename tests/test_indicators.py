"""Test per il modulo indicatori tecnici."""

import pandas as pd
import numpy as np
import pytest

from src.indicators.technical import add_indicators


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """Crea un DataFrame OHLCV di esempio con 50 candele."""
    np.random.seed(42)
    n = 50
    close = 35000 + np.cumsum(np.random.randn(n) * 50)
    df = pd.DataFrame({
        "open": close - np.random.rand(n) * 20,
        "high": close + np.random.rand(n) * 30,
        "low": close - np.random.rand(n) * 30,
        "close": close,
        "volume": np.random.rand(n) * 200 + 50,
    }, index=pd.date_range("2026-01-01", periods=n, freq="5min"))
    return df


class TestAddIndicators:
    """Test per la funzione add_indicators."""

    def test_returns_dataframe(self, sample_ohlcv):
        """Deve restituire un DataFrame."""
        result = add_indicators(sample_ohlcv)
        assert isinstance(result, pd.DataFrame)

    def test_adds_ema_columns(self, sample_ohlcv):
        """Deve aggiungere colonne ema_fast e ema_slow."""
        result = add_indicators(sample_ohlcv)
        assert "ema_fast" in result.columns
        assert "ema_slow" in result.columns

    def test_adds_rsi_column(self, sample_ohlcv):
        """Deve aggiungere colonna rsi."""
        result = add_indicators(sample_ohlcv)
        assert "rsi" in result.columns

    def test_adds_volume_ma_column(self, sample_ohlcv):
        """Deve aggiungere colonna volume_ma."""
        result = add_indicators(sample_ohlcv)
        assert "volume_ma" in result.columns

    def test_rsi_bounded(self, sample_ohlcv):
        """RSI deve essere tra 0 e 100."""
        result = add_indicators(sample_ohlcv)
        rsi = result["rsi"].dropna()
        assert (rsi >= 0).all()
        assert (rsi <= 100).all()

    def test_ema_fast_more_responsive(self, sample_ohlcv):
        """EMA fast (9) deve avere deviazione standard >= EMA slow (21)."""
        result = add_indicators(sample_ohlcv)
        ema_f = result["ema_fast"].dropna()
        ema_s = result["ema_slow"].dropna()
        assert ema_f.std() >= ema_s.std()

    def test_preserves_original_columns(self, sample_ohlcv):
        """Non deve rimuovere le colonne OHLCV originali."""
        result = add_indicators(sample_ohlcv)
        for col in ["open", "high", "low", "close", "volume"]:
            assert col in result.columns

    def test_custom_periods(self, sample_ohlcv):
        """Deve accettare periodi personalizzati."""
        result = add_indicators(
            sample_ohlcv,
            ema_fast_period=5,
            ema_slow_period=10,
            rsi_period=7,
            volume_ma_period=10,
        )
        assert "ema_fast" in result.columns
        assert "rsi" in result.columns
