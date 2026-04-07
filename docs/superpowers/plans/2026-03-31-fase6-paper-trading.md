# Fase 6 — Paper Trading Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the paper trading loop that orchestrates all existing components (exchange, indicators, strategy, sentiment, risk) into a continuous cycle synced to 5-minute candles, with JSON status file for monitoring.

**Architecture:** `TradingLoop` class in `src/main.py` runs the main loop. `StatusWriter` in `src/utils/status.py` handles JSON state persistence. `ClaudeSentiment` gets cooldown caching added to its existing `analyze()` method. All components are already implemented — this phase wires them together.

**Tech Stack:** Python 3.10+, pytest, existing project dependencies (ccxt, anthropic, pandas, ta)

---

### File Structure

- **Modify:** `config/settings.py` — add `SENTIMENT_COOLDOWN_MIN`
- **Create:** `src/utils/status.py` — `StatusWriter` class
- **Create:** `tests/test_status.py` — tests for StatusWriter
- **Modify:** `src/sentiment/claude_sentiment.py` — add cooldown cache to `ClaudeSentiment`
- **Modify:** `tests/test_sentiment.py` — add cooldown cache tests
- **Modify:** `src/main.py` — replace stub with `TradingLoop` class
- **Create:** `tests/test_trading_loop.py` — tests for TradingLoop

---

### Task 1: Add SENTIMENT_COOLDOWN_MIN setting

**Files:**
- Modify: `config/settings.py`

- [ ] **Step 1: Add setting**

Add after `SENTIMENT_THRESHOLD` in `config/settings.py`:

```python
SENTIMENT_COOLDOWN_MIN: int = 15  # minuti minimo tra chiamate sentiment
```

- [ ] **Step 2: Verify import**

Run: `python -c "from config.settings import SENTIMENT_COOLDOWN_MIN; print(SENTIMENT_COOLDOWN_MIN)"`
Expected: `15`

- [ ] **Step 3: Commit**

```bash
git add config/settings.py
git commit -m "feat: add SENTIMENT_COOLDOWN_MIN setting"
```

---

### Task 2: Implement StatusWriter

**Files:**
- Create: `src/utils/status.py`
- Create: `tests/test_status.py`

- [ ] **Step 1: Write failing tests**

Write `tests/test_status.py`:

```python
"""Test per StatusWriter."""

import json
import os
import pytest

from src.utils.status import StatusWriter


@pytest.fixture
def tmp_status(tmp_path):
    """StatusWriter con path temporaneo."""
    path = str(tmp_path / "status.json")
    return StatusWriter(output_path=path), path


class TestStatusWriterWrite:
    """Test per StatusWriter.write()."""

    def test_writes_valid_json(self, tmp_status):
        """Deve scrivere un file JSON valido."""
        sw, path = tmp_status
        data = {
            "timestamp": "2026-03-31T14:35:00Z",
            "mode": "paper",
            "position": None,
            "daily": {"trades": 0, "pnl": 0.0, "win_rate": 0.0},
            "last_signal": None,
            "last_sentiment": None,
        }
        sw.write(data)
        with open(path) as f:
            loaded = json.load(f)
        assert loaded["timestamp"] == "2026-03-31T14:35:00Z"
        assert loaded["mode"] == "paper"
        assert loaded["position"] is None

    def test_overwrites_existing(self, tmp_status):
        """Deve sovrascrivere il file ad ogni chiamata."""
        sw, path = tmp_status
        sw.write({"timestamp": "first", "mode": "paper", "position": None,
                   "daily": {}, "last_signal": None, "last_sentiment": None})
        sw.write({"timestamp": "second", "mode": "paper", "position": None,
                   "daily": {}, "last_signal": None, "last_sentiment": None})
        with open(path) as f:
            loaded = json.load(f)
        assert loaded["timestamp"] == "second"

    def test_creates_parent_directory(self, tmp_path):
        """Deve creare la directory se non esiste."""
        path = str(tmp_path / "subdir" / "status.json")
        sw = StatusWriter(output_path=path)
        sw.write({"timestamp": "test", "mode": "paper", "position": None,
                   "daily": {}, "last_signal": None, "last_sentiment": None})
        assert os.path.exists(path)

    def test_writes_position_data(self, tmp_status):
        """Deve scrivere i dati della posizione aperta."""
        sw, path = tmp_status
        data = {
            "timestamp": "2026-03-31T14:35:00Z",
            "mode": "paper",
            "position": {
                "side": "LONG",
                "entry_price": 50000.0,
                "entry_time": "2026-03-31T14:25:00Z",
                "stop_loss": 49850.0,
                "take_profit": 50200.0,
                "trailing_stop": 49950.0,
                "unrealized_pnl_pct": 0.15,
            },
            "daily": {"trades": 3, "pnl": 12.50, "win_rate": 66.7},
            "last_signal": "LONG",
            "last_sentiment": {"score": 0.4, "confidence": 0.7, "recommendation": "BUY"},
        }
        sw.write(data)
        with open(path) as f:
            loaded = json.load(f)
        assert loaded["position"]["side"] == "LONG"
        assert loaded["position"]["entry_price"] == 50000.0


class TestStatusWriterRead:
    """Test per StatusWriter.read()."""

    def test_read_existing_file(self, tmp_status):
        """Deve leggere un file JSON esistente."""
        sw, path = tmp_status
        data = {"timestamp": "test", "mode": "paper", "position": {"side": "LONG"},
                "daily": {}, "last_signal": None, "last_sentiment": None}
        sw.write(data)
        loaded = sw.read()
        assert loaded is not None
        assert loaded["position"]["side"] == "LONG"

    def test_read_missing_file(self, tmp_path):
        """Deve restituire None se il file non esiste."""
        sw = StatusWriter(output_path=str(tmp_path / "nonexistent.json"))
        assert sw.read() is None

    def test_read_corrupted_file(self, tmp_status):
        """Deve restituire None se il file e' corrotto."""
        sw, path = tmp_status
        with open(path, "w") as f:
            f.write("not valid json{{{")
        assert sw.read() is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_status.py -v`
