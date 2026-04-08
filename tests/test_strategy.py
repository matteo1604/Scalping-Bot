"""Test per la strategia combinata RSI Mean Reversion + Bollinger Bands + ADX."""

import pandas as pd
import numpy as np
import pytest

from src.strategies.combined import CombinedStrategy
from src.sentiment.claude_sentiment import SentimentResult


@pytest.fixture
def strategy() -> CombinedStrategy:
    """Crea un'istanza della strategia con parametri di default."""
    return CombinedStrategy()


def _make_df(**overrides) -> pd.DataFrame:
    """Helper: crea un DataFrame a riga singola con indicatori.

    Default: condizioni neutre (ADX basso, RSI 50, prezzo in mezzo alle BB,
    volume sopra la media) → nessun segnale.
    """
    defaults = {
        "open": 35000.0,
        "high": 35100.0,
        "low": 34900.0,
        "close": 35000.0,
        "volume": 150.0,
        "rsi": 50.0,
        "volume_ma": 100.0,
        "bb_upper": 35500.0,
        "bb_middle": 35000.0,
        "bb_lower": 34500.0,
        "atr": 200.0,
        "adx": 15.0,
    }
    defaults.update(overrides)
    return pd.DataFrame([defaults], index=pd.to_datetime(["2026-01-01"]))


# ---------------------------------------------------------------------------
# ADX regime filter
# ---------------------------------------------------------------------------

class TestADXRegimeFilter:
    """ADX alto deve bloccare tutti i segnali (mercato in trend)."""

    def test_high_adx_blocks_long_signal(self, strategy):
        """ADX > threshold blocca LONG anche con RSI+BB corretti."""
        df = _make_df(
            rsi=20.0,
            close=34490.0,  # <= bb_lower (34500)
            volume=150.0,
            volume_ma=100.0,
            adx=30.0,  # sopra ADX_TREND_THRESHOLD (25)
        )
        assert strategy.generate_signal(df) is None

    def test_high_adx_blocks_short_signal(self, strategy):
        """ADX > threshold blocca SHORT anche con RSI+BB corretti."""
        df = _make_df(
            rsi=80.0,
            close=35510.0,  # >= bb_upper (35500)
            volume=150.0,
            volume_ma=100.0,
            adx=30.0,
        )
        assert strategy.generate_signal(df) is None

    def test_adx_exactly_at_threshold_allows_signal(self, strategy):
        """ADX esattamente uguale alla threshold non blocca il segnale."""
        df = _make_df(
            rsi=20.0,
            close=34490.0,
            volume=150.0,
            volume_ma=100.0,
            adx=25.0,  # uguale alla soglia → non trend forte
        )
        assert strategy.generate_signal(df) == "LONG"

    def test_low_adx_allows_signals(self, strategy):
        """ADX basso permette i segnali."""
        df = _make_df(
            rsi=20.0,
            close=34490.0,
            volume=150.0,
            volume_ma=100.0,
            adx=10.0,
        )
        assert strategy.generate_signal(df) == "LONG"


# ---------------------------------------------------------------------------
# LONG signal
# ---------------------------------------------------------------------------

class TestLongSignal:
    """Test per segnali LONG (RSI oversold + prezzo su BB lower)."""

    def test_long_signal_rsi_oversold_and_bb_lower(self, strategy):
        """LONG quando RSI < 25 e close <= bb_lower e volume ok."""
        df = _make_df(
            rsi=20.0,
            close=34490.0,  # <= bb_lower
            volume=150.0,
            volume_ma=100.0,
            adx=15.0,
        )
        assert strategy.generate_signal(df) == "LONG"

    def test_long_on_rsi_exactly_at_oversold_threshold(self, strategy):
        """LONG quando RSI == RSI_ENTRY_OVERSOLD (25)."""
        df = _make_df(
            rsi=25.0,
            close=34490.0,
            volume=150.0,
            volume_ma=100.0,
            adx=15.0,
        )
        assert strategy.generate_signal(df) == "LONG"

    def test_no_long_when_rsi_not_oversold(self, strategy):
        """Nessun LONG se RSI > RSI_ENTRY_OVERSOLD (25)."""
        df = _make_df(
            rsi=35.0,
            close=34490.0,
            volume=150.0,
            volume_ma=100.0,
            adx=15.0,
        )
        assert strategy.generate_signal(df) is None

    def test_no_long_when_close_above_bb_lower(self, strategy):
        """Nessun LONG se close > bb_lower (prezzo non tocca la banda)."""
        df = _make_df(
            rsi=20.0,
            close=34600.0,  # sopra bb_lower=34500
            volume=150.0,
            volume_ma=100.0,
            adx=15.0,
        )
        assert strategy.generate_signal(df) is None

    def test_no_long_when_volume_low(self, strategy):
        """Nessun LONG se volume < volume_ma."""
        df = _make_df(
            rsi=20.0,
            close=34490.0,
            volume=80.0,
            volume_ma=100.0,
            adx=15.0,
        )
        assert strategy.generate_signal(df) is None


