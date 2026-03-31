# Fase 7 — Deploy Live Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable real order execution on Binance spot with Slack notifications, kill switch, and pre-flight safety checks.

**Architecture:** `SlackNotifier` in `src/utils/notifier.py` handles Slack webhooks. `TradingLoop` in `src/main.py` gets modified to place real orders in live mode, check a kill switch file each tick, run pre-flight checks at startup, and send Slack notifications on key events. Three new settings added to `config/settings.py`.

**Tech Stack:** Python 3.10+, pytest, existing project dependencies (ccxt, anthropic, pandas, ta), urllib (stdlib)

---

### File Structure

- **Modify:** `config/settings.py` — add `SLACK_WEBHOOK_URL`, `LIVE_CAPITAL_USDT`, `KILL_SWITCH_PATH`
- **Modify:** `.env.example` — add `SLACK_WEBHOOK_URL`
- **Create:** `src/utils/notifier.py` — `SlackNotifier` class
- **Create:** `tests/test_notifier.py` — tests for SlackNotifier
- **Modify:** `src/main.py` — live execution, kill switch, pre-flight checks, notifier integration
- **Create:** `tests/test_live_execution.py` — tests for live-specific TradingLoop logic

---

### Task 1: Add new settings

**Files:**
- Modify: `config/settings.py`
- Modify: `.env.example`

- [ ] **Step 1: Add settings**

Add after `LOG_LEVEL` in `config/settings.py`:

```python
# --- Notifiche ---
SLACK_WEBHOOK_URL: str = os.getenv("SLACK_WEBHOOK_URL", "")

# --- Live ---
LIVE_CAPITAL_USDT: float = 50.0  # capitale allocato per live trading
KILL_SWITCH_PATH: str = "data/kill.flag"
```

- [ ] **Step 2: Update .env.example**

Add after the `LOG_LEVEL` line in `.env.example`:

```
# Slack (opzionale)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

- [ ] **Step 3: Verify import**

Run: `python -c "from config.settings import SLACK_WEBHOOK_URL, LIVE_CAPITAL_USDT, KILL_SWITCH_PATH; print(LIVE_CAPITAL_USDT, KILL_SWITCH_PATH)"`
Expected: `50.0 data/kill.flag`

- [ ] **Step 4: Commit**

```bash
git add config/settings.py .env.example
git commit -m "feat: add Slack, live capital, and kill switch settings"
```

---

### Task 2: Implement SlackNotifier

**Files:**
- Create: `src/utils/notifier.py`
- Create: `tests/test_notifier.py`

- [ ] **Step 1: Write failing tests**

Write `tests/test_notifier.py`:

```python
"""Test per SlackNotifier."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.utils.notifier import SlackNotifier


class TestSlackNotifierInit:
    """Test per inizializzazione SlackNotifier."""

    def test_enabled_with_url(self):
        """Deve essere abilitato se webhook URL fornito."""
        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/test")
        assert notifier.enabled is True

    def test_disabled_with_empty_url(self):
        """Deve essere disabilitato se webhook URL vuoto."""
        notifier = SlackNotifier(webhook_url="")
        assert notifier.enabled is False

    def test_disabled_with_no_url(self):
        """Deve essere disabilitato se webhook URL non fornito."""
        notifier = SlackNotifier()
        assert notifier.enabled is False


class TestSlackNotifierNotify:
    """Test per SlackNotifier.notify()."""

    @patch("src.utils.notifier.urlopen")
    def test_sends_post_request(self, mock_urlopen):
        """Deve inviare POST con payload JSON corretto."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"ok"
        mock_response.__enter__ = lambda s: mock_response
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/test")
        notifier.notify("Test message")

        mock_urlopen.assert_called_once()
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        assert "Test message" in body["text"]

    @patch("src.utils.notifier.urlopen")
    def test_info_level_no_emoji_prefix(self, mock_urlopen):
        """Livello info: nessun prefisso speciale."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"ok"
        mock_response.__enter__ = lambda s: mock_response
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/test")
        notifier.notify("Trade aperto", level="info")

        request = mock_urlopen.call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        assert body["text"] == "[INFO] Trade aperto"

    @patch("src.utils.notifier.urlopen")
    def test_error_level_prefix(self, mock_urlopen):
        """Livello error: prefisso ERROR."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"ok"
        mock_response.__enter__ = lambda s: mock_response
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/test")
        notifier.notify("Ordine fallito", level="error")

        request = mock_urlopen.call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        assert body["text"] == "[ERROR] Ordine fallito"

    @patch("src.utils.notifier.urlopen")
    def test_warning_level_prefix(self, mock_urlopen):
        """Livello warning: prefisso WARNING."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"ok"
        mock_response.__enter__ = lambda s: mock_response
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/test")
        notifier.notify("Kill switch", level="warning")

        request = mock_urlopen.call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        assert body["text"] == "[WARNING] Kill switch"

    def test_no_call_when_disabled(self):
        """Non deve fare nulla se disabilitato."""
        notifier = SlackNotifier(webhook_url="")
        # Non deve lanciare eccezioni
        notifier.notify("This should be silently ignored")

    @patch("src.utils.notifier.urlopen")
    def test_does_not_raise_on_network_error(self, mock_urlopen):
        """Errore di rete non deve propagarsi."""
        mock_urlopen.side_effect = Exception("Connection refused")

        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/test")
        # Non deve lanciare eccezioni
        notifier.notify("Test message")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_notifier.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement SlackNotifier**

Write `src/utils/notifier.py`:

```python
"""Notifiche Slack via webhook.

