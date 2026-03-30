# Fase 2 — Implementazione Strategia Tecnica

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementare il calcolo degli indicatori tecnici (EMA, RSI, Volume MA) e la strategia combinata che genera segnali LONG/SHORT basati su crossover EMA + filtri RSI/Volume.

**Architecture:** `indicators/technical.py` espone una funzione `add_indicators(df)` che arricchisce un DataFrame OHLCV con le colonne degli indicatori. `strategies/combined.py` espone una classe `CombinedStrategy` che riceve un DataFrame con indicatori e genera segnali di trading. Il sentiment (Fase 4) è opzionale e per ora ignorato.

**Tech Stack:** Python 3.10+, pandas, ta (technical analysis library), pytest

---

### Task 1: Implementare indicatori tecnici (`src/indicators/technical.py`)

**Files:**
- Modify: `src/indicators/technical.py`
- Create: `tests/test_indicators.py`

- [ ] **Step 1: Scrivere i test per add_indicators**

```python
# tests/test_indicators.py
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
```

- [ ] **Step 2: Eseguire i test per verificare che falliscano**

Run: `pytest tests/test_indicators.py -v`
Expected: FAIL — `add_indicators` non esiste.

- [ ] **Step 3: Implementare add_indicators**

```python
# src/indicators/technical.py
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
```

- [ ] **Step 4: Eseguire i test e verificare che passino**

Run: `pytest tests/test_indicators.py -v`
Expected: 8 PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/indicators/technical.py tests/test_indicators.py
git commit -m "feat: implement technical indicators (EMA, RSI, Volume MA)"
```

---

### Task 2: Implementare strategia combinata (`src/strategies/combined.py`)

**Files:**
- Modify: `src/strategies/combined.py`
- Create: `tests/test_strategy.py`

- [ ] **Step 1: Scrivere i test per CombinedStrategy**

```python
# tests/test_strategy.py
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
            ema_fast=35100.0,     # fast sopra slow ora
            ema_slow=35050.0,
            ema_fast_prev=35000.0,  # fast sotto slow prima
            ema_slow_prev=35050.0,
            rsi=55.0,             # sotto 70
            volume=150.0,         # sopra volume_ma (100)
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
            ema_fast=35000.0,     # fast sotto slow ora
            ema_slow=35050.0,
            ema_fast_prev=35100.0,  # fast sopra slow prima
            ema_slow_prev=35050.0,
            rsi=45.0,             # sopra 30
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
            ema_fast_prev=35100.0,  # gia' sopra prima
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
```

- [ ] **Step 2: Eseguire i test per verificare che falliscano**

Run: `pytest tests/test_strategy.py -v`
Expected: FAIL — `CombinedStrategy` non esiste.

- [ ] **Step 3: Implementare CombinedStrategy**

```python
# src/strategies/combined.py
"""Strategia combinata: EMA Crossover + RSI + Volume + Sentiment.

Logica segnali:
- LONG: EMA9 > EMA21 (cross up) + RSI < 70 + Volume > media + Sentiment > threshold
- SHORT: EMA9 < EMA21 (cross down) + RSI > 30 + Volume > media + Sentiment < -threshold
- Il sentiment modifica anche il position sizing
"""

import pandas as pd

from config.settings import RSI_OVERBOUGHT, RSI_OVERSOLD
from src.utils.logger import setup_logger

logger = setup_logger("strategy")


class CombinedStrategy:
    """Strategia di scalping basata su EMA crossover con filtri RSI e Volume.

    Args:
        rsi_overbought: Soglia RSI overbought (default: 70).
        rsi_oversold: Soglia RSI oversold (default: 30).
    """

    def __init__(
        self,
        rsi_overbought: float = RSI_OVERBOUGHT,
        rsi_oversold: float = RSI_OVERSOLD,
    ) -> None:
        self.rsi_overbought = rsi_overbought
        self.rsi_oversold = rsi_oversold

    def generate_signal(self, df: pd.DataFrame) -> str | None:
        """Genera un segnale di trading dall'ultima riga del DataFrame.

        Il DataFrame deve contenere le colonne:
        ema_fast, ema_slow, ema_fast_prev, ema_slow_prev, rsi, volume, volume_ma.

        Args:
            df: DataFrame con indicatori calcolati.

        Returns:
            "LONG", "SHORT", o None se nessun segnale.
        """
        row = df.iloc[-1]

        # Controlla NaN
        required = ["ema_fast", "ema_slow", "ema_fast_prev", "ema_slow_prev",
                     "rsi", "volume", "volume_ma"]
        if any(pd.isna(row.get(col)) for col in required):
            return None

        ema_fast = row["ema_fast"]
        ema_slow = row["ema_slow"]
        ema_fast_prev = row["ema_fast_prev"]
        ema_slow_prev = row["ema_slow_prev"]
        rsi = row["rsi"]
        volume = row["volume"]
        volume_ma = row["volume_ma"]

        # Crossover detection
        bullish_cross = ema_fast_prev <= ema_slow_prev and ema_fast > ema_slow
        bearish_cross = ema_fast_prev >= ema_slow_prev and ema_fast < ema_slow

        # Volume filter
        volume_ok = volume > volume_ma

        # LONG
        if bullish_cross and rsi < self.rsi_overbought and volume_ok:
            logger.info("Segnale LONG: EMA cross up, RSI=%.1f, Vol=%.1f", rsi, volume)
            return "LONG"

        # SHORT
        if bearish_cross and rsi > self.rsi_oversold and volume_ok:
            logger.info("Segnale SHORT: EMA cross down, RSI=%.1f, Vol=%.1f", rsi, volume)
            return "SHORT"

        return None
```

- [ ] **Step 4: Eseguire i test e verificare che passino**

Run: `pytest tests/test_strategy.py -v`
Expected: 7 PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/strategies/combined.py tests/test_strategy.py
git commit -m "feat: implement CombinedStrategy with EMA crossover, RSI and volume filters"
```

---

### Task 3: Helper per preparare il DataFrame con colonne _prev (`src/indicators/technical.py`)

**Files:**
- Modify: `src/indicators/technical.py`
- Modify: `tests/test_indicators.py`

- [ ] **Step 1: Aggiungere test per add_prev_indicators**

Aggiungere in fondo a `tests/test_indicators.py`:

```python
from src.indicators.technical import add_prev_indicators


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
        # La seconda riga: prev deve essere uguale al valore della prima riga
        assert result["ema_fast_prev"].iloc[1] == result["ema_fast"].iloc[0]
```

- [ ] **Step 2: Eseguire i test per verificare che falliscano**

Run: `pytest tests/test_indicators.py::TestAddPrevIndicators -v`
Expected: FAIL — `add_prev_indicators` non esiste.

- [ ] **Step 3: Implementare add_prev_indicators**

Aggiungere in fondo a `src/indicators/technical.py`:

```python
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
```

- [ ] **Step 4: Eseguire i test e verificare che passino**

Run: `pytest tests/test_indicators.py -v`
Expected: 10 PASSED (8 precedenti + 2 nuovi).

- [ ] **Step 5: Commit**

```bash
git add src/indicators/technical.py tests/test_indicators.py
git commit -m "feat: add prev indicator columns for crossover detection"
```

---

### Task 4: Verifica finale — tutti i test

- [ ] **Step 1: Eseguire tutti i test unitari**

```bash
pytest tests/ -v --ignore=tests/test_exchange_integration.py
```

Expected: tutti PASSED (13 precedenti + 10 + 7 = ~23 test unitari).

- [ ] **Step 2: Commit finale se necessario**

```bash
git status
```