Expected: FAIL (StatusWriter not found)

- [ ] **Step 3: Implement StatusWriter**

Write `src/utils/status.py`:

```python
"""Scrittura e lettura del file di stato del bot.

Responsabilita':
- Scrivere lo stato corrente in formato JSON (atomicamente)
- Leggere lo stato precedente per recovery dopo crash
"""

from __future__ import annotations

import json
import os
import tempfile

from src.utils.logger import setup_logger

logger = setup_logger("status")


class StatusWriter:
    """Gestore del file di stato JSON del bot.

    Scrive lo stato ad ogni tick (overwrite atomico) e lo legge per recovery.

    Args:
        output_path: Path del file di stato JSON.
    """

    def __init__(self, output_path: str = "data/paper_status.json") -> None:
        self._path = output_path

    def write(self, data: dict) -> None:
        """Scrive lo stato corrente su file JSON.

        Usa scrittura atomica: scrive su file temporaneo, poi rinomina.

        Args:
            data: Dizionario con lo stato corrente del bot.
        """
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        dir_name = os.path.dirname(self._path) or "."
        try:
            fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2, default=str)
            os.replace(tmp_path, self._path)
        except Exception:
            logger.exception("Errore scrittura status file")
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def read(self) -> dict | None:
        """Legge lo stato precedente dal file JSON.

        Returns:
            Dict con lo stato, o None se il file non esiste o e' corrotto.
        """
        if not os.path.exists(self._path):
            return None
        try:
            with open(self._path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            logger.warning("Status file corrotto o illeggibile: %s", self._path)
            return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_status.py -v`
Expected: all 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/utils/status.py tests/test_status.py
git commit -m "feat: implement StatusWriter with atomic write and read for recovery"
```

---

### Task 3: Add cooldown cache to ClaudeSentiment

**Files:**
- Modify: `src/sentiment/claude_sentiment.py`
- Modify: `tests/test_sentiment.py`

- [ ] **Step 1: Write failing tests for cooldown**

Add to `tests/test_sentiment.py`:

```python
from unittest.mock import MagicMock, patch