Responsabilita':
- Inviare messaggi al canale Slack configurato
- Non bloccare il bot in caso di errori di rete
- Disabilitarsi silenziosamente se il webhook non e' configurato
"""

from __future__ import annotations

import json
from urllib.request import Request, urlopen

from src.utils.logger import setup_logger

logger = setup_logger("notifier")

_LEVEL_PREFIX = {
    "info": "[INFO]",
    "warning": "[WARNING]",
    "error": "[ERROR]",
}


class SlackNotifier:
    """Invia notifiche a Slack via webhook.

    Se il webhook URL e' vuoto, tutte le chiamate sono silenziosamente ignorate.

    Args:
        webhook_url: URL del webhook Slack.
    """

    def __init__(self, webhook_url: str = "") -> None:
        self._url = webhook_url
        self.enabled = bool(webhook_url)

    def notify(self, message: str, level: str = "info") -> None:
        """Invia un messaggio a Slack.

        Non propaga eccezioni: logga l'errore e continua.

        Args:
            message: Testo del messaggio.
            level: Livello del messaggio ("info", "warning", "error").
        """
        if not self.enabled:
            return

        prefix = _LEVEL_PREFIX.get(level, "[INFO]")
        text = f"{prefix} {message}"

        payload = json.dumps({"text": text}).encode("utf-8")
        request = Request(
            self._url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=10) as response:
                response.read()
            logger.debug("Slack notifica inviata: %s", text)
        except Exception:
            logger.warning("Errore invio notifica Slack: %s", text)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_notifier.py -v`
Expected: all 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/utils/notifier.py tests/test_notifier.py
git commit -m "feat: implement SlackNotifier with webhook support"
```

---

### Task 3: Add kill switch and pre-flight checks to TradingLoop

**Files:**
- Modify: `src/main.py`
- Create: `tests/test_live_execution.py`

- [ ] **Step 1: Write failing tests**

Write `tests/test_live_execution.py`:

```python
"""Test per la logica live del TradingLoop."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from src.main import TradingLoop


@pytest.fixture
def live_loop(tmp_path):
    """TradingLoop in mode live con componenti mockati."""
    status_path = str(tmp_path / "status.json")
    kill_path = str(tmp_path / "kill.flag")
    with patch("src.main.BinanceExchange") as mock_ex_cls:
        with patch("src.main.ClaudeSentiment"):
            with patch("src.main.SlackNotifier"):
                tl = TradingLoop(
                    mode="live",
                    status_path=status_path,
                    kill_switch_path=kill_path,
                )
    tl._exchange = mock_ex_cls.return_value
    return tl, tmp_path, kill_path