# ---------------------------------------------------------------------------
# SHORT signal
# ---------------------------------------------------------------------------

class TestShortSignal:
    """Test per segnali SHORT (RSI overbought + prezzo su BB upper)."""

    def test_short_signal_rsi_overbought_and_bb_upper(self, strategy):
        """SHORT quando RSI > 75 e close >= bb_upper e volume ok."""
        df = _make_df(
            rsi=80.0,
            close=35510.0,  # >= bb_upper
            volume=150.0,
            volume_ma=100.0,
            adx=15.0,
        )
        assert strategy.generate_signal(df) == "SHORT"

    def test_short_on_rsi_exactly_at_overbought_threshold(self, strategy):
        """SHORT quando RSI == RSI_ENTRY_OVERBOUGHT (75)."""
        df = _make_df(
            rsi=75.0,
            close=35510.0,
            volume=150.0,
            volume_ma=100.0,
            adx=15.0,
        )
        assert strategy.generate_signal(df) == "SHORT"

    def test_no_short_when_rsi_not_overbought(self, strategy):
        """Nessun SHORT se RSI < RSI_ENTRY_OVERBOUGHT (75)."""
        df = _make_df(
            rsi=65.0,
            close=35510.0,
            volume=150.0,
            volume_ma=100.0,
            adx=15.0,
        )
        assert strategy.generate_signal(df) is None

    def test_no_short_when_close_below_bb_upper(self, strategy):
        """Nessun SHORT se close < bb_upper."""
        df = _make_df(
            rsi=80.0,
            close=35400.0,  # sotto bb_upper=35500
            volume=150.0,
            volume_ma=100.0,
            adx=15.0,
        )
        assert strategy.generate_signal(df) is None

    def test_no_short_when_volume_low(self, strategy):
        """Nessun SHORT se volume < volume_ma."""
        df = _make_df(
            rsi=80.0,
            close=35510.0,
            volume=80.0,
            volume_ma=100.0,
            adx=15.0,
        )
        assert strategy.generate_signal(df) is None


# ---------------------------------------------------------------------------
# NaN handling
# ---------------------------------------------------------------------------

class TestNaNHandling:
    """NaN in qualsiasi indicatore chiave deve restituire None."""

    def test_returns_none_with_nan_rsi(self, strategy):
        df = _make_df(rsi=float("nan"))
        assert strategy.generate_signal(df) is None

    def test_returns_none_with_nan_adx(self, strategy):
        df = _make_df(adx=float("nan"))
        assert strategy.generate_signal(df) is None

    def test_returns_none_with_nan_bb_lower(self, strategy):
        df = _make_df(bb_lower=float("nan"))
        assert strategy.generate_signal(df) is None

    def test_returns_none_with_nan_bb_upper(self, strategy):
        df = _make_df(bb_upper=float("nan"))
        assert strategy.generate_signal(df) is None

    def test_returns_none_with_nan_volume_ma(self, strategy):
        df = _make_df(volume_ma=float("nan"))
        assert strategy.generate_signal(df) is None


# ---------------------------------------------------------------------------
# Sentiment filter
# ---------------------------------------------------------------------------