class TestSentimentCooldown:
    """Test per il cooldown cache di ClaudeSentiment."""

    @patch("src.sentiment.claude_sentiment.Anthropic")
    @patch("src.sentiment.claude_sentiment.time")
    def test_cache_hit_within_cooldown(self, mock_time, mock_anthropic_cls):
        """Seconda chiamata entro il cooldown deve restituire il risultato cached."""
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = json.dumps({
            "sentiment_score": 0.6, "confidence": 0.8,
            "top_events": ["Rally"], "recommendation": "BUY",
        })
        mock_message = MagicMock()
        mock_message.content = [mock_text_block]
        mock_client.messages.create.return_value = mock_message

        mock_time.time.side_effect = [1000.0, 1500.0]  # 500s < 900s cooldown

        sentiment = ClaudeSentiment(api_key="test-key", cooldown_minutes=15)
        result1 = sentiment.analyze()
        result2 = sentiment.analyze()

        assert result1.sentiment_score == 0.6
        assert result2.sentiment_score == 0.6
        assert mock_client.messages.create.call_count == 1  # solo 1 chiamata API

    @patch("src.sentiment.claude_sentiment.Anthropic")
    @patch("src.sentiment.claude_sentiment.time")
    def test_cache_miss_after_cooldown(self, mock_time, mock_anthropic_cls):
        """Chiamata dopo il cooldown deve fare una nuova richiesta API."""
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = json.dumps({
            "sentiment_score": 0.6, "confidence": 0.8,
            "top_events": ["Rally"], "recommendation": "BUY",
        })
        mock_message = MagicMock()
        mock_message.content = [mock_text_block]
        mock_client.messages.create.return_value = mock_message

        mock_time.time.side_effect = [1000.0, 2000.0]  # 1000s > 900s cooldown

        sentiment = ClaudeSentiment(api_key="test-key", cooldown_minutes=15)
        sentiment.analyze()
        sentiment.analyze()

        assert mock_client.messages.create.call_count == 2  # 2 chiamate API

    @patch("src.sentiment.claude_sentiment.Anthropic")
    def test_first_call_always_hits_api(self, mock_anthropic_cls):
        """Prima chiamata deve sempre fare la richiesta API."""
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = json.dumps({
            "sentiment_score": 0.0, "confidence": 0.5,
            "top_events": [], "recommendation": "HOLD",
        })
        mock_message = MagicMock()
        mock_message.content = [mock_text_block]
        mock_client.messages.create.return_value = mock_message

        sentiment = ClaudeSentiment(api_key="test-key")
        sentiment.analyze()

        assert mock_client.messages.create.call_count == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_sentiment.py::TestSentimentCooldown -v`
Expected: FAIL (cooldown_minutes param not accepted)

- [ ] **Step 3: Implement cooldown cache**

Modify `src/sentiment/claude_sentiment.py`:

1. Add `import time` at the top (after existing imports, before the logger).

2. Add `SENTIMENT_COOLDOWN_MIN` to the settings import:

```python
from config.settings import ANTHROPIC_API_KEY, SENTIMENT_COOLDOWN_MIN, SENTIMENT_MODEL
```

3. Modify `ClaudeSentiment.__init__` to accept cooldown:

```python
    def __init__(
        self,
        api_key: str = ANTHROPIC_API_KEY,
        model: str = SENTIMENT_MODEL,
        cooldown_minutes: int = SENTIMENT_COOLDOWN_MIN,
    ) -> None:
        self._client = Anthropic(api_key=api_key)
        self._model = model
        self._cooldown_seconds = cooldown_minutes * 60
        self._last_result: SentimentResult | None = None
        self._last_call_time: float = 0.0
