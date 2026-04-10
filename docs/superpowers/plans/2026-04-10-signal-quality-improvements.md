# Signal Quality Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aumentare il win rate dal ~7% verso il 40%+ aggiungendo RSI turning confirmation alla strategia e HTF filter nel backtester.

**Architecture:** (1) `_mean_reversion_signal` e `_trend_following_signal` ricevono `df` invece di `row` e richiedono che RSI/DI stia già girando nella direzione del trade prima di emettere segnale. (2) Il backtester pre-calcola i dati 1h dal resample del 5min e applica `HTFFilter.allows_signal()` a ogni segnale generato, replicando il comportamento live di `main.py`.

**Tech Stack:** Python 3.11, pandas, ta, pytest. File toccati: `src/indicators/technical.py`, `src/strategies/combined.py`, `src/backtesting/engine.py`, `tests/test_indicators.py`, `tests/test_strategy.py`.

---

## File map

| File | Modifica |
|---|---|
| `src/indicators/technical.py` | Aggiunge `di_plus_prev`, `di_minus_prev` in `add_prev_indicators` |
| `src/strategies/combined.py` | `_mean_reversion_signal(df)` e `_trend_following_signal(df)` ricevono `df`; aggiunto turning check |
| `src/backtesting/engine.py` | Pre-calcola 1h indicators all'inizio di `run()`; applica HTFFilter prima di `pending_signal` |
| `tests/test_indicators.py` | Aggiunge test per le nuove colonne `_prev` |
| `tests/test_strategy.py` | Aggiorna `_make_df` a 2 righe; aggiunge `rsi_prev`/`di_prev` params; nuovi test turning |

---

## Task 1: Aggiungere `di_plus_prev` e `di_minus_prev` in `add_prev_indicators`

**Files:**
- Modify: `src/indicators/technical.py`
- Test: `tests/test_indicators.py`

- [ ] **Step 1: Scrivi i test fallenti**

Aggiungi questa classe in fondo a `tests/test_indicators.py`:

```python
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
```

- [ ] **Step 2: Verifica che i test falliscano**

```bash
pytest tests/test_indicators.py::TestAddPrevDIIndicators -v
```

Expected: 4 FAIL con `KeyError: 'di_plus_prev'`

- [ ] **Step 3: Implementa**

In `src/indicators/technical.py`, nella funzione `add_prev_indicators`, aggiungi le due righe:

```python
def add_prev_indicators(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result["ema_fast_prev"] = result["ema_fast"].shift(1)
    result["ema_slow_prev"] = result["ema_slow"].shift(1)
    result["di_plus_prev"] = result["di_plus"].shift(1)   # NUOVO
    result["di_minus_prev"] = result["di_minus"].shift(1) # NUOVO
    return result
```

- [ ] **Step 4: Verifica che i test passino**

```bash
pytest tests/test_indicators.py -v
```

Expected: tutti PASS (inclusi i 4 nuovi)

- [ ] **Step 5: Commit**

```bash
git add src/indicators/technical.py tests/test_indicators.py
git commit -m "feat: add di_plus_prev and di_minus_prev to add_prev_indicators"
```

---

## Task 2: RSI turning confirmation in mean reversion

**Files:**
- Modify: `src/strategies/combined.py`
- Modify: `tests/test_strategy.py`

### Parte A — Aggiorna `_make_df` e i test esistenti

- [ ] **Step 1: Aggiorna `_make_df` in `tests/test_strategy.py`**

Sostituisci l'intera funzione `_make_df`:

```python
def _make_df(rsi_prev: float | None = None, **overrides) -> pd.DataFrame:
    """Helper: crea un DataFrame a DUE righe con indicatori.

    La riga [0] è il candle precedente (prev), la riga [1] è quello corrente.
    rsi_prev: RSI della riga precedente. Default = stesso RSI del corrente (nessun turning).
    Per testare LONG: passa rsi_prev < rsi corrente (RSI risale → turning up).
    Per testare SHORT: passa rsi_prev > rsi corrente (RSI scende → turning down).
    """
    defaults = {
        "open": 35000.0, "high": 35100.0, "low": 34900.0, "close": 35000.0,
        "volume": 150.0, "rsi": 50.0, "volume_ma": 100.0,
        "bb_upper": 35500.0, "bb_middle": 35000.0, "bb_lower": 34500.0,
        "atr": 200.0, "adx": 15.0, "di_plus": 20.0, "di_minus": 20.0,
        "ema_slow": 35000.0,
    }
    defaults.update(overrides)
    prev = defaults.copy()
    if rsi_prev is not None:
        prev["rsi"] = rsi_prev
    idx = pd.to_datetime(["2026-01-01 00:00", "2026-01-01 00:05"])
    return pd.DataFrame([prev, defaults], index=idx)
```

- [ ] **Step 2: Aggiorna i test che assertiscono "LONG" (mean reversion)**

Per ogni test che assertisce `== "LONG"` con RSI in zona oversold, aggiungi `rsi_prev=rsi - 3` (il RSI era più basso nel candle prev, ora risale = turning up). Schema: cerca tutti i `_make_df(rsi=X, ...)` che si aspettano `"LONG"` e aggiungi `rsi_prev=X-3`.

Aggiorna questi test in `tests/test_strategy.py`:

```python
# TestADXRegimeFilter
def test_adx_exactly_at_threshold_allows_signal(self, strategy):
    df = _make_df(rsi=20.0, rsi_prev=17.0, close=34490.0, volume=150.0, volume_ma=100.0, adx=30.0)
    assert strategy.generate_signal(df) == "LONG"

def test_low_adx_allows_signals(self, strategy):
    df = _make_df(rsi=20.0, rsi_prev=17.0, close=34490.0, volume=150.0, volume_ma=100.0, adx=10.0)
    assert strategy.generate_signal(df) == "LONG"

# TestLongSignal
def test_long_rsi_moderate_with_bb(self, strategy):
    df = _make_df(rsi=28.0, rsi_prev=25.0, close=34490.0, volume=150.0, volume_ma=100.0, adx=15.0)
    assert strategy.generate_signal(df) == "LONG"

def test_long_rsi_extreme_without_bb(self, strategy):
    df = _make_df(rsi=18.0, rsi_prev=15.0, close=34600.0, volume=150.0, volume_ma=100.0, adx=15.0)
    assert strategy.generate_signal(df) == "LONG"

def test_long_rsi_at_new_oversold_threshold(self, strategy):
    df = _make_df(rsi=30.0, rsi_prev=27.0, close=34490.0, volume=150.0, volume_ma=100.0, adx=15.0)
    assert strategy.generate_signal(df) == "LONG"

def test_long_volume_slightly_below_ma(self, strategy):
    df = _make_df(rsi=28.0, rsi_prev=25.0, close=34490.0, volume=95.0, volume_ma=100.0, adx=15.0)
    assert strategy.generate_signal(df) == "LONG"

# TestShortSignal
def test_short_rsi_moderate_with_bb(self, strategy):
    df = _make_df(rsi=72.0, rsi_prev=75.0, close=35510.0, volume=150.0, volume_ma=100.0, adx=15.0)
    assert strategy.generate_signal(df) == "SHORT"

def test_short_rsi_extreme_without_bb(self, strategy):
    df = _make_df(rsi=82.0, rsi_prev=85.0, close=35400.0, volume=150.0, volume_ma=100.0, adx=15.0)
    assert strategy.generate_signal(df) == "SHORT"

def test_short_rsi_at_new_overbought_threshold(self, strategy):
    df = _make_df(rsi=70.0, rsi_prev=73.0, close=35510.0, volume=150.0, volume_ma=100.0, adx=15.0)
    assert strategy.generate_signal(df) == "SHORT"

def test_short_volume_slightly_below_ma(self, strategy):
    df = _make_df(rsi=72.0, rsi_prev=75.0, close=35510.0, volume=95.0, volume_ma=100.0, adx=15.0)
    assert strategy.generate_signal(df) == "SHORT"

# TestSentimentFilter — aggiorna quelli che aspettano LONG/SHORT o che testano il blocco
def test_long_blocked_by_bearish_sentiment(self, strategy):
    df = _make_df(rsi=20.0, rsi_prev=17.0, close=34490.0, volume=150.0, volume_ma=100.0, adx=15.0)
    sentiment = SentimentResult(sentiment_score=-0.5, confidence=0.8, top_events=["Crash"], recommendation="SELL")
    assert strategy.generate_signal(df, sentiment=sentiment) is None

def test_long_allowed_by_bullish_sentiment(self, strategy):
    df = _make_df(rsi=20.0, rsi_prev=17.0, close=34490.0, volume=150.0, volume_ma=100.0, adx=15.0)
    sentiment = SentimentResult(sentiment_score=0.5, confidence=0.8, top_events=["Rally"], recommendation="BUY")
    assert strategy.generate_signal(df, sentiment=sentiment) == "LONG"

def test_short_blocked_by_bullish_sentiment(self, strategy):
    df = _make_df(rsi=80.0, rsi_prev=83.0, close=35510.0, volume=150.0, volume_ma=100.0, adx=15.0)
    sentiment = SentimentResult(sentiment_score=0.5, confidence=0.8, top_events=["Rally"], recommendation="BUY")
    assert strategy.generate_signal(df, sentiment=sentiment) is None

def test_short_allowed_by_bearish_sentiment(self, strategy):
    df = _make_df(rsi=80.0, rsi_prev=83.0, close=35510.0, volume=150.0, volume_ma=100.0, adx=15.0)
    sentiment = SentimentResult(sentiment_score=-0.5, confidence=0.8, top_events=["Crash"], recommendation="SELL")
    assert strategy.generate_signal(df, sentiment=sentiment) == "SHORT"

def test_no_sentiment_means_no_filter(self, strategy):
    df = _make_df(rsi=20.0, rsi_prev=17.0, close=34490.0, volume=150.0, volume_ma=100.0, adx=15.0)
    assert strategy.generate_signal(df, sentiment=None) == "LONG"

def test_low_confidence_sentiment_is_ignored(self, strategy):
    df = _make_df(rsi=20.0, rsi_prev=17.0, close=34490.0, volume=150.0, volume_ma=100.0, adx=15.0)
    sentiment = SentimentResult(sentiment_score=-0.8, confidence=0.1, top_events=["FUD"], recommendation="SELL")
    assert strategy.generate_signal(df, sentiment=sentiment) == "LONG"

# TestCustomThresholds
def test_custom_rsi_entry_oversold(self):
    strat = CombinedStrategy(rsi_entry_oversold=25.0)
    df = _make_df(rsi=23.0, rsi_prev=20.0, close=34490.0, volume=150.0, volume_ma=100.0, adx=15.0)
    assert strat.generate_signal(df) == "LONG"

def test_custom_rsi_entry_overbought(self):
    strat = CombinedStrategy(rsi_entry_overbought=75.0)
    df = _make_df(rsi=77.0, rsi_prev=80.0, close=35510.0, volume=150.0, volume_ma=100.0, adx=15.0)
    assert strat.generate_signal(df) == "SHORT"

def test_custom_adx_threshold(self):
    strat = CombinedStrategy(adx_trend_threshold=35.0)
    df = _make_df(rsi=20.0, rsi_prev=17.0, close=34490.0, volume=150.0, volume_ma=100.0, adx=30.0)
    assert strat.generate_signal(df) == "LONG"

def test_custom_rsi_extreme_oversold(self):
    strat = CombinedStrategy(rsi_extreme_oversold=25.0)
    df = _make_df(rsi=23.0, rsi_prev=20.0, close=34600.0, volume=150.0, volume_ma=100.0, adx=15.0)
    assert strat.generate_signal(df) == "LONG"
```

- [ ] **Step 3: Aggiungi la classe `TestRSITurningConfirmation`**

Aggiungi in fondo a `tests/test_strategy.py`:

```python
class TestRSITurningConfirmation:
    """Il turning del RSI è richiesto prima di emettere segnale mean reversion."""

    def test_no_long_when_rsi_still_falling(self, strategy):
        """LONG bloccato se RSI continua a scendere (RSI prev > RSI current)."""
        df = _make_df(
            rsi=28.0, rsi_prev=31.0,  # RSI scende 31→28 = ancora in momentum ribassista
            close=34490.0, volume=150.0, volume_ma=100.0, adx=15.0,
        )
        assert strategy.generate_signal(df) is None

    def test_no_short_when_rsi_still_rising(self, strategy):
        """SHORT bloccato se RSI continua a salire (RSI prev < RSI current)."""
        df = _make_df(
            rsi=72.0, rsi_prev=69.0,  # RSI sale 69→72 = ancora in momentum rialzista
            close=35510.0, volume=150.0, volume_ma=100.0, adx=15.0,
        )
        assert strategy.generate_signal(df) is None

    def test_long_when_rsi_turning_up(self, strategy):
        """LONG emesso se RSI risale dal minimo (turning up)."""
        df = _make_df(
            rsi=28.0, rsi_prev=25.0,  # RSI sale 25→28 = inversione
            close=34490.0, volume=150.0, volume_ma=100.0, adx=15.0,
        )
        assert strategy.generate_signal(df) == "LONG"

    def test_short_when_rsi_turning_down(self, strategy):
        """SHORT emesso se RSI scende dal massimo (turning down)."""
        df = _make_df(
            rsi=72.0, rsi_prev=75.0,  # RSI scende 75→72 = inversione
            close=35510.0, volume=150.0, volume_ma=100.0, adx=15.0,
        )
        assert strategy.generate_signal(df) == "SHORT"

    def test_no_signal_with_single_row_df(self, strategy):
        """Con df a singola riga, nessun segnale (impossibile calcolare il turning)."""
        defaults = {
            "open": 35000.0, "high": 35100.0, "low": 34900.0, "close": 34490.0,
            "volume": 150.0, "rsi": 20.0, "volume_ma": 100.0,
            "bb_upper": 35500.0, "bb_middle": 35000.0, "bb_lower": 34500.0,
            "atr": 200.0, "adx": 15.0, "di_plus": 20.0, "di_minus": 20.0,
            "ema_slow": 35000.0,
        }
        df = pd.DataFrame([defaults], index=pd.to_datetime(["2026-01-01"]))
        assert strategy.generate_signal(df) is None
```

- [ ] **Step 4: Verifica che i test falliscano**

```bash
pytest tests/test_strategy.py -v 2>&1 | tail -20
```

Expected: vari FAIL — i test "no signal" falliscono perché la strategia ancora emette segnali, i test "turning" falliscono perché il check non esiste.

### Parte B — Implementa il turning check in `combined.py`

- [ ] **Step 5: Aggiorna `_mean_reversion_signal`**

In `src/strategies/combined.py`, modifica la firma di `_mean_reversion_signal` da `(self, row)` a `(self, df)` e aggiungi il turning check:

```python
def _mean_reversion_signal(self, df: pd.DataFrame) -> str | None:
    """Genera segnale mean reversion (ADX <= threshold).

    Condizioni LONG:
    - A: RSI <= rsi_entry_oversold AND close <= bb_lower AND RSI in risalita
    - B: RSI < rsi_extreme_oversold AND RSI in risalita

    Condizioni SHORT:
    - A: RSI >= rsi_entry_overbought AND close >= bb_upper AND RSI in discesa
    - B: RSI > rsi_extreme_overbought AND RSI in discesa

    Il "turning" richiede almeno 2 candele: len(df) < 2 → None.
    """
    if len(df) < 2:
        return None

    row = df.iloc[-1]
    prev_row = df.iloc[-2]

    rsi = row["rsi"]
    prev_rsi = prev_row["rsi"]
    close = row["close"]
    bb_upper = row["bb_upper"]
    bb_lower = row["bb_lower"]

    rsi_turning_up = rsi > prev_rsi      # RSI risale = momentum esaurito al ribasso
    rsi_turning_down = rsi < prev_rsi    # RSI scende = momentum esaurito al rialzo

    long_cond_a = rsi <= self.rsi_entry_oversold and close <= bb_lower and rsi_turning_up
    long_cond_b = rsi < self.rsi_extreme_oversold and rsi_turning_up
    if long_cond_a or long_cond_b:
        logger.info(
            "Segnale LONG (mean rev): RSI=%.1f (prev=%.1f), Close=%.2f, BB_lower=%.2f (cond_%s)",
            rsi, prev_rsi, close, bb_lower, "A" if long_cond_a else "B",
        )
        return "LONG"

    short_cond_a = rsi >= self.rsi_entry_overbought and close >= bb_upper and rsi_turning_down
    short_cond_b = rsi > self.rsi_extreme_overbought and rsi_turning_down
    if short_cond_a or short_cond_b:
        logger.info(
            "Segnale SHORT (mean rev): RSI=%.1f (prev=%.1f), Close=%.2f, BB_upper=%.2f (cond_%s)",
            rsi, prev_rsi, close, bb_upper, "A" if short_cond_a else "B",
        )
        return "SHORT"

    logger.debug(
        "No signal (mean rev): RSI=%.1f (prev=%.1f), close=%.1f",
        rsi, prev_rsi, close,
    )
    return None
```

- [ ] **Step 6: Aggiorna la chiamata in `generate_signal`**

Nella stessa funzione `generate_signal`, la chiamata a `_mean_reversion_signal` cambia da `(row)` a `(df)`:

```python
# Prima (riga ~142):
signal = self._mean_reversion_signal(row)

# Dopo:
signal = self._mean_reversion_signal(df)
```

- [ ] **Step 7: Verifica che i test passino**

```bash
pytest tests/test_strategy.py -v 2>&1 | grep -E "PASSED|FAILED|ERROR"
```

Expected: solo i test trend (TestTrendFollowing) ancora FAIL — li fixiamo nel Task 3. Tutti i test mean reversion PASS.

- [ ] **Step 8: Commit**

```bash
git add src/strategies/combined.py tests/test_strategy.py
git commit -m "feat: add RSI turning confirmation to mean reversion signals"
```

---

## Task 3: DI turning confirmation in trend following

**Files:**
- Modify: `src/strategies/combined.py`
- Modify: `tests/test_strategy.py`

- [ ] **Step 1: Aggiorna `_make_df` con parametri DI prev**

Estendi `_make_df` per supportare `di_plus_prev` e `di_minus_prev`. Sostituisci la firma nella funzione già aggiornata nel Task 2:

```python
def _make_df(
    rsi_prev: float | None = None,
    di_plus_prev: float | None = None,
    di_minus_prev: float | None = None,
    **overrides,
) -> pd.DataFrame:
    defaults = {
        "open": 35000.0, "high": 35100.0, "low": 34900.0, "close": 35000.0,
        "volume": 150.0, "rsi": 50.0, "volume_ma": 100.0,
        "bb_upper": 35500.0, "bb_middle": 35000.0, "bb_lower": 34500.0,
        "atr": 200.0, "adx": 15.0, "di_plus": 20.0, "di_minus": 20.0,
        "ema_slow": 35000.0,
    }
    defaults.update(overrides)
    prev = defaults.copy()
    if rsi_prev is not None:
        prev["rsi"] = rsi_prev
    if di_plus_prev is not None:
        prev["di_plus"] = di_plus_prev
    if di_minus_prev is not None:
        prev["di_minus"] = di_minus_prev
    idx = pd.to_datetime(["2026-01-01 00:00", "2026-01-01 00:05"])
    return pd.DataFrame([prev, defaults], index=idx)
```

- [ ] **Step 2: Aggiorna i test trend che assertiscono LONG/SHORT**