@pytest.fixture
def paper_loop(tmp_path):
    """TradingLoop in mode paper con componenti mockati."""
    status_path = str(tmp_path / "status.json")
    with patch("src.main.BinanceExchange"):
        with patch("src.main.ClaudeSentiment"):
            with patch("src.main.SlackNotifier"):
                tl = TradingLoop(mode="paper", status_path=status_path)
    return tl


class TestKillSwitch:
    """Test per il kill switch file-based."""

    def test_kill_switch_stops_bot(self, live_loop):
        """Kill switch file presente deve fermare il bot."""
        tl, tmp_path, kill_path = live_loop
        tl._running = True
        # Crea il kill flag
        with open(kill_path, "w") as f:
            f.write("kill")

        result = tl._check_kill_switch()
        assert result is True
        assert tl._running is False

    def test_no_kill_switch_continues(self, live_loop):
        """Nessun kill switch file: il bot continua."""
        tl, tmp_path, kill_path = live_loop
        tl._running = True

        result = tl._check_kill_switch()
        assert result is False
        assert tl._running is True

    def test_kill_switch_notifies_slack(self, live_loop):
        """Kill switch deve inviare notifica Slack."""
        tl, tmp_path, kill_path = live_loop
        tl._running = True
        with open(kill_path, "w") as f:
            f.write("kill")

        tl._check_kill_switch()
        tl._notifier.notify.assert_called()

    def test_kill_switch_warns_open_position(self, live_loop):
        """Kill switch con posizione aperta: log warning."""
        tl, tmp_path, kill_path = live_loop
        tl._running = True
        tl._position = {
            "side": "LONG", "entry_price": 50000.0, "entry_time": "t",
            "stop_loss": 49850.0, "take_profit": 50200.0,
            "trailing_stop": 49900.0, "size_usdt": 100.0,
        }
        with open(kill_path, "w") as f:
            f.write("kill")

        tl._check_kill_switch()
        # Posizione NON deve essere chiusa
        assert tl._position is not None
        assert tl._running is False


class TestPreflightChecks:
    """Test per i pre-flight checks."""

    def test_preflight_fails_empty_api_key(self, tmp_path):
        """Deve fallire se API key vuota."""
        status_path = str(tmp_path / "status.json")
        with patch("src.main.BinanceExchange"):
            with patch("src.main.ClaudeSentiment"):
                with patch("src.main.SlackNotifier"):
                    with patch("src.main.BINANCE_API_KEY", ""):
                        tl = TradingLoop(mode="live", status_path=status_path)
        assert tl._preflight_checks() is False

    def test_preflight_fails_low_balance(self, tmp_path):
        """Deve fallire se balance sotto il minimo."""
        status_path = str(tmp_path / "status.json")
        with patch("src.main.BinanceExchange") as mock_ex_cls:
            with patch("src.main.ClaudeSentiment"):
                with patch("src.main.SlackNotifier"):
                    with patch("src.main.BINANCE_API_KEY", "test-key"):
                        with patch("src.main.BINANCE_API_SECRET", "test-secret"):
                            tl = TradingLoop(mode="live", status_path=status_path)
        tl._exchange.get_balance.return_value = 5.0  # sotto MIN_ORDER_SIZE_USDT (10)
        assert tl._preflight_checks() is False

    def test_preflight_fails_kill_switch_exists(self, tmp_path):
        """Deve fallire se kill switch gia' presente."""
        status_path = str(tmp_path / "status.json")
        kill_path = str(tmp_path / "kill.flag")
        with open(kill_path, "w") as f:
            f.write("kill")
        with patch("src.main.BinanceExchange") as mock_ex_cls:
            with patch("src.main.ClaudeSentiment"):
                with patch("src.main.SlackNotifier"):
                    with patch("src.main.BINANCE_API_KEY", "test-key"):
                        with patch("src.main.BINANCE_API_SECRET", "test-secret"):
                            tl = TradingLoop(
                                mode="live",
                                status_path=status_path,
                                kill_switch_path=kill_path,
                            )
        tl._exchange.get_balance.return_value = 100.0
        assert tl._preflight_checks() is False

    def test_preflight_passes_all_ok(self, tmp_path):
        """Deve passare se tutto OK."""
        status_path = str(tmp_path / "status.json")
        kill_path = str(tmp_path / "kill.flag")
        with patch("src.main.BinanceExchange") as mock_ex_cls:
            with patch("src.main.ClaudeSentiment"):
                with patch("src.main.SlackNotifier"):
                    with patch("src.main.BINANCE_API_KEY", "test-key"):
                        with patch("src.main.BINANCE_API_SECRET", "test-secret"):
                            tl = TradingLoop(
                                mode="live",
                                status_path=status_path,
                                kill_switch_path=kill_path,
                            )
        tl._exchange.get_balance.return_value = 100.0
        assert tl._preflight_checks() is True

    def test_preflight_skipped_in_paper(self, paper_loop):
        """In paper mode pre-flight non viene eseguito (run procede direttamente)."""
        # Paper loop non ha _preflight_checks che blocca
        # Verifichiamo solo che il metodo restituisce True
        assert paper_loop._preflight_checks() is True