```

4. Add cooldown check at the beginning of `analyze()`, before the try block:

```python
    def analyze(self, symbol: str = "BTC") -> SentimentResult:
        """Esegue l'analisi sentiment tramite Claude API.

        Usa un cooldown cache: se l'ultima chiamata e' avvenuta meno di
        cooldown_seconds fa, restituisce il risultato cached.

        Args:
            symbol: Simbolo crypto da analizzare.

        Returns:
            SentimentResult con score, confidence, eventi e raccomandazione.
        """
        now = time.time()
        if self._last_result is not None and (now - self._last_call_time) < self._cooldown_seconds:
            remaining = self._cooldown_seconds - (now - self._last_call_time)
            logger.info("Sentiment cache hit (%.0fs remaining)", remaining)
            return self._last_result

        try:
            message = self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                tools=[{
                    "type": "web_search_20250305",
                    "name": "web_search",
                }],
                messages=[{
                    "role": "user",
                    "content": _SENTIMENT_PROMPT.replace("Bitcoin", symbol),
                }],
            )

            # Estrai il testo dalla risposta (ignora blocchi web search)
            text = ""
            for block in message.content:
                if block.type == "text":
                    text += block.text

            data = self._extract_json(text)
            result = SentimentResult.from_dict(data)
            logger.info(
                "Sentiment %s: score=%.2f confidence=%.2f rec=%s",
                symbol, result.sentiment_score, result.confidence, result.recommendation,
            )
            self._last_result = result
            self._last_call_time = now
            return result

        except Exception as e:
            logger.error("Errore analisi sentiment: %s", e)
            return SentimentResult.neutral()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_sentiment.py -v`
Expected: all tests PASS (existing + 3 new)

- [ ] **Step 5: Commit**

```bash
git add src/sentiment/claude_sentiment.py tests/test_sentiment.py
git commit -m "feat: add cooldown cache to ClaudeSentiment (15min default)"
```

---

### Task 4: Implement TradingLoop position management

**Files:**
- Modify: `src/main.py`
- Create: `tests/test_trading_loop.py`

This task implements the core position management methods (`_check_open_position`, `_open_position`, `_close_position`, `_recover_position`, `_check_daily_reset`) without the full loop — those are testable in isolation.

- [ ] **Step 1: Write failing tests**

Write `tests/test_trading_loop.py`:

```python
"""Test per il TradingLoop (position management)."""

import json
import os
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from src.main import TradingLoop


@pytest.fixture
def loop(tmp_path):
    """TradingLoop con componenti mockati."""
    status_path = str(tmp_path / "status.json")
    with patch("src.main.BinanceExchange"):
        with patch("src.main.ClaudeSentiment"):
            tl = TradingLoop(mode="paper", status_path=status_path)
    return tl


class TestCheckOpenPosition:
    """Test per _check_open_position."""

    def test_long_sl_hit(self, loop):
        """LONG: low <= stop_loss -> chiudi con stop_loss."""
        loop._position = {
            "side": "LONG", "entry_price": 50000.0, "entry_time": "t",
            "stop_loss": 49850.0, "take_profit": 50200.0,
            "trailing_stop": 49900.0, "size_usdt": 100.0,
        }
        row = MagicMock()
        row.__getitem__ = lambda s, k: {"high": 50100.0, "low": 49800.0, "close": 49900.0}[k]

        loop._check_open_position(row)
        assert loop._position is None  # posizione chiusa

    def test_long_tp_hit(self, loop):
        """LONG: high >= take_profit -> chiudi con take_profit."""
        loop._position = {
            "side": "LONG", "entry_price": 50000.0, "entry_time": "t",
            "stop_loss": 49850.0, "take_profit": 50200.0,
            "trailing_stop": 49900.0, "size_usdt": 100.0,
        }
        row = MagicMock()
        row.__getitem__ = lambda s, k: {"high": 50250.0, "low": 49900.0, "close": 50200.0}[k]

        loop._check_open_position(row)
        assert loop._position is None

    def test_long_sl_priority_over_tp(self, loop):
        """Candela che tocca sia SL che TP: SL ha priorita' (conservativo)."""
        loop._position = {
            "side": "LONG", "entry_price": 50000.0, "entry_time": "t",
            "stop_loss": 49850.0, "take_profit": 50200.0,
            "trailing_stop": 49900.0, "size_usdt": 100.0,
        }
        row = MagicMock()
        # Candela con range enorme: tocca sia SL (low=49800) che TP (high=50300)
        row.__getitem__ = lambda s, k: {"high": 50300.0, "low": 49800.0, "close": 50000.0}[k]

        loop._close_position = MagicMock()
        loop._check_open_position(row)
        # Deve chiamare _close_position con reason="stop_loss" (non take_profit)
        loop._close_position.assert_called_once()
        call_args = loop._close_position.call_args
        assert call_args[1]["reason"] == "stop_loss" or call_args[0][1] == "stop_loss"

    def test_short_sl_hit(self, loop):
        """SHORT: high >= stop_loss -> chiudi con stop_loss."""
        loop._position = {
            "side": "SHORT", "entry_price": 50000.0, "entry_time": "t",
            "stop_loss": 50150.0, "take_profit": 49800.0,
            "trailing_stop": 50100.0, "size_usdt": 100.0,
        }
        row = MagicMock()
        row.__getitem__ = lambda s, k: {"high": 50200.0, "low": 49900.0, "close": 50100.0}[k]

        loop._check_open_position(row)
        assert loop._position is None

    def test_no_exit_when_within_range(self, loop):
        """Nessuna uscita se il prezzo e' dentro SL-TP."""
        loop._position = {
            "side": "LONG", "entry_price": 50000.0, "entry_time": "t",
            "stop_loss": 49850.0, "take_profit": 50200.0,
            "trailing_stop": 49900.0, "size_usdt": 100.0,
        }
        row = MagicMock()
        row.__getitem__ = lambda s, k: {"high": 50100.0, "low": 49900.0, "close": 50050.0}[k]

        loop._check_open_position(row)
        assert loop._position is not None  # posizione ancora aperta

    def test_trailing_stop_updates(self, loop):
        """Trailing stop deve aggiornarsi quando il prezzo sale (LONG)."""
        loop._position = {
            "side": "LONG", "entry_price": 50000.0, "entry_time": "t",
            "stop_loss": 49850.0, "take_profit": 50200.0,
            "trailing_stop": 49900.0, "size_usdt": 100.0,
        }
        row = MagicMock()
        # Prezzo sale a 50150, trailing dovrebbe salire
        row.__getitem__ = lambda s, k: {"high": 50150.0, "low": 50050.0, "close": 50100.0}[k]

        loop._check_open_position(row)
        assert loop._position is not None
        # Trailing dovrebbe essere salito (esatto valore dipende da ATR, ma > 49900)
        assert loop._position["trailing_stop"] >= 49900.0