```python
# TestTrendFollowing
def test_long_in_uptrend_with_rsi_pullback(self, strategy):
    """LONG in uptrend: DI+ > DI-, close > ema_slow, RSI 40-55, DI+ in crescita."""
    df = _make_df(
        adx=35.0, di_plus=30.0, di_minus=15.0,
        di_plus_prev=27.0,   # DI+ era 27, ora 30 → sta crescendo
        rsi=48.0, close=35100.0, ema_slow=35000.0,
        volume=150.0, volume_ma=100.0,
    )
    assert strategy.generate_signal(df) == "LONG"

def test_short_in_downtrend_with_rsi_pullback(self, strategy):
    """SHORT in downtrend: DI- > DI+, close < ema_slow, RSI 45-60, DI- in crescita."""
    df = _make_df(
        adx=35.0, di_plus=15.0, di_minus=30.0,
        di_minus_prev=27.0,  # DI- era 27, ora 30 → sta crescendo
        rsi=52.0, close=34900.0, ema_slow=35000.0,
        volume=150.0, volume_ma=100.0,
    )
    assert strategy.generate_signal(df) == "SHORT"
```

- [ ] **Step 3: Aggiungi `TestDITurningConfirmation` in fondo a `tests/test_strategy.py`**

```python
class TestDITurningConfirmation:
    """DI dominante deve essere in crescita per emettere segnale trend."""

    def test_no_long_when_di_plus_not_growing(self, strategy):
        """LONG bloccato se DI+ non sta aumentando (uptrend indebolito)."""
        df = _make_df(
            adx=35.0, di_plus=30.0, di_minus=15.0,
            di_plus_prev=32.0,  # DI+ scende 32→30 = trend indebolisce
            rsi=48.0, close=35100.0, ema_slow=35000.0,
            volume=150.0, volume_ma=100.0,
        )
        assert strategy.generate_signal(df) is None

    def test_no_short_when_di_minus_not_growing(self, strategy):
        """SHORT bloccato se DI- non sta aumentando (downtrend indebolito)."""
        df = _make_df(
            adx=35.0, di_plus=15.0, di_minus=30.0,
            di_minus_prev=32.0,  # DI- scende 32→30 = trend indebolisce
            rsi=52.0, close=34900.0, ema_slow=35000.0,
            volume=150.0, volume_ma=100.0,
        )
        assert strategy.generate_signal(df) is None

    def test_long_when_di_plus_growing(self, strategy):
        """LONG emesso se DI+ cresce (trend in rafforzamento)."""
        df = _make_df(
            adx=35.0, di_plus=30.0, di_minus=15.0,
            di_plus_prev=27.0,  # DI+ sale 27→30
            rsi=48.0, close=35100.0, ema_slow=35000.0,
            volume=150.0, volume_ma=100.0,
        )
        assert strategy.generate_signal(df) == "LONG"

    def test_short_when_di_minus_growing(self, strategy):
        """SHORT emesso se DI- cresce (downtrend in rafforzamento)."""
        df = _make_df(
            adx=35.0, di_plus=15.0, di_minus=30.0,
            di_minus_prev=27.0,  # DI- sale 27→30
            rsi=52.0, close=34900.0, ema_slow=35000.0,
            volume=150.0, volume_ma=100.0,
        )
        assert strategy.generate_signal(df) == "SHORT"
```

- [ ] **Step 4: Verifica che i test falliscano**

```bash
pytest tests/test_strategy.py::TestDITurningConfirmation tests/test_strategy.py::TestTrendFollowing -v
```

Expected: FAIL su `test_long_in_uptrend_with_rsi_pullback`, `test_short_in_downtrend_with_rsi_pullback`, e i test "no signal when DI not growing".

- [ ] **Step 5: Implementa il turning check in `_trend_following_signal`**

In `src/strategies/combined.py`, sostituisci `_trend_following_signal`:

```python
def _trend_following_signal(self, df: pd.DataFrame) -> str | None:
    """Genera segnale trend following (ADX > threshold).

    LONG: DI+ > DI- AND close > ema_slow AND RSI in [bull_min, bull_max]
          AND close > bb_middle AND DI+ in crescita vs candela precedente.
    SHORT: DI- > DI+ AND close < ema_slow AND RSI in [bear_min, bear_max]
           AND close < bb_middle AND DI- in crescita vs candela precedente.

    len(df) < 2 → None.
    """
    if len(df) < 2:
        return None

    row = df.iloc[-1]
    prev_row = df.iloc[-2]

    rsi = row["rsi"]
    close = row["close"]
    adx = row["adx"]
    di_plus = row.get("di_plus")
    di_minus = row.get("di_minus")
    ema_slow = row.get("ema_slow")
    bb_middle = row.get("bb_middle")
    prev_di_plus = prev_row.get("di_plus")
    prev_di_minus = prev_row.get("di_minus")

    if any(pd.isna(v) for v in [di_plus, di_minus, ema_slow, bb_middle, prev_di_plus, prev_di_minus]):
        logger.debug("Nessun segnale trend: colonne NaN")
        return None

    di_plus_growing = di_plus > prev_di_plus    # trend rialzista si rafforza
    di_minus_growing = di_minus > prev_di_minus  # trend ribassista si rafforza

    uptrend = di_plus > di_minus and close > ema_slow
    if (uptrend and di_plus_growing
            and self.trend_rsi_bull_min <= rsi <= self.trend_rsi_bull_max
            and close > bb_middle):
        logger.info(
            "Segnale LONG (trend): ADX=%.1f, DI+=%.1f (prev=%.1f), DI-=%.1f, RSI=%.1f",
            adx, di_plus, prev_di_plus, di_minus, rsi,
        )
        return "LONG"

    downtrend = di_minus > di_plus and close < ema_slow
    if (downtrend and di_minus_growing
            and self.trend_rsi_bear_min <= rsi <= self.trend_rsi_bear_max
            and close < bb_middle):
        logger.info(
            "Segnale SHORT (trend): ADX=%.1f, DI-=%.1f (prev=%.1f), DI+=%.1f, RSI=%.1f",
            adx, di_minus, prev_di_minus, di_plus, rsi,
        )
        return "SHORT"

    logger.debug(
        "No signal (trend): ADX=%.1f, DI+=%.1f, DI-=%.1f, RSI=%.1f",
        adx, di_plus, di_minus, rsi,
    )
    return None
```

- [ ] **Step 6: Aggiorna la chiamata in `generate_signal`**

```python
# Prima:
signal = self._trend_following_signal(row)

# Dopo:
signal = self._trend_following_signal(df)
```

- [ ] **Step 7: Verifica tutti i test strategy**

```bash
pytest tests/test_strategy.py -v
```

Expected: tutti PASS

- [ ] **Step 8: Verifica tutti i test del progetto**

```bash
pytest tests/ -v --ignore=tests/test_exchange_integration.py
```

Expected: tutti PASS

- [ ] **Step 9: Commit**

```bash
git add src/strategies/combined.py tests/test_strategy.py
git commit -m "feat: add DI turning confirmation to trend following signals"
```

---

## Task 4: HTF filter nel backtester

**Files:**
- Modify: `src/backtesting/engine.py`

Il backtester deve replicare il comportamento di `main.py`: applicare `HTFFilter.allows_signal()` a ogni segnale prima di impostare `pending_signal`. I dati 1h vengono pre-calcolati all'inizio di `run()` dal resample del 5min (nessuna chiamata a exchange).

- [ ] **Step 1: Aggiungi gli import in `engine.py`**

In `src/backtesting/engine.py`, aggiungi/aggiusta gli import. L'engine già importa `ADX_TREND_THRESHOLD` — aggiungere solo le righe mancanti:

```python
import ta                                          # NUOVO: per calcoli RSI/EMA 1h inline
from src.indicators.htf_filter import HTFFilter    # NUOVO
```

`HTF_RSI_OVERBOUGHT` e `HTF_RSI_OVERSOLD` non servono in engine — li gestisce internamente `HTFFilter`.

- [ ] **Step 2: Implementa la pre-computazione 1h e il filtro in `run()`**

All'inizio di `run()`, dopo `data = data.dropna()` e prima del loop principale, aggiungi:

```python
# --- Pre-calcola dati HTF (1h) per filtro multi-timeframe ---
htf_filter = HTFFilter()
htf_series: dict = {}

try:
    df_1h = (
        data[["open", "high", "low", "close", "volume"]]
        .resample("1h")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna()
    )
    if len(df_1h) >= 25:
        rsi_1h = ta.momentum.rsi(df_1h["close"], window=14)
        ema_fast_1h = ta.trend.ema_indicator(df_1h["close"], window=9)
        ema_slow_1h = ta.trend.ema_indicator(df_1h["close"], window=21)

        for idx_h, ts in enumerate(df_1h.index):
            r = rsi_1h.iloc[idx_h]
            ef = ema_fast_1h.iloc[idx_h]
            es = ema_slow_1h.iloc[idx_h]
            if pd.isna(r) or pd.isna(ef) or pd.isna(es):
                htf_series[ts] = {"rsi_1h": None, "trend_1h": "NEUTRAL"}
            else:
                trend = "UP" if ef > es else ("DOWN" if ef < es else "NEUTRAL")
                htf_series[ts] = {"rsi_1h": float(r), "trend_1h": trend}
except Exception as e:
    logger.warning("HTF precompute fallito: %s — filtro disabilitato", e)
```

- [ ] **Step 3: Applica il filtro HTF nel loop segnali**

Nel loop principale, alla sezione che genera il segnale (alla fine del loop), sostituisci:

```python
# Prima:
signal = self.strategy.generate_signal(window)
if signal in ("LONG", "SHORT"):
    pending_signal = signal

# Dopo:
signal = self.strategy.generate_signal(window)
if signal in ("LONG", "SHORT"):
    # Filtro HTF: usa l'ultima ora COMPLETATA (no look-ahead bias)
    candle_ts = data.index[i]
    last_completed_hour = candle_ts.floor("1h") - pd.Timedelta(hours=1)
    htf_data = htf_series.get(last_completed_hour, {"rsi_1h": None, "trend_1h": "NEUTRAL"})
    adx_now = float(data.iloc[i].get("adx", 0.0))
    strategy_mode = "trend" if adx_now > ADX_TREND_THRESHOLD else "reversion"
    if htf_filter.allows_signal(signal, strategy_mode, htf_data):
        pending_signal = signal
```

- [ ] **Step 4: Verifica che i test del backtester passino**

```bash
pytest tests/test_backtester.py -v
```

Expected: tutti PASS (il filtro HTF è fail-open con `rsi_1h=None`, quindi i test con dati sintetici non sono influenzati)

- [ ] **Step 5: Verifica tutti i test del progetto**

```bash
pytest tests/ -v --ignore=tests/test_exchange_integration.py
```

Expected: tutti PASS

- [ ] **Step 6: Commit**

```bash
git add src/backtesting/engine.py
git commit -m "feat: apply HTF filter in backtester engine (replicates live main.py behavior)"
```

---

## Task 5: Backtest di verifica

- [ ] **Step 1: Esegui il backtest**

```bash
python scripts/run_backtest.py --data "data/ohlcv/BTC_USDT_5m_*.csv" --capital 10000 2>/dev/null
```

- [ ] **Step 2: Confronta con il baseline**

| Metrica | Baseline | Target post-fix |
|---|---|---|
| Trade totali | 1.182 | < 400 (segnali più selettivi) |
| Win rate | 6.8% | > 30% |
| Max drawdown | 45.9% | < 20% |
| Exit via SL | 96.6% | < 70% |
| Durata media | 1.6 candele | > 5 candele |

Se il win rate è ancora < 20%, i parametri RSI da rivedere (da CLAUDE.md):
- Stringere `RSI_ENTRY_OVERSOLD` da 32 → 28
- Alzare `ADX_TREND_THRESHOLD` da 30 → 35

- [ ] **Step 3: Commit finale se i risultati migliorano**

```bash
git add -A
git commit -m "test: first backtest with signal quality improvements — WR: X%"
```