class TestLiveExecution:
    """Test per ordini live."""

    def test_open_position_live_calls_create_order(self, live_loop):
        """In live mode, _open_position deve chiamare exchange.create_order."""
        from src.sentiment.claude_sentiment import SentimentResult
        tl, tmp_path, kill_path = live_loop
        tl._exchange.get_balance.return_value = 100.0
        tl._exchange.create_order.return_value = {"id": "123", "status": "filled"}

        sentiment = SentimentResult(
            sentiment_score=0.5, confidence=0.8,
            top_events=[], recommendation="BUY",
        )
        row = MagicMock()
        row.__getitem__ = lambda s, k: {"close": 50000.0}[k]
        row.name = "2026-03-31T14:25:00"

        tl._open_position("LONG", row, sentiment, atr=100.0)

        tl._exchange.create_order.assert_called_once()
        call_kwargs = tl._exchange.create_order.call_args
        assert call_kwargs[1]["side"] == "buy" or call_kwargs[0][1] == "buy"

    def test_open_position_short_skipped_in_live(self, live_loop):
        """In live mode, segnali SHORT devono essere ignorati (spot only)."""
        from src.sentiment.claude_sentiment import SentimentResult
        tl, tmp_path, kill_path = live_loop

        sentiment = SentimentResult(
            sentiment_score=-0.5, confidence=0.8,
            top_events=[], recommendation="SELL",
        )
        row = MagicMock()
        row.__getitem__ = lambda s, k: {"close": 50000.0}[k]
        row.name = "2026-03-31T14:25:00"

        tl._open_position("SHORT", row, sentiment, atr=100.0)

        tl._exchange.create_order.assert_not_called()
        assert tl._position is None

    def test_close_position_live_calls_sell_order(self, live_loop):
        """In live mode, _close_position deve piazzare ordine sell."""
        tl, tmp_path, kill_path = live_loop
        tl._exchange.create_order.return_value = {"id": "456", "status": "filled"}
        tl._position = {
            "side": "LONG", "entry_price": 50000.0, "entry_time": "t",
            "stop_loss": 49850.0, "take_profit": 50200.0,
            "trailing_stop": 49900.0, "size_usdt": 100.0,
        }
        row = MagicMock()
        row.__getitem__ = lambda s, k: {"close": 50100.0}[k]
        row.name = "2026-03-31T14:30:00"

        tl._close_position(row, "take_profit")

        tl._exchange.create_order.assert_called_once()
        assert tl._position is None

    def test_close_position_live_keeps_position_on_order_failure(self, live_loop):
        """Se l'ordine di chiusura fallisce, la posizione resta aperta."""
        tl, tmp_path, kill_path = live_loop
        tl._exchange.create_order.side_effect = Exception("Order failed")
        tl._position = {
            "side": "LONG", "entry_price": 50000.0, "entry_time": "t",
            "stop_loss": 49850.0, "take_profit": 50200.0,
            "trailing_stop": 49900.0, "size_usdt": 100.0,
        }
        row = MagicMock()
        row.__getitem__ = lambda s, k: {"close": 50100.0}[k]
        row.name = "2026-03-31T14:30:00"

        tl._close_position(row, "take_profit")

        # Posizione NON cancellata
        assert tl._position is not None

    def test_open_position_live_no_order_on_failure(self, live_loop):
        """Se l'ordine di apertura fallisce, nessuna posizione salvata."""
        from src.sentiment.claude_sentiment import SentimentResult
        tl, tmp_path, kill_path = live_loop
        tl._exchange.get_balance.return_value = 100.0
        tl._exchange.create_order.side_effect = Exception("Order failed")

        sentiment = SentimentResult(
            sentiment_score=0.5, confidence=0.8,
            top_events=[], recommendation="BUY",
        )
        row = MagicMock()
        row.__getitem__ = lambda s, k: {"close": 50000.0}[k]
        row.name = "2026-03-31T14:25:00"

        tl._open_position("LONG", row, sentiment, atr=100.0)

        assert tl._position is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_live_execution.py -v`
Expected: FAIL (SlackNotifier import missing, _check_kill_switch not found, etc.)

- [ ] **Step 3: Implement kill switch and pre-flight checks**

Modify `src/main.py`. Replace the imports section with:

```python
from __future__ import annotations