class TestOpenClosePosition:
    """Test per _open_position e _close_position."""

    def test_open_position_sets_state(self, loop):
        """_open_position deve settare _position con tutti i campi."""
        from src.sentiment.claude_sentiment import SentimentResult
        sentiment = SentimentResult(sentiment_score=0.5, confidence=0.8,
                                     top_events=[], recommendation="BUY")
        row = MagicMock()
        row.__getitem__ = lambda s, k: {"close": 50000.0}[k]
        row.name = "2026-03-31T14:25:00"

        loop._open_position("LONG", row, sentiment, atr=100.0)

        assert loop._position is not None
        assert loop._position["side"] == "LONG"
        assert loop._position["entry_price"] == 50000.0
        assert "stop_loss" in loop._position
        assert "take_profit" in loop._position
        assert "trailing_stop" in loop._position
        assert "size_usdt" in loop._position

    def test_close_position_clears_state(self, loop):
        """_close_position deve azzerare _position e registrare il trade."""
        loop._position = {
            "side": "LONG", "entry_price": 50000.0, "entry_time": "t",
            "stop_loss": 49850.0, "take_profit": 50200.0,
            "trailing_stop": 49900.0, "size_usdt": 100.0,
        }
        row = MagicMock()
        row.__getitem__ = lambda s, k: {"close": 50100.0}[k]
        row.name = "2026-03-31T14:30:00"

        loop._close_position(row, "take_profit")

        assert loop._position is None
        assert loop._daily_trades > 0


class TestRecoverPosition:
    """Test per _recover_position."""

    def test_recover_from_valid_file(self, tmp_path):
        """Deve ripristinare la posizione da un file valido."""
        status_path = str(tmp_path / "status.json")
        data = {
            "position": {
                "side": "LONG", "entry_price": 50000.0, "entry_time": "t",
                "stop_loss": 49850.0, "take_profit": 50200.0,
                "trailing_stop": 49900.0, "size_usdt": 100.0,
            }
        }
        with open(status_path, "w") as f:
            json.dump(data, f)

        with patch("src.main.BinanceExchange"):
            with patch("src.main.ClaudeSentiment"):
                tl = TradingLoop(mode="paper", status_path=status_path)

        assert tl._position is not None
        assert tl._position["side"] == "LONG"

    def test_recover_no_file(self, tmp_path):
        """Nessun file -> nessuna posizione, nessun errore."""
        status_path = str(tmp_path / "nonexistent.json")
        with patch("src.main.BinanceExchange"):
            with patch("src.main.ClaudeSentiment"):
                tl = TradingLoop(mode="paper", status_path=status_path)
        assert tl._position is None

    def test_recover_null_position(self, tmp_path):
        """File con position=null -> nessuna posizione."""
        status_path = str(tmp_path / "status.json")
        with open(status_path, "w") as f:
            json.dump({"position": None}, f)

        with patch("src.main.BinanceExchange"):
            with patch("src.main.ClaudeSentiment"):
                tl = TradingLoop(mode="paper", status_path=status_path)
        assert tl._position is None


