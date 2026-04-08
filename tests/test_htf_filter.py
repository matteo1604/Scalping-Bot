"""Test per il filtro multi-timeframe."""

import pandas as pd
import numpy as np
import pytest

from src.indicators.htf_filter import HTFFilter


@pytest.fixture
def htf() -> HTFFilter:
    return HTFFilter()


class TestComputeIndicators:
    """Test per compute_indicators."""

    def test_returns_all_keys(self, htf):
        """Deve restituire dict con tutte le chiavi."""
        np.random.seed(42)
        n = 50
        close = 50000 + np.cumsum(np.random.randn(n) * 50)
        df = pd.DataFrame({
            "open": close - 10, "high": close + 30,
            "low": close - 30, "close": close,
            "volume": np.random.rand(n) * 100 + 50,
        }, index=pd.date_range("2026-01-01", periods=n, freq="1h"))

        result = htf.compute_indicators(df)
        assert "rsi_1h" in result
        assert "ema_fast_1h" in result
        assert "ema_slow_1h" in result
        assert "trend_1h" in result

    def test_insufficient_data_returns_neutral(self, htf):
        """Con pochi dati, trend deve essere NEUTRAL."""
        df = pd.DataFrame({
            "open": [50000], "high": [50100], "low": [49900],
            "close": [50050], "volume": [100],
        }, index=pd.to_datetime(["2026-01-01"]))

        result = htf.compute_indicators(df)
        assert result["trend_1h"] == "NEUTRAL"
        assert result["rsi_1h"] is None

    def test_uptrend_detected(self, htf):
        """EMA fast > EMA slow → trend UP."""
        n = 50
        close = 50000 + np.arange(n) * 20.0  # trend rialzista lineare
        df = pd.DataFrame({
            "open": close - 5, "high": close + 10,
            "low": close - 10, "close": close,
            "volume": np.full(n, 100.0),
        }, index=pd.date_range("2026-01-01", periods=n, freq="1h"))

        result = htf.compute_indicators(df)
        assert result["trend_1h"] == "UP"

    def test_downtrend_detected(self, htf):
        """EMA fast < EMA slow → trend DOWN."""
        n = 50
        close = 50000 - np.arange(n) * 20.0  # trend ribassista lineare
        df = pd.DataFrame({
            "open": close + 5, "high": close + 10,
            "low": close - 10, "close": close,
            "volume": np.full(n, 100.0),
        }, index=pd.date_range("2026-01-01", periods=n, freq="1h"))

        result = htf.compute_indicators(df)
        assert result["trend_1h"] == "DOWN"


class TestAllowsSignal:
    """Test per allows_signal."""

    # --- Mean Reversion ---

    def test_mr_long_blocked_when_1h_overbought(self, htf):
        """LONG mean-rev bloccato se RSI 1h >= 65."""
        htf_data = {"rsi_1h": 68.0, "trend_1h": "UP"}
        assert htf.allows_signal("LONG", "reversion", htf_data) is False

    def test_mr_long_allowed_when_1h_not_overbought(self, htf):
        """LONG mean-rev permesso se RSI 1h < 65."""
        htf_data = {"rsi_1h": 55.0, "trend_1h": "UP"}
        assert htf.allows_signal("LONG", "reversion", htf_data) is True

    def test_mr_short_blocked_when_1h_oversold(self, htf):
        """SHORT mean-rev bloccato se RSI 1h <= 35."""
        htf_data = {"rsi_1h": 30.0, "trend_1h": "DOWN"}
        assert htf.allows_signal("SHORT", "reversion", htf_data) is False

    def test_mr_short_allowed_when_1h_not_oversold(self, htf):
        """SHORT mean-rev permesso se RSI 1h > 35."""
        htf_data = {"rsi_1h": 45.0, "trend_1h": "DOWN"}
        assert htf.allows_signal("SHORT", "reversion", htf_data) is True

    # --- Trend Following ---

    def test_tf_long_blocked_when_1h_downtrend(self, htf):
        """LONG trend-follow bloccato se trend 1h = DOWN."""
        htf_data = {"rsi_1h": 50.0, "trend_1h": "DOWN"}
        assert htf.allows_signal("LONG", "trend", htf_data) is False

    def test_tf_long_allowed_when_1h_uptrend(self, htf):
        """LONG trend-follow permesso se trend 1h = UP."""
        htf_data = {"rsi_1h": 50.0, "trend_1h": "UP"}
        assert htf.allows_signal("LONG", "trend", htf_data) is True

    def test_tf_long_allowed_when_1h_neutral(self, htf):
        """LONG trend-follow permesso se trend 1h = NEUTRAL."""
        htf_data = {"rsi_1h": 50.0, "trend_1h": "NEUTRAL"}
        assert htf.allows_signal("LONG", "trend", htf_data) is True

    def test_tf_short_blocked_when_1h_uptrend(self, htf):
        """SHORT trend-follow bloccato se trend 1h = UP."""
        htf_data = {"rsi_1h": 50.0, "trend_1h": "UP"}
        assert htf.allows_signal("SHORT", "trend", htf_data) is False

    def test_tf_short_allowed_when_1h_downtrend(self, htf):
        """SHORT trend-follow permesso se trend 1h = DOWN."""
        htf_data = {"rsi_1h": 50.0, "trend_1h": "DOWN"}
        assert htf.allows_signal("SHORT", "trend", htf_data) is True

    # --- Fail-open ---

    def test_no_htf_data_allows_all(self, htf):
        """Senza dati 1h, tutti i segnali passano (fail-open)."""
        htf_data = {"rsi_1h": None, "trend_1h": "NEUTRAL"}
        assert htf.allows_signal("LONG", "reversion", htf_data) is True
        assert htf.allows_signal("SHORT", "trend", htf_data) is True