import argparse
import os
import signal
import time
from datetime import date, datetime, timezone

from config.settings import (
    BINANCE_API_KEY,
    BINANCE_API_SECRET,
    KILL_SWITCH_PATH,
    LIVE_CAPITAL_USDT,
    LOG_LEVEL,
    MIN_ORDER_SIZE_USDT,
    SLACK_WEBHOOK_URL,
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
from src.utils.notifier import SlackNotifier
from src.utils.status import StatusWriter
```

Modify `TradingLoop.__init__` to accept `kill_switch_path` and create notifier:

```python
    def __init__(
        self,
        mode: str = "paper",
        status_path: str = "data/paper_status.json",
        kill_switch_path: str = KILL_SWITCH_PATH,
    ) -> None:
        self.mode = mode
        self._running = False
        self._kill_switch_path = kill_switch_path

        # Componenti
        self._exchange = BinanceExchange(
            api_key=BINANCE_API_KEY, api_secret=BINANCE_API_SECRET,
            sandbox=(mode == "paper"),
        )
        self._strategy = CombinedStrategy()
        self._sentiment = ClaudeSentiment()
        self._risk = RiskManager()
        self._status = StatusWriter(output_path=status_path)
        self._notifier = SlackNotifier(webhook_url=SLACK_WEBHOOK_URL)

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
```

Add `_check_kill_switch` method after `_handle_shutdown`:

```python
    def _check_kill_switch(self) -> bool:
        """Controlla se il kill switch file e' presente.

        Returns:
            True se il kill switch e' attivo (bot deve fermarsi).
        """
        if not os.path.exists(self._kill_switch_path):
            return False

        logger.warning("KILL SWITCH attivato: %s", self._kill_switch_path)
        self._notifier.notify("KILL SWITCH attivato — bot fermato", level="warning")

        if self._position is not None:
            logger.warning(
                "Posizione aperta rimasta: %s @ %.2f (size=%.2f USDT)",
                self._position["side"],
                self._position["entry_price"],
                self._position["size_usdt"],
            )
            self._notifier.notify(
                "Posizione aperta rimasta: %s @ %.2f" % (
                    self._position["side"], self._position["entry_price"],
                ),
                level="warning",
            )

        self._running = False
        return True
```

Add `_preflight_checks` method after `_check_kill_switch`:

```python
    def _preflight_checks(self) -> bool:
        """Esegue verifiche di sicurezza prima di avviare il loop live.

        Returns:
            True se tutti i check passano.
        """
        if self.mode != "live":
            return True

        # 1. API keys
        if not BINANCE_API_KEY or not BINANCE_API_SECRET:
            logger.error("Pre-flight FAIL: API keys Binance mancanti")
            return False

        # 2. Connessione exchange e balance
        try:
            balance = self._exchange.get_balance("USDT")
        except Exception:
            logger.exception("Pre-flight FAIL: impossibile connettersi a Binance")
            return False

        # 3. Balance minimo
        if balance < MIN_ORDER_SIZE_USDT:
            logger.error(
                "Pre-flight FAIL: balance %.2f USDT < minimo %.2f USDT",
                balance, MIN_ORDER_SIZE_USDT,
            )
            return False

        # 4. Kill switch
        if os.path.exists(self._kill_switch_path):
            logger.error("Pre-flight FAIL: kill switch gia' attivo (%s)", self._kill_switch_path)
            return False

        # 5. Slack (opzionale)
        if self._notifier.enabled:
            self._notifier.notify("Pre-flight OK — bot in avvio")
        else:
            logger.warning("Slack webhook non configurato — notifiche disabilitate")

        logger.info("Pre-flight checks superati (balance=%.2f USDT)", balance)
        return True
```

Modify `run()` to call pre-flight checks and notify:

```python
    def run(self) -> None:
        """Esegue il loop principale con graceful shutdown."""
        self._running = True
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

        if not self._preflight_checks():
            logger.error("Pre-flight checks falliti — bot non avviato")
            self._running = False
            return

        logger.info("Bot avviato in modalita': %s", self.mode)
        self._notifier.notify("Bot avviato in modalita': %s" % self.mode)

        while self._running:
            try:
                self._wait_for_candle()
                if not self._running:
                    break
                self._tick()
            except Exception:
                logger.exception("Errore nel tick, riprovo al prossimo ciclo")

        logger.info("Bot fermato.")
        self._notifier.notify("Bot fermato")
```

Modify `_tick()` to check kill switch as first operation:

```python
    def _tick(self) -> None:
        """Esegue un singolo ciclo del bot."""
        if self._check_kill_switch():
            return

        self._check_daily_reset()
        # ... rest unchanged
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_live_execution.py::TestKillSwitch tests/test_live_execution.py::TestPreflightChecks -v`
Expected: all 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/main.py tests/test_live_execution.py
git commit -m "feat: add kill switch and pre-flight checks to TradingLoop"
```

---

### Task 4: Implement live order execution

**Files:**
- Modify: `src/main.py`

- [ ] **Step 1: Modify _open_position for live mode**

Replace the `_open_position` method in `src/main.py` with:

```python
    def _open_position(self, signal: str, row, sentiment: SentimentResult, atr: float) -> None:
        """Apre una nuova posizione (paper o live).

        Args:
            signal: "LONG" o "SHORT".
            row: Ultima riga del DataFrame.
            sentiment: Risultato sentiment corrente.
            atr: ATR corrente.
        """
        # SHORT ignorato in live (spot only)
        if self.mode == "live" and signal == "SHORT":
            logger.info("SHORT ignorato in live mode (spot only)")
            return

        entry_price = row["close"]

        # Capitale: balance reale in live, simulato in paper
        if self.mode == "live":
            try:
                capital = self._exchange.get_balance("USDT")
            except Exception:
                logger.exception("Errore fetch balance, skip apertura")
                self._notifier.notify("Errore fetch balance — trade non aperto", level="error")
                return
        else:
            capital = LIVE_CAPITAL_USDT

        levels = self._risk.calculate_levels(entry_price, signal, atr)
        size = self._risk.calculate_position_size(
            capital=capital,
            entry_price=entry_price,
            sl_price=levels["stop_loss"],
            sentiment=sentiment,
        )

        if size == 0.0:
            logger.info("Position size troppo piccola, skip trade")
            return

        # Ordine live
        if self.mode == "live":
            amount_btc = size / entry_price
            try:
                order = self._exchange.create_order(
                    symbol=SYMBOL,
                    side="buy",
                    amount=amount_btc,
                )
                logger.info("Ordine live eseguito: %s", order.get("id"))
            except Exception:
                logger.exception("Errore ordine live — posizione non aperta")
                self._notifier.notify(
                    "ERRORE ordine %s @ %.2f — non aperto" % (signal, entry_price),
                    level="error",
                )
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

        msg = "APERTA %s @ %.2f | SL=%.2f TP=%.2f Trail=%.2f | Size=%.2f USDT" % (
            signal, entry_price, levels["stop_loss"], levels["take_profit"],
            levels["trailing_stop"], size,
        )
        logger.info(msg)
        self._notifier.notify(msg)
```

- [ ] **Step 2: Modify _close_position for live mode**

Replace the `_close_position` method in `src/main.py` with:

```python
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

        # Ordine live di chiusura
        if self.mode == "live":
            amount_btc = pos["size_usdt"] / entry_price
            try:
                order = self._exchange.create_order(
                    symbol=SYMBOL,
                    side="sell",
                    amount=amount_btc,
                )
                logger.info("Ordine chiusura live eseguito: %s", order.get("id"))
            except Exception:
                logger.exception("Errore ordine chiusura live — posizione resta aperta")
                self._notifier.notify(
                    "ERRORE chiusura %s @ %.2f — posizione resta aperta" % (
                        pos["side"], exit_price,
                    ),
                    level="error",
                )
                return  # NON cancella la posizione

        if pos["side"] == "LONG":
            pnl_pct = ((exit_price - entry_price) / entry_price) * 100.0
        else:
            pnl_pct = ((entry_price - exit_price) / entry_price) * 100.0

        pnl = (pnl_pct / 100.0) * pos["size_usdt"]

        msg = "CHIUSA %s @ %.2f | Reason=%s | PnL=%.2f%% (%.2f USDT)" % (
            pos["side"], exit_price, reason, pnl_pct, pnl,
        )
        logger.info(msg)
        self._notifier.notify(msg)

        self._risk.record_trade(pnl)
        self._daily_trades += 1
        self._daily_pnl += pnl
        if pnl > 0:
            self._daily_wins += 1

        self._position = None
```

- [ ] **Step 3: Update _tick capital placeholder**

In `_tick()`, replace the `can_trade` call to use `LIVE_CAPITAL_USDT` instead of the old placeholder:

```python
                if signal_filtered is not None and self._risk.can_trade(
                    capital=LIVE_CAPITAL_USDT,
                ):
```

- [ ] **Step 4: Run all live execution tests**

Run: `pytest tests/test_live_execution.py -v`
Expected: all 14 tests PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -v`
Expected: all tests PASS (existing + new)

- [ ] **Step 6: Commit**

```bash
git add src/main.py
git commit -m "feat: implement live order execution with Slack notifications"
```

---

### Task 5: Final verification

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v`
Expected: all tests PASS

- [ ] **Step 2: Verify bot starts in paper mode**

Run: `timeout 5 python -m src.main --mode paper 2>&1 || true`
Expected: Bot starts, logs "Bot avviato in modalita': paper", exits cleanly after timeout.

- [ ] **Step 3: Verify parse_args**

Run: `python -c "from src.main import parse_args; print(parse_args(['--mode', 'live']).mode)"`
Expected: `live`

- [ ] **Step 4: Verify live mode fails without keys**

Run: `python -c "from src.main import TradingLoop; t = TradingLoop(mode='live'); print(t._preflight_checks())"`
Expected: `False` (API keys vuote)

- [ ] **Step 5: Commit any fixes**

Only if there are uncommitted changes from fixes.