class TestCheckDailyReset:
    """Test per _check_daily_reset."""

    def test_resets_on_new_day(self, loop):
        """Cambio data deve resettare i contatori."""
        loop._daily_trades = 5
        loop._daily_wins = 3
        loop._daily_pnl = 25.0
        loop._last_date = date(2026, 3, 30)

        with patch("src.main.date") as mock_date:
            mock_date.today.return_value = date(2026, 3, 31)
            mock_date.side_effect = lambda *args, **kw: date(*args, **kw)
            loop._check_daily_reset()

        assert loop._daily_trades == 0
        assert loop._daily_wins == 0
        assert loop._daily_pnl == 0.0

    def test_no_reset_same_day(self, loop):
        """Stessa data non deve resettare."""
        loop._daily_trades = 5
        loop._last_date = date.today()

        loop._check_daily_reset()

        assert loop._daily_trades == 5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_trading_loop.py -v`
Expected: FAIL (TradingLoop not yet implemented)

- [ ] **Step 3: Implement TradingLoop**

Replace `src/main.py` with:

```python
"""Entry point del bot di scalping.

Avvia il loop principale del bot in modalita' paper o live.
Gestisce il ciclo: fetch dati -> calcolo indicatori -> segnale -> sentiment -> esecuzione.
"""

from __future__ import annotations

import argparse
import signal
import time
from datetime import date, datetime, timezone

from config.settings import (
    BINANCE_API_KEY,
    BINANCE_API_SECRET,
    LOG_LEVEL,
    SYMBOL,
    TIMEFRAME,
    TRADE_AMOUNT_USDT,
)
from src.exchange import BinanceExchange
from src.indicators.technical import add_indicators, add_prev_indicators
from src.risk.manager import RiskManager
from src.sentiment.claude_sentiment import ClaudeSentiment, SentimentResult
from src.strategies.combined import CombinedStrategy
from src.utils.logger import setup_logger
from src.utils.status import StatusWriter

logger = setup_logger("bot", level=LOG_LEVEL)


