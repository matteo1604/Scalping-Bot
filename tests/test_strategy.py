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
        "di_plus": 20.0,
        "di_minus": 20.0,
        "ema_slow": 35000.0,
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
            adx=31.0,  # sopra ADX_TREND_THRESHOLD (30)
        )
        assert strategy.generate_signal(df) is None

    def test_high_adx_blocks_short_signal(self, strategy):
        """ADX > threshold blocca SHORT anche con RSI+BB corretti."""
        df = _make_df(
            rsi=80.0,
            close=35510.0,  # >= bb_upper (35500)
            volume=150.0,
            volume_ma=100.0,
            adx=31.0,  # sopra ADX_TREND_THRESHOLD (30)
        )
        assert strategy.generate_signal(df) is None

    def test_adx_exactly_at_threshold_allows_signal(self, strategy):
        """ADX esattamente uguale alla threshold non blocca il segnale."""
        df = _make_df(
            rsi=20.0,
            close=34490.0,
            volume=150.0,
            volume_ma=100.0,
            adx=30.0,  # uguale alla soglia (30) → non bloccato
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
    """Test per segnali LONG."""

    def test_long_rsi_moderate_with_bb(self, strategy):
        """LONG (cond A): RSI < 30 AND close <= bb_lower."""
        df = _make_df(
            rsi=28.0,
            close=34490.0,  # <= bb_lower (34500)
            volume=150.0,
            volume_ma=100.0,
            adx=15.0,
        )
        assert strategy.generate_signal(df) == "LONG"

    def test_long_rsi_extreme_without_bb(self, strategy):
        """LONG (cond B): RSI < 20 basta da solo, anche se close > bb_lower."""
        df = _make_df(
            rsi=18.0,
            close=34600.0,  # sopra bb_lower=34500 — non importa
            volume=150.0,
            volume_ma=100.0,
            adx=15.0,
        )
        assert strategy.generate_signal(df) == "LONG"

    def test_long_rsi_moderate_without_bb_gives_no_signal(self, strategy):
        """RSI < 30 ma close > bb_lower non basta (serve BB oppure RSI estremo)."""
        df = _make_df(
            rsi=28.0,
            close=34600.0,  # sopra bb_lower — condizione A non soddisfatta
            volume=150.0,
            volume_ma=100.0,
            adx=15.0,
        )
        assert strategy.generate_signal(df) is None

    def test_long_rsi_at_new_oversold_threshold(self, strategy):
        """LONG quando RSI == RSI_ENTRY_OVERSOLD (30) con close <= bb_lower."""
        df = _make_df(
            rsi=30.0,
            close=34490.0,
            volume=150.0,
            volume_ma=100.0,
            adx=15.0,
        )
        assert strategy.generate_signal(df) == "LONG"

    def test_no_long_when_rsi_above_oversold_and_no_bb(self, strategy):
        """Nessun LONG se RSI >= 30 e close non è sul BB lower."""
        df = _make_df(
            rsi=35.0,
            close=34600.0,
            volume=150.0,
            volume_ma=100.0,
            adx=15.0,
        )
        assert strategy.generate_signal(df) is None

    def test_no_long_when_close_above_bb_lower_and_rsi_not_extreme(self, strategy):
        """Nessun LONG se close > bb_lower e RSI non è estremo (>= 22)."""
        df = _make_df(
            rsi=23.0,
            close=34600.0,  # sopra bb_lower=34500; RSI=23 non è < 22
            volume=150.0,
            volume_ma=100.0,
            adx=15.0,
        )
        assert strategy.generate_signal(df) is None

    def test_long_volume_slightly_below_ma(self, strategy):
        """LONG se volume >= volume_ma * 0.8 (filtro volume rilassato)."""
        df = _make_df(
            rsi=28.0,
            close=34490.0,
            volume=95.0,      # 95 >= 100 * 0.8 = 80
            volume_ma=100.0,
            adx=15.0,
        )
        assert strategy.generate_signal(df) == "LONG"

    def test_no_long_when_volume_way_below_ma(self, strategy):
        """Nessun LONG se volume < volume_ma * 0.8."""
        df = _make_df(
            rsi=28.0,
            close=34490.0,
            volume=70.0,      # 70 < 100 * 0.8 = 80
            volume_ma=100.0,
            adx=15.0,
        )
        assert strategy.generate_signal(df) is None


# ---------------------------------------------------------------------------
# SHORT signal
# ---------------------------------------------------------------------------

class TestShortSignal:
    """Test per segnali SHORT."""

    def test_short_rsi_moderate_with_bb(self, strategy):
        """SHORT (cond A): RSI >= 70 AND close >= bb_upper."""
        df = _make_df(
            rsi=72.0,
            close=35510.0,  # >= bb_upper (35500)
            volume=150.0,
            volume_ma=100.0,
            adx=15.0,
        )
        assert strategy.generate_signal(df) == "SHORT"

    def test_short_rsi_extreme_without_bb(self, strategy):
        """SHORT (cond B): RSI > 80 basta da solo, anche se close < bb_upper."""
        df = _make_df(
            rsi=82.0,
            close=35400.0,  # sotto bb_upper=35500 — non importa
            volume=150.0,
            volume_ma=100.0,
            adx=15.0,
        )
        assert strategy.generate_signal(df) == "SHORT"

    def test_short_rsi_moderate_without_bb_gives_no_signal(self, strategy):
        """RSI >= 70 ma close < bb_upper non basta."""
        df = _make_df(
            rsi=72.0,
            close=35400.0,  # sotto bb_upper — condizione A non soddisfatta
            volume=150.0,
            volume_ma=100.0,
            adx=15.0,
        )
        assert strategy.generate_signal(df) is None

    def test_short_rsi_at_new_overbought_threshold(self, strategy):
        """SHORT quando RSI == RSI_ENTRY_OVERBOUGHT (70) con close >= bb_upper."""
        df = _make_df(
            rsi=70.0,
            close=35510.0,
            volume=150.0,
            volume_ma=100.0,
            adx=15.0,
        )
        assert strategy.generate_signal(df) == "SHORT"

    def test_no_short_when_rsi_below_overbought_and_no_bb(self, strategy):
        """Nessun SHORT se RSI < 70 e close non è sul BB upper."""
        df = _make_df(
            rsi=65.0,
            close=35400.0,
            volume=150.0,
            volume_ma=100.0,
            adx=15.0,
        )
        assert strategy.generate_signal(df) is None

    def test_no_short_when_close_below_bb_upper_and_rsi_not_extreme(self, strategy):
        """Nessun SHORT se close < bb_upper e RSI non è estremo (<= 78)."""
        df = _make_df(
            rsi=77.0,
            close=35400.0,  # sotto bb_upper; RSI=77 non è > 78
            volume=150.0,
            volume_ma=100.0,
            adx=15.0,
        )
        assert strategy.generate_signal(df) is None

    def test_short_volume_slightly_below_ma(self, strategy):
        """SHORT se volume >= volume_ma * 0.8 (filtro volume rilassato)."""
        df = _make_df(
            rsi=72.0,
            close=35510.0,
            volume=95.0,      # 95 >= 100 * 0.8 = 80
            volume_ma=100.0,
            adx=15.0,
        )
        assert strategy.generate_signal(df) == "SHORT"

    def test_no_short_when_volume_way_below_ma(self, strategy):
        """Nessun SHORT se volume < volume_ma * 0.8."""
        df = _make_df(
            rsi=72.0,
            close=35510.0,
            volume=70.0,      # 70 < 100 * 0.8 = 80
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
        """Parametro rsi_entry_oversold personalizzato (cond A più stretta)."""
        strat = CombinedStrategy(rsi_entry_oversold=25.0)  # più restrittivo del default 30
        df = _make_df(
            rsi=23.0,
            close=34490.0,
            volume=150.0,
            volume_ma=100.0,
            adx=15.0,
        )
        assert strat.generate_signal(df) == "LONG"

    def test_custom_rsi_entry_overbought(self):
        """Parametro rsi_entry_overbought personalizzato (cond A più stretta)."""
        strat = CombinedStrategy(rsi_entry_overbought=75.0)  # più restrittivo del default 70
        df = _make_df(
            rsi=77.0,
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

    def test_custom_volume_filter_ratio(self):
        """Parametro volume_filter_ratio personalizzato (più restrittivo)."""
        strat = CombinedStrategy(volume_filter_ratio=1.0)  # richiede volume >= volume_ma
        df = _make_df(
            rsi=28.0,
            close=34490.0,
            volume=95.0,      # 95 < 100 * 1.0 = 100 → bloccato
            volume_ma=100.0,
            adx=15.0,
        )
        assert strat.generate_signal(df) is None

    def test_custom_rsi_extreme_oversold(self):
        """Parametro rsi_extreme_oversold personalizzato."""
        strat = CombinedStrategy(rsi_extreme_oversold=25.0)  # soglia estrema più alta
        df = _make_df(
            rsi=23.0,
            close=34600.0,  # sopra bb_lower — serve cond B
            volume=150.0,
            volume_ma=100.0,
            adx=15.0,
        )
        assert strat.generate_signal(df) == "LONG"


# ---------------------------------------------------------------------------
# Trend following (ADX > threshold)
# ---------------------------------------------------------------------------

class TestTrendFollowing:
    """Trend following: DI+/DI- + RSI pullback quando ADX > threshold."""

    def test_long_in_uptrend_with_rsi_pullback(self, strategy):
        """LONG in uptrend: DI+ > DI-, close > ema_slow, RSI 40-55, close > bb_middle."""
        df = _make_df(
            adx=35.0,          # sopra threshold → trend mode
            di_plus=30.0,      # DI+ > DI- → uptrend
            di_minus=15.0,
            rsi=48.0,          # pullback zone 40-55
            close=35100.0,     # close > ema_slow (35000) e > bb_middle (35000)
            ema_slow=35000.0,
            volume=150.0,
            volume_ma=100.0,
        )
        assert strategy.generate_signal(df) == "LONG"

    def test_no_long_in_uptrend_rsi_too_low(self, strategy):
        """No LONG in uptrend se RSI < 40 (non è pullback, è ipervenduto)."""
        df = _make_df(
            adx=35.0,
            di_plus=30.0,
            di_minus=15.0,
            rsi=35.0,          # sotto la pullback zone (40)
            close=35100.0,
            ema_slow=35000.0,
            volume=150.0,
            volume_ma=100.0,
        )
        assert strategy.generate_signal(df) is None

    def test_no_long_in_uptrend_rsi_too_high(self, strategy):
        """No LONG in uptrend se RSI > 55 (momentum già esaurito)."""
        df = _make_df(
            adx=35.0,
            di_plus=30.0,
            di_minus=15.0,
            rsi=60.0,          # sopra la pullback zone (55)
            close=35100.0,
            ema_slow=35000.0,
            volume=150.0,
            volume_ma=100.0,
        )
        assert strategy.generate_signal(df) is None

    def test_no_long_in_uptrend_close_below_ema_slow(self, strategy):
        """No LONG in uptrend se close <= ema_slow (trend non confermato dal prezzo)."""
        df = _make_df(
            adx=35.0,
            di_plus=30.0,
            di_minus=15.0,
            rsi=48.0,
            close=34950.0,     # close < ema_slow (35000)
            ema_slow=35000.0,
            volume=150.0,
            volume_ma=100.0,
        )
        assert strategy.generate_signal(df) is None

    def test_no_long_when_di_minus_greater_than_di_plus(self, strategy):
        """No LONG in trend mode se DI- > DI+ (downtrend)."""
        df = _make_df(
            adx=35.0,
            di_plus=15.0,
            di_minus=30.0,     # downtrend
            rsi=48.0,
            close=35100.0,
            ema_slow=35000.0,
            volume=150.0,
            volume_ma=100.0,
        )
        assert strategy.generate_signal(df) is None

    def test_short_in_downtrend_with_rsi_pullback(self, strategy):
        """SHORT in downtrend: DI- > DI+, close < ema_slow, RSI 45-60, close < bb_middle."""
        df = _make_df(
            adx=35.0,          # sopra threshold → trend mode
            di_plus=15.0,      # DI- > DI+ → downtrend
            di_minus=30.0,
            rsi=52.0,          # pullback zone 45-60
            close=34900.0,     # close < ema_slow (35000) e < bb_middle (35000)
            ema_slow=35000.0,
            volume=150.0,
            volume_ma=100.0,
        )
        assert strategy.generate_signal(df) == "SHORT"

    def test_no_short_in_downtrend_rsi_too_high(self, strategy):
        """No SHORT in downtrend se RSI > 60 (non è pullback)."""
        df = _make_df(
            adx=35.0,
            di_plus=15.0,
            di_minus=30.0,
            rsi=65.0,          # sopra la pullback zone (60)
            close=34900.0,
            ema_slow=35000.0,
            volume=150.0,
            volume_ma=100.0,
        )
        assert strategy.generate_signal(df) is None

    def test_no_short_in_downtrend_close_above_ema_slow(self, strategy):
        """No SHORT in downtrend se close >= ema_slow."""
        df = _make_df(
            adx=35.0,
            di_plus=15.0,
            di_minus=30.0,
            rsi=52.0,
            close=35050.0,     # close > ema_slow (35000)
            ema_slow=35000.0,
            volume=150.0,
            volume_ma=100.0,
        )
        assert strategy.generate_signal(df) is None

    def test_trend_signal_blocked_by_volume(self, strategy):
        """Trend following richiede volume ok come mean reversion."""
        df = _make_df(
            adx=35.0,
            di_plus=30.0,
            di_minus=15.0,
            rsi=48.0,
            close=35100.0,
            ema_slow=35000.0,
            volume=50.0,       # 50 < 100 * 0.8 = 80 → bloccato
            volume_ma=100.0,
        )
        assert strategy.generate_signal(df) is None

    def test_mean_reversion_unchanged_when_adx_low(self, strategy):
        """Con ADX basso la mean reversion funziona come prima."""
        df = _make_df(
            adx=15.0,          # sotto threshold → mean reversion
            rsi=20.0,
            close=34490.0,     # <= bb_lower
            volume=150.0,
            volume_ma=100.0,
        )
        assert strategy.generate_signal(df) == "LONG"


class TestShouldExit:
    """Test per should_exit() — exit basate su segnali tecnici."""

    def test_mean_reversion_long_exit_at_rsi_50(self, strategy):
        """Mean rev LONG esce quando RSI >= 50."""
        df = _make_df(rsi=52.0, adx=15.0, di_plus=20.0, di_minus=20.0)
        pos = {"side": "LONG", "strategy": "reversion"}
        assert strategy.should_exit(df, pos) == "signal_exit"

    def test_mean_reversion_long_no_exit_below_50(self, strategy):
        """Mean rev LONG non esce se RSI < 50."""
        df = _make_df(rsi=45.0, adx=15.0, di_plus=20.0, di_minus=20.0)
        pos = {"side": "LONG", "strategy": "reversion"}
        assert strategy.should_exit(df, pos) is None

    def test_mean_reversion_short_exit_at_rsi_50(self, strategy):
        """Mean rev SHORT esce quando RSI <= 50."""
        df = _make_df(rsi=48.0, adx=15.0, di_plus=20.0, di_minus=20.0)
        pos = {"side": "SHORT", "strategy": "reversion"}
        assert strategy.should_exit(df, pos) == "signal_exit"

    def test_mean_reversion_short_no_exit_above_50(self, strategy):
        """Mean rev SHORT non esce se RSI > 50."""
        df = _make_df(rsi=55.0, adx=15.0, di_plus=20.0, di_minus=20.0)
        pos = {"side": "SHORT", "strategy": "reversion"}
        assert strategy.should_exit(df, pos) is None

    def test_trend_long_exit_on_di_cross(self, strategy):
        """Trend LONG esce quando DI- > DI+."""
        df = _make_df(rsi=50.0, adx=35.0, di_plus=18.0, di_minus=25.0)
        pos = {"side": "LONG", "strategy": "trend"}
        assert strategy.should_exit(df, pos) == "signal_exit"

    def test_trend_long_no_exit_when_di_aligned(self, strategy):
        """Trend LONG non esce se DI+ > DI-."""
        df = _make_df(rsi=50.0, adx=35.0, di_plus=28.0, di_minus=18.0)
        pos = {"side": "LONG", "strategy": "trend"}
        assert strategy.should_exit(df, pos) is None

    def test_trend_short_exit_on_di_cross(self, strategy):
        """Trend SHORT esce quando DI+ > DI-."""
        df = _make_df(rsi=50.0, adx=35.0, di_plus=28.0, di_minus=18.0)
        pos = {"side": "SHORT", "strategy": "trend"}
        assert strategy.should_exit(df, pos) == "signal_exit"

    def test_trend_short_no_exit_when_di_aligned(self, strategy):
        """Trend SHORT non esce se DI- > DI+."""
        df = _make_df(rsi=50.0, adx=35.0, di_plus=15.0, di_minus=28.0)
        pos = {"side": "SHORT", "strategy": "trend"}
        assert strategy.should_exit(df, pos) is None

    def test_no_exit_with_nan_indicators(self, strategy):
        """Nessun exit se ci sono NaN."""
        df = _make_df(rsi=float("nan"))
        pos = {"side": "LONG", "strategy": "reversion"}
        assert strategy.should_exit(df, pos) is None

    def test_missing_strategy_defaults_to_reversion(self, strategy):
        """Se manca il campo 'strategy', usa reversion come default."""
        df = _make_df(rsi=52.0, adx=15.0, di_plus=20.0, di_minus=20.0)
        pos = {"side": "LONG"}  # no "strategy" key
        assert strategy.should_exit(df, pos) == "signal_exit"