class TestSentimentFilter:
    """Il sentiment filtra i segnali tecnici."""

    def test_long_blocked_by_bearish_sentiment(self, strategy):
        """LONG bloccato se sentiment è bearish con confidence sufficiente."""
        df = _make_df(
            rsi=20.0, close=34490.0,
            volume=150.0, volume_ma=100.0, adx=15.0,
        )
        sentiment = SentimentResult(
            sentiment_score=-0.5, confidence=0.8,
            top_events=["Crash"], recommendation="SELL",
        )
        assert strategy.generate_signal(df, sentiment=sentiment) is None

    def test_long_allowed_by_bullish_sentiment(self, strategy):
        """LONG passa se sentiment è bullish."""
        df = _make_df(
            rsi=20.0, close=34490.0,
            volume=150.0, volume_ma=100.0, adx=15.0,
        )
        sentiment = SentimentResult(
            sentiment_score=0.5, confidence=0.8,
            top_events=["Rally"], recommendation="BUY",
        )
        assert strategy.generate_signal(df, sentiment=sentiment) == "LONG"

    def test_short_blocked_by_bullish_sentiment(self, strategy):
        """SHORT bloccato se sentiment è bullish con confidence sufficiente."""
        df = _make_df(
            rsi=80.0, close=35510.0,
            volume=150.0, volume_ma=100.0, adx=15.0,
        )
        sentiment = SentimentResult(
            sentiment_score=0.5, confidence=0.8,
            top_events=["Rally"], recommendation="BUY",
        )
        assert strategy.generate_signal(df, sentiment=sentiment) is None

    def test_short_allowed_by_bearish_sentiment(self, strategy):
        """SHORT passa se sentiment è bearish."""
        df = _make_df(
            rsi=80.0, close=35510.0,
            volume=150.0, volume_ma=100.0, adx=15.0,
        )
        sentiment = SentimentResult(
            sentiment_score=-0.5, confidence=0.8,
            top_events=["Crash"], recommendation="SELL",
        )
        assert strategy.generate_signal(df, sentiment=sentiment) == "SHORT"

    def test_no_sentiment_means_no_filter(self, strategy):
        """Senza sentiment (None) il segnale tecnico passa direttamente."""
        df = _make_df(
            rsi=20.0, close=34490.0,
            volume=150.0, volume_ma=100.0, adx=15.0,
        )
        assert strategy.generate_signal(df, sentiment=None) == "LONG"

    def test_low_confidence_sentiment_is_ignored(self, strategy):
        """Sentiment con confidence bassa non blocca il segnale."""
        df = _make_df(
            rsi=20.0, close=34490.0,
            volume=150.0, volume_ma=100.0, adx=15.0,
        )
        sentiment = SentimentResult(
            sentiment_score=-0.8, confidence=0.1,
            top_events=["FUD"], recommendation="SELL",
        )
        assert strategy.generate_signal(df, sentiment=sentiment) == "LONG"


# ---------------------------------------------------------------------------
# Custom thresholds
# ---------------------------------------------------------------------------

class TestCustomThresholds:
    """La strategia deve rispettare i parametri personalizzati."""

    def test_custom_rsi_entry_oversold(self):
        """Parametro rsi_entry_oversold personalizzato."""
        strat = CombinedStrategy(rsi_entry_oversold=30.0)
        df = _make_df(
            rsi=28.0,
            close=34490.0,
            volume=150.0,
            volume_ma=100.0,
            adx=15.0,
        )
        assert strat.generate_signal(df) == "LONG"

    def test_custom_rsi_entry_overbought(self):
        """Parametro rsi_entry_overbought personalizzato."""
        strat = CombinedStrategy(rsi_entry_overbought=70.0)
        df = _make_df(
            rsi=72.0,
            close=35510.0,
            volume=150.0,
            volume_ma=100.0,
            adx=15.0,
        )
        assert strat.generate_signal(df) == "SHORT"

    def test_custom_adx_threshold(self):
        """Parametro adx_trend_threshold personalizzato."""
        strat = CombinedStrategy(adx_trend_threshold=35.0)
        df = _make_df(
            rsi=20.0,
            close=34490.0,
            volume=150.0,
            volume_ma=100.0,
            adx=30.0,  # sarebbe bloccato con threshold=25, ma non con 35
        )
        assert strat.generate_signal(df) == "LONG"