class TradingLoop:
    """Loop principale del bot di scalping.

    Orchestrare tutti i componenti in un ciclo continuo sincronizzato
    alle candele 5min. Supporta paper trading (nessun ordine reale)
    e live trading.

    Args:
        mode: "paper" o "live".
        status_path: Path del file di stato JSON.
    """

    def __init__(self, mode: str = "paper", status_path: str = "data/paper_status.json") -> None:
        self.mode = mode
        self._running = False

        # Componenti
        self._exchange = BinanceExchange(
            api_key=BINANCE_API_KEY, api_secret=BINANCE_API_SECRET,
            sandbox=(mode == "paper"),
        )
        self._strategy = CombinedStrategy()
        self._sentiment = ClaudeSentiment()
        self._risk = RiskManager()
        self._status = StatusWriter(output_path=status_path)

        # Stato posizione
        self._position: dict | None = None
        self._last_signal: str | None = None
        self._last_sentiment: SentimentResult | None = None

        # Contatori giornalieri (paralleli a RiskManager per status file)
        self._daily_trades: int = 0
        self._daily_wins: int = 0
        self._daily_pnl: float = 0.0
        self._last_date: date = date.today()

        # Recovery
        self._recover_position()

    def run(self) -> None:
        """Esegue il loop principale con graceful shutdown."""
        self._running = True
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

        logger.info("Bot avviato in modalita': %s", self.mode)

        while self._running:
            try:
                self._wait_for_candle()
                if not self._running:
                    break
                self._tick()
            except Exception:
                logger.exception("Errore nel tick, riprovo al prossimo ciclo")

        logger.info("Bot fermato.")

    def _handle_shutdown(self, signum: int, frame) -> None:
        """Handler per SIGINT/SIGTERM."""
        logger.info("Shutdown richiesto (signal=%d)", signum)
        self._running = False

    def _wait_for_candle(self) -> None:
        """Attende la chiusura della prossima candela 5min."""
        now = time.time()
        interval = 300  # 5 minuti
        seconds_to_next = interval - (now % interval) + 5  # 5s buffer
        logger.debug("Attesa prossima candela: %.0f secondi", seconds_to_next)
        # Sleep in blocchi da 1s per controllare _running
        end_time = now + seconds_to_next
        while time.time() < end_time and self._running:
            time.sleep(1)

    def _tick(self) -> None:
        """Esegue un singolo ciclo del bot."""
        self._check_daily_reset()

        # Fetch dati
        try:
            df = self._exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, limit=100)
        except Exception:
            logger.exception("Errore fetch OHLCV, skip tick")
            return

        # Indicatori
        df = add_indicators(df)
        df = add_prev_indicators(df)
        df = df.dropna()
        if len(df) < 2:
            logger.warning("Dati insufficienti dopo dropna")
            return

        row = df.iloc[-1]

        # ATR semplificato: high - low dell'ultima candela
        atr = row["high"] - row["low"]

        # Check posizione aperta
        if self._position is not None:
            self._position["trailing_stop"] = self._risk.update_trailing_stop(
                side=self._position["side"],
                current_price=row["close"],
                current_trailing=self._position["trailing_stop"],
                atr=atr,
            )
            self._check_open_position(row)
        else:
            # Genera segnale
            signal_raw = self._strategy.generate_signal(df)
            self._last_signal = signal_raw

            if signal_raw is not None:
                # Sentiment con cooldown
                sentiment = self._sentiment.analyze()
                self._last_sentiment = sentiment

                # Rigenera con filtro sentiment
                signal_filtered = self._strategy.generate_signal(df, sentiment=sentiment)

                if signal_filtered is not None and self._risk.can_trade(
                    capital=TRADE_AMOUNT_USDT * 100,  # placeholder capital
                ):
                    self._open_position(signal_filtered, row, sentiment, atr)

        # Aggiorna status
        self._write_status(row)

    def _check_open_position(self, row) -> None:
        """Controlla se la posizione aperta ha raggiunto SL/TP/trailing.

        Ordine conservativo: SL -> trailing -> TP.
        Usa high/low della candela per check realistici.

        Args:
            row: Ultima riga del DataFrame con high, low, close.
        """
        pos = self._position
        if pos is None:
            return

        high = row["high"]
        low = row["low"]

        if pos["side"] == "LONG":
            if low <= pos["stop_loss"]:
                self._close_position(row, "stop_loss")
            elif low <= pos["trailing_stop"]:
                self._close_position(row, "trailing_stop")
            elif high >= pos["take_profit"]:
                self._close_position(row, "take_profit")
        else:  # SHORT
            if high >= pos["stop_loss"]:
                self._close_position(row, "stop_loss")
            elif high >= pos["trailing_stop"]:
                self._close_position(row, "trailing_stop")
            elif low <= pos["take_profit"]:
                self._close_position(row, "take_profit")

    def _open_position(self, signal: str, row, sentiment: SentimentResult, atr: float) -> None:
        """Apre una nuova posizione (paper o live).

        Args:
            signal: "LONG" o "SHORT".
            row: Ultima riga del DataFrame.
            sentiment: Risultato sentiment corrente.
            atr: ATR corrente.
        """
        entry_price = row["close"]
        levels = self._risk.calculate_levels(entry_price, signal, atr)
        size = self._risk.calculate_position_size(
            capital=TRADE_AMOUNT_USDT * 100,
            entry_price=entry_price,
            sl_price=levels["stop_loss"],
            sentiment=sentiment,
        )

        if size == 0.0:
            logger.info("Position size troppo piccola, skip trade")
            return

        self._position = {
            "side": signal,
            "entry_price": entry_price,
            "entry_time": str(row.name),
            "stop_loss": levels["stop_loss"],
            "take_profit": levels["take_profit"],
            "trailing_stop": levels["trailing_stop"],
            "size_usdt": size,
        }

        logger.info(
            "APERTA %s @ %.2f | SL=%.2f TP=%.2f Trail=%.2f | Size=%.2f USDT",
            signal, entry_price, levels["stop_loss"], levels["take_profit"],
            levels["trailing_stop"], size,
        )

    def _close_position(self, row, reason: str) -> None:
        """Chiude la posizione aperta.

        Args:
            row: Ultima riga del DataFrame.
            reason: "stop_loss", "take_profit", "trailing_stop".
        """
        pos = self._position
        if pos is None:
            return

        exit_price = row["close"]
        entry_price = pos["entry_price"]

        if pos["side"] == "LONG":
            pnl_pct = ((exit_price - entry_price) / entry_price) * 100.0
        else:
            pnl_pct = ((entry_price - exit_price) / entry_price) * 100.0

        pnl = (pnl_pct / 100.0) * pos["size_usdt"]

        logger.info(
            "CHIUSA %s @ %.2f | Reason=%s | PnL=%.2f%% (%.2f USDT)",
            pos["side"], exit_price, reason, pnl_pct, pnl,
        )

        self._risk.record_trade(pnl)
        self._daily_trades += 1
        self._daily_pnl += pnl
        if pnl > 0:
            self._daily_wins += 1

        self._position = None

    def _recover_position(self) -> None:
        """Ripristina la posizione aperta dal file di stato."""
        data = self._status.read()
        if data is None:
            return

        pos = data.get("position")
        if pos is not None and isinstance(pos, dict) and "side" in pos:
            self._position = pos
            logger.info("Posizione recuperata: %s @ %.2f", pos["side"], pos["entry_price"])

    def _check_daily_reset(self) -> None:
        """Resetta i contatori se la data e' cambiata."""
        today = date.today()
        if today != self._last_date:
            logger.info("Nuovo giorno: reset contatori giornalieri")
            self._risk.reset_daily()
            self._daily_trades = 0
            self._daily_wins = 0
            self._daily_pnl = 0.0
            self._last_date = today

    def _write_status(self, row) -> None:
        """Scrive il file di stato JSON."""
        pos_data = None
        if self._position is not None:
            entry = self._position["entry_price"]
            current = row["close"]
            if self._position["side"] == "LONG":
                unrealized = ((current - entry) / entry) * 100.0
            else:
                unrealized = ((entry - current) / entry) * 100.0

            pos_data = {**self._position, "unrealized_pnl_pct": round(unrealized, 4)}

        win_rate = 0.0
        if self._daily_trades > 0:
            win_rate = round((self._daily_wins / self._daily_trades) * 100.0, 1)

        sentiment_data = None
        if self._last_sentiment is not None:
            sentiment_data = {
                "score": self._last_sentiment.sentiment_score,
                "confidence": self._last_sentiment.confidence,
                "recommendation": self._last_sentiment.recommendation,
            }

        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": self.mode,
            "position": pos_data,
            "daily": {
                "trades": self._daily_trades,
                "pnl": round(self._daily_pnl, 2),
                "win_rate": win_rate,
            },
            "last_signal": self._last_signal,
            "last_sentiment": sentiment_data,
        }

        try:
            self._status.write(data)
        except Exception:
            logger.exception("Errore scrittura status")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parsa gli argomenti della linea di comando.

    Args:
        argv: Lista di argomenti. Se None, usa sys.argv[1:].

    Returns:
        Namespace con gli argomenti parsati.
    """
    parser = argparse.ArgumentParser(description="Scalping Bot - BTC/USDT")
    parser.add_argument(
        "--mode",
        choices=["paper", "live"],
        default="paper",
        help="Modalita' di esecuzione (default: paper)",
    )
    return parser.parse_args(argv)


def main() -> None:
    """Entry point principale del bot."""
    args = parse_args()

    if args.mode == "live":
        logger.warning("MODALITA' LIVE - Ordini reali saranno piazzati!")

    loop = TradingLoop(mode=args.mode)
    loop.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_trading_loop.py -v`
Expected: all tests PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -v`
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/main.py tests/test_trading_loop.py
git commit -m "feat: implement TradingLoop with paper trading, position management, and crash recovery"
```

---

### Task 5: Final verification and integration test

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v`
Expected: all tests PASS

- [ ] **Step 2: Verify bot starts in paper mode**

Run: `python -m src.main --mode paper`
Expected: Bot starts, logs "Bot avviato in modalita': paper", waits for next candle. Kill with Ctrl+C after a few seconds — should log "Shutdown richiesto" and exit cleanly.

- [ ] **Step 3: Verify parse_args still works**

Run: `python -c "from src.main import parse_args; print(parse_args(['--mode', 'paper']).mode)"`
Expected: `paper`

- [ ] **Step 4: Commit any fixes**

Only if there are uncommitted changes from fixes.
