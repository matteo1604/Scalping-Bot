"""Test per il modulo indicatori tecnici."""

import pandas as pd
import numpy as np
import pytest

from src.indicators.technical import add_indicators, add_prev_indicators


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


class TestAddIndicatorsNew:
    """Test per i nuovi indicatori: BB, ATR, ADX."""

    def test_adds_bb_columns(self, sample_ohlcv):
        """Deve aggiungere colonne bb_upper, bb_middle, bb_lower."""
        result = add_indicators(sample_ohlcv)
        assert "bb_upper" in result.columns
        assert "bb_middle" in result.columns
        assert "bb_lower" in result.columns

    def test_adds_atr_column(self, sample_ohlcv):
        """Deve aggiungere colonna atr."""
        result = add_indicators(sample_ohlcv)
        assert "atr" in result.columns

    def test_adds_adx_column(self, sample_ohlcv):
        """Deve aggiungere colonna adx."""
        result = add_indicators(sample_ohlcv)
        assert "adx" in result.columns

    def test_bb_upper_above_lower(self, sample_ohlcv):
        """bb_upper deve essere sempre >= bb_lower (dove non NaN)."""
        result = add_indicators(sample_ohlcv)
        valid = result.dropna(subset=["bb_upper", "bb_lower"])
        assert (valid["bb_upper"] >= valid["bb_lower"]).all()

    def test_bb_middle_between_bands(self, sample_ohlcv):
        """bb_middle deve essere tra bb_lower e bb_upper."""
        result = add_indicators(sample_ohlcv)
        valid = result.dropna(subset=["bb_upper", "bb_middle", "bb_lower"])
        assert (valid["bb_middle"] >= valid["bb_lower"]).all()
        assert (valid["bb_middle"] <= valid["bb_upper"]).all()

    def test_atr_non_negative(self, sample_ohlcv):
        """ATR deve essere >= 0."""
        result = add_indicators(sample_ohlcv)
        atr = result["atr"].dropna()
        assert (atr >= 0).all()

    def test_adx_bounded(self, sample_ohlcv):
        """ADX deve essere tra 0 e 100."""
        result = add_indicators(sample_ohlcv)
        adx = result["adx"].dropna()
        assert (adx >= 0).all()
        assert (adx <= 100).all()

    def test_custom_bb_period(self, sample_ohlcv):
        """Deve accettare bb_period personalizzato."""
        result = add_indicators(sample_ohlcv, bb_period=10)
        assert "bb_upper" in result.columns

    def test_custom_atr_period(self, sample_ohlcv):
        """Deve accettare atr_period personalizzato."""
        result = add_indicators(sample_ohlcv, atr_period=7)
        assert "atr" in result.columns

    def test_custom_adx_period(self, sample_ohlcv):
        """Deve accettare adx_period personalizzato."""
        result = add_indicators(sample_ohlcv, adx_period=7)
        assert "adx" in result.columns


class TestDirectionalIndicators:
    """Test per DI+ e DI- (indicatori direzionali per trend following)."""

    def test_adds_di_plus_column(self, sample_ohlcv):
        """Deve aggiungere colonna di_plus."""
        result = add_indicators(sample_ohlcv)
        assert "di_plus" in result.columns

    def test_adds_di_minus_column(self, sample_ohlcv):
        """Deve aggiungere colonna di_minus."""
        result = add_indicators(sample_ohlcv)
        assert "di_minus" in result.columns

    def test_di_plus_bounded(self, sample_ohlcv):
        """DI+ deve essere tra 0 e 100."""
        result = add_indicators(sample_ohlcv)
        di = result["di_plus"].dropna()
        assert len(di) > 0
        assert (di >= 0).all()
        assert (di <= 100).all()

    def test_di_minus_bounded(self, sample_ohlcv):
        """DI- deve essere tra 0 e 100."""
        result = add_indicators(sample_ohlcv)
        di = result["di_minus"].dropna()
        assert len(di) > 0
        assert (di >= 0).all()
        assert (di <= 100).all()

    def test_di_not_all_nan(self, sample_ohlcv):
        """DI+ e DI- non devono essere tutti NaN."""
        result = add_indicators(sample_ohlcv)
        assert result["di_plus"].notna().any()
        assert result["di_minus"].notna().any()


class TestAddPrevIndicators:
    """Test per add_prev_indicators."""

    def test_adds_prev_columns(self, sample_ohlcv):
        """Deve aggiungere ema_fast_prev e ema_slow_prev."""
        df = add_indicators(sample_ohlcv)
        result = add_prev_indicators(df)
        assert "ema_fast_prev" in result.columns
        assert "ema_slow_prev" in result.columns

    def test_prev_is_shifted(self, sample_ohlcv):
        """Le colonne _prev devono essere i valori della riga precedente."""
        df = add_indicators(sample_ohlcv)
        result = add_prev_indicators(df)
        # Usa righe dove EMA non e' NaN (dopo il warmup period)
        valid = result.dropna(subset=["ema_fast", "ema_fast_prev"])
        idx = valid.index[0]
        pos = result.index.get_loc(idx)
        assert result["ema_fast_prev"].iloc[pos] == result["ema_fast"].iloc[pos - 1]


class TestAddPrevDIIndicators:
    """Nuove colonne DI prev aggiunte da add_prev_indicators."""

    def test_adds_di_plus_prev(self, sample_ohlcv):
        df = add_indicators(sample_ohlcv)
        result = add_prev_indicators(df)
        assert "di_plus_prev" in result.columns

    def test_adds_di_minus_prev(self, sample_ohlcv):
        df = add_indicators(sample_ohlcv)
        result = add_prev_indicators(df)
        assert "di_minus_prev" in result.columns

    def test_di_plus_prev_is_shifted(self, sample_ohlcv):
        df = add_indicators(sample_ohlcv)
        result = add_prev_indicators(df)
        valid = result.dropna(subset=["di_plus", "di_plus_prev"])
        assert len(valid) > 0
        idx = valid.index[1]
        prev_idx = valid.index[0]
        assert result.loc[idx, "di_plus_prev"] == pytest.approx(result.loc[prev_idx, "di_plus"])

    def test_di_minus_prev_is_shifted(self, sample_ohlcv):
        df = add_indicators(sample_ohlcv)
        result = add_prev_indicators(df)
        valid = result.dropna(subset=["di_minus", "di_minus_prev"])
        assert len(valid) > 0
        idx = valid.index[1]
        prev_idx = valid.index[0]
        assert result.loc[idx, "di_minus_prev"] == pytest.approx(result.loc[prev_idx, "di_minus"])
