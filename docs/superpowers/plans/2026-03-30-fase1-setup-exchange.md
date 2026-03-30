# Fase 1 — Setup Ambiente & Connessione Exchange

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Configurare l'ambiente di sviluppo, inizializzare git, implementare il modulo exchange per connettersi a Binance e fare fetch di dati OHLCV, il logger strutturato, e l'entry point del bot con argument parser.

**Architecture:** Il modulo `exchange.py` espone una classe `BinanceExchange` che wrappa ccxt per connettersi a Binance. Il `logger.py` configura logging su file e console. Il `main.py` parsa argomenti CLI e avvia il bot. Tutto è configurato centralmente via `config/settings.py` (già esistente).

**Tech Stack:** Python 3.10+, ccxt, pandas, python-dotenv, pytest

---

### Task 1: Inizializzare Git Repository

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Inizializzare il repository git**

```bash
cd /c/Users/matti/OneDrive/Desktop/scalping-bot
git init
```

- [ ] **Step 2: Verificare .gitignore è adeguato**

Leggere `.gitignore` e assicurarsi che contenga: `venv/`, `.env`, `__pycache__/`, `*.pyc`, `logs/`, `data/`.

- [ ] **Step 3: Primo commit**

```bash
git add -A
git commit -m "chore: initial project structure"
```

---

### Task 2: Implementare Logger (`src/utils/logger.py`)

**Files:**
- Modify: `src/utils/logger.py`
- Create: `tests/test_logger.py`

- [ ] **Step 1: Scrivere il test per setup_logger**

```python
# tests/test_logger.py
"""Test per il modulo logger."""

import logging
import os
from src.utils.logger import setup_logger


def test_setup_logger_returns_logger():
    """setup_logger deve restituire un'istanza di logging.Logger."""
    logger = setup_logger("test_bot")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test_bot"


def test_setup_logger_has_console_handler():
    """Il logger deve avere almeno un handler per la console."""
    logger = setup_logger("test_console")
    handler_types = [type(h).__name__ for h in logger.handlers]
    assert "StreamHandler" in handler_types or "RichHandler" in handler_types


def test_setup_logger_has_file_handler(tmp_path):
    """Il logger deve creare un file handler nella directory logs."""
    logger = setup_logger("test_file", log_dir=str(tmp_path))
    handler_types = [type(h).__name__ for h in logger.handlers]
    assert "FileHandler" in handler_types or "RotatingFileHandler" in handler_types


def test_setup_logger_respects_level():
    """Il logger deve rispettare il livello configurato."""
    logger = setup_logger("test_level", level="DEBUG")
    assert logger.level == logging.DEBUG
```

- [ ] **Step 2: Eseguire i test per verificare che falliscano**

```bash
pytest tests/test_logger.py -v
```

Expected: FAIL — `setup_logger` non è implementata.

- [ ] **Step 3: Implementare setup_logger**

```python
# src/utils/logger.py
"""Logging strutturato per il bot.

Configura logging con output su file (logs/) e console.
Formato: timestamp | livello | modulo | messaggio.
"""

import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logger(
    name: str,
    level: str = "INFO",
    log_dir: str = "logs",
) -> logging.Logger:
    """Crea e configura un logger con output su console e file.

    Args:
        name: Nome del logger.
        level: Livello di logging (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_dir: Directory per i file di log.

    Returns:
        Logger configurato.
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Evita duplicazione handler se chiamato più volte
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler
    os.makedirs(log_dir, exist_ok=True)
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, f"{name}.log"),
        maxBytes=5_000_000,  # 5 MB
        backupCount=3,
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
```

- [ ] **Step 4: Eseguire i test e verificare che passino**

```bash
pytest tests/test_logger.py -v
```

Expected: 4 PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/utils/logger.py tests/test_logger.py
git commit -m "feat: implement structured logger with console and file output"
```

---

### Task 3: Implementare BinanceExchange (`src/exchange.py`)

**Files:**
- Modify: `src/exchange.py`
- Create: `tests/test_exchange.py`

- [ ] **Step 1: Scrivere i test per BinanceExchange**

```python
# tests/test_exchange.py
"""Test per il modulo exchange.

Usa ccxt in sandbox mode o mock per evitare chiamate API reali.
"""

import pandas as pd
import pytest
from unittest.mock import MagicMock, patch

from src.exchange import BinanceExchange


class TestBinanceExchangeInit:
    """Test per l'inizializzazione dell'exchange."""

    @patch("src.exchange.ccxt.binance")
    def test_creates_ccxt_instance(self, mock_binance_cls):
        """BinanceExchange deve creare un'istanza ccxt.binance."""
        exchange = BinanceExchange(api_key="test", api_secret="secret")
        mock_binance_cls.assert_called_once()

    @patch("src.exchange.ccxt.binance")
    def test_sandbox_mode_sets_urls(self, mock_binance_cls):
        """In sandbox mode, deve attivare il sandbox di ccxt."""
        mock_instance = MagicMock()
        mock_binance_cls.return_value = mock_instance
        exchange = BinanceExchange(api_key="test", api_secret="secret", sandbox=True)
        mock_instance.set_sandbox_mode.assert_called_once_with(True)


class TestFetchOHLCV:
    """Test per il fetch dei dati OHLCV."""

    @patch("src.exchange.ccxt.binance")
    def test_fetch_ohlcv_returns_dataframe(self, mock_binance_cls):
        """fetch_ohlcv deve restituire un DataFrame con colonne OHLCV."""
        mock_instance = MagicMock()
        mock_binance_cls.return_value = mock_instance
        # ccxt restituisce lista di liste: [timestamp, open, high, low, close, volume]
        mock_instance.fetch_ohlcv.return_value = [
            [1700000000000, 35000.0, 35100.0, 34900.0, 35050.0, 100.5],
            [1700000300000, 35050.0, 35200.0, 35000.0, 35150.0, 120.3],
            [1700000600000, 35150.0, 35300.0, 35100.0, 35250.0, 90.1],
        ]

        exchange = BinanceExchange(api_key="test", api_secret="secret")
        df = exchange.fetch_ohlcv(symbol="BTC/USDT", timeframe="5m", limit=3)

        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
        assert len(df) == 3
        assert df["close"].iloc[-1] == 35250.0

    @patch("src.exchange.ccxt.binance")
    def test_fetch_ohlcv_sets_datetime_index(self, mock_binance_cls):
        """Il DataFrame deve avere un indice datetime."""
        mock_instance = MagicMock()
        mock_binance_cls.return_value = mock_instance
        mock_instance.fetch_ohlcv.return_value = [
            [1700000000000, 35000.0, 35100.0, 34900.0, 35050.0, 100.5],
        ]

        exchange = BinanceExchange(api_key="test", api_secret="secret")
        df = exchange.fetch_ohlcv(symbol="BTC/USDT", timeframe="5m", limit=1)

        assert isinstance(df.index, pd.DatetimeIndex)


class TestGetBalance:
    """Test per il recupero del balance."""

    @patch("src.exchange.ccxt.binance")
    def test_get_balance_returns_usdt(self, mock_binance_cls):
        """get_balance deve restituire il saldo USDT disponibile."""
        mock_instance = MagicMock()
        mock_binance_cls.return_value = mock_instance
        mock_instance.fetch_balance.return_value = {
            "free": {"USDT": 1000.0, "BTC": 0.01},
            "total": {"USDT": 1500.0, "BTC": 0.02},
        }

        exchange = BinanceExchange(api_key="test", api_secret="secret")
        balance = exchange.get_balance(currency="USDT")

        assert balance == 1000.0


class TestCreateOrder:
    """Test per la creazione di ordini."""

    @patch("src.exchange.ccxt.binance")
    def test_create_market_buy_order(self, mock_binance_cls):
        """create_order deve chiamare ccxt create_order con i parametri corretti."""
        mock_instance = MagicMock()
        mock_binance_cls.return_value = mock_instance
        mock_instance.create_order.return_value = {
            "id": "12345",
            "status": "closed",
            "filled": 0.001,
            "price": 35000.0,
        }

        exchange = BinanceExchange(api_key="test", api_secret="secret")
        order = exchange.create_order(
            symbol="BTC/USDT", side="buy", amount=0.001
        )

        mock_instance.create_order.assert_called_once_with(
            symbol="BTC/USDT",
            type="market",
            side="buy",
            amount=0.001,
        )
        assert order["id"] == "12345"
```

- [ ] **Step 2: Eseguire i test per verificare che falliscano**

```bash
pytest tests/test_exchange.py -v
```

Expected: FAIL — `BinanceExchange` non è implementata.

- [ ] **Step 3: Implementare BinanceExchange**

```python
# src/exchange.py
"""Connessione e interazione con Binance via ccxt.

Responsabilità:
- Inizializzare la connessione a Binance (API key da .env)
- Fetch candele OHLCV (BTC/USDT, 5min)
- Piazzare ordini (market buy/sell)
- Ottenere balance e posizioni aperte
- Gestire rate limits e retry
"""

import ccxt
import pandas as pd

from src.utils.logger import setup_logger

logger = setup_logger("exchange")


class BinanceExchange:
    """Wrapper attorno a ccxt.binance per operazioni di trading.

    Args:
        api_key: Binance API key.
        api_secret: Binance API secret.
        sandbox: Se True, usa il testnet di Binance.
    """

    def __init__(self, api_key: str, api_secret: str, sandbox: bool = False) -> None:
        self._exchange = ccxt.binance({
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        })
        if sandbox:
            self._exchange.set_sandbox_mode(True)
        logger.info("Connesso a Binance (sandbox=%s)", sandbox)

    def fetch_ohlcv(
        self,
        symbol: str = "BTC/USDT",
        timeframe: str = "5m",
        limit: int = 100,
    ) -> pd.DataFrame:
        """Scarica candele OHLCV dall'exchange.

        Args:
            symbol: Coppia di trading.
            timeframe: Intervallo temporale delle candele.
            limit: Numero massimo di candele da scaricare.

        Returns:
            DataFrame con colonne [timestamp, open, high, low, close, volume]
            e indice DatetimeIndex.
        """
        logger.debug("Fetch OHLCV: %s %s (limit=%d)", symbol, timeframe, limit)
        raw = self._exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)
        logger.info("Scaricate %d candele %s %s", len(df), symbol, timeframe)
        return df

    def get_balance(self, currency: str = "USDT") -> float:
        """Restituisce il saldo disponibile (free) per una valuta.

        Args:
            currency: Valuta di cui ottenere il saldo.

        Returns:
            Saldo disponibile.
        """
        balance = self._exchange.fetch_balance()
        free = balance["free"].get(currency, 0.0)
        logger.info("Balance %s: %.4f", currency, free)
        return free

    def create_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        order_type: str = "market",
    ) -> dict:
        """Crea un ordine sull'exchange.

        Args:
            symbol: Coppia di trading.
            side: 'buy' o 'sell'.
            amount: Quantità da comprare/vendere.
            order_type: Tipo di ordine (default: market).

        Returns:
            Risposta dell'ordine da ccxt.
        """
        logger.info("Ordine %s %s: %.6f %s", order_type, side, amount, symbol)
        order = self._exchange.create_order(
            symbol=symbol,
            type=order_type,
            side=side,
            amount=amount,
        )
        logger.info("Ordine eseguito: id=%s status=%s", order.get("id"), order.get("status"))
        return order
```

- [ ] **Step 4: Eseguire i test e verificare che passino**

```bash
pytest tests/test_exchange.py -v
```

Expected: 5 PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/exchange.py tests/test_exchange.py
git commit -m "feat: implement BinanceExchange with OHLCV fetch, balance, and order creation"
```

---

### Task 4: Implementare Entry Point (`src/main.py`)

**Files:**
- Modify: `src/main.py`
- Create: `tests/test_main.py`

- [ ] **Step 1: Scrivere il test per l'argument parser**

```python
# tests/test_main.py
"""Test per l'entry point del bot."""

from src.main import parse_args


def test_parse_args_default_mode():
    """Senza argomenti, il mode deve essere 'paper'."""
    args = parse_args([])
    assert args.mode == "paper"


def test_parse_args_paper_mode():
    """--mode paper deve impostare mode='paper'."""
    args = parse_args(["--mode", "paper"])
    assert args.mode == "paper"


def test_parse_args_live_mode():
    """--mode live deve impostare mode='live'."""
    args = parse_args(["--mode", "live"])
    assert args.mode == "live"
```

- [ ] **Step 2: Eseguire i test per verificare che falliscano**

```bash
pytest tests/test_main.py -v
```

Expected: FAIL — `parse_args` non è implementata.

- [ ] **Step 3: Implementare main.py con argument parser**

```python
# src/main.py
"""Entry point del bot di scalping.

Avvia il loop principale del bot in modalità paper o live.
Gestisce il ciclo: fetch dati → calcolo indicatori → segnale → sentiment → esecuzione.
"""

import argparse
import sys

from src.utils.logger import setup_logger
from config.settings import BOT_MODE, LOG_LEVEL

logger = setup_logger("bot", level=LOG_LEVEL)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parsa gli argomenti della linea di comando.

    Args:
        argv: Lista di argomenti. Se None, usa sys.argv[1:].

    Returns:
        Namespace con gli argomenti parsati.
    """
    parser = argparse.ArgumentParser(description="Scalping Bot — BTC/USDT")
    parser.add_argument(
        "--mode",
        choices=["paper", "live"],
        default="paper",
        help="Modalità di esecuzione (default: paper)",
    )
    return parser.parse_args(argv)


def main() -> None:
    """Entry point principale del bot."""
    args = parse_args()
    logger.info("Avvio bot in modalità: %s", args.mode)

    if args.mode == "live":
        logger.warning("⚠ MODALITÀ LIVE — Ordini reali saranno piazzati!")

    # TODO: Fase 2 — Implementare il loop principale del bot
    logger.info("Bot avviato. In attesa di implementazione loop principale (Fase 2).")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Eseguire i test e verificare che passino**

```bash
pytest tests/test_main.py -v
```

Expected: 3 PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/main.py tests/test_main.py
git commit -m "feat: implement CLI entry point with paper/live mode argument"
```

---

### Task 5: Test di integrazione — Fetch OHLCV da Binance (senza API key)

**Files:**
- Create: `tests/test_exchange_integration.py`

- [ ] **Step 1: Scrivere un test di integrazione che usa le API pubbliche di Binance**

```python
# tests/test_exchange_integration.py
"""Test di integrazione per il fetch OHLCV da Binance.

Questi test chiamano le API pubbliche di Binance (no API key richiesta per OHLCV).
Segnati come 'integration' per poterli saltare in CI.
"""

import pandas as pd
import pytest

from src.exchange import BinanceExchange


@pytest.mark.integration
def test_fetch_ohlcv_live():
    """Verifica che il fetch OHLCV da Binance funzioni con dati reali."""
    exchange = BinanceExchange(api_key="", api_secret="")
    df = exchange.fetch_ohlcv(symbol="BTC/USDT", timeframe="5m", limit=10)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 10
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert isinstance(df.index, pd.DatetimeIndex)
    # Prezzi BTC devono essere ragionevoli (> $1000)
    assert df["close"].iloc[-1] > 1000.0
```

- [ ] **Step 2: Configurare pytest marker per integration test**

Aggiungere `pytest.ini` o `pyproject.toml` config:

```ini
# pytest.ini
[pytest]
markers =
    integration: test che richiedono connessione a internet
```

- [ ] **Step 3: Eseguire il test di integrazione**

```bash
pytest tests/test_exchange_integration.py -v -m integration
```

Expected: 1 PASSED (se connesso a internet). Questo conferma che il modulo exchange funziona con Binance reale.

- [ ] **Step 4: Eseguire TUTTI i test per verifica finale**

```bash
pytest tests/ -v --ignore=tests/test_exchange_integration.py
```

Expected: tutti i test unitari PASSED.

- [ ] **Step 5: Commit**

```bash
git add tests/test_exchange_integration.py pytest.ini
git commit -m "test: add integration test for live Binance OHLCV fetch"
```

---

### Task 6: Commit finale e verifica

- [ ] **Step 1: Eseguire tutti i test (unitari)**

```bash
pytest tests/ -v --ignore=tests/test_exchange_integration.py
```

Expected: 12 test PASSED.

- [ ] **Step 2: Verificare che il bot parta**

```bash
python -m src.main --mode paper
```

Expected: Log "Avvio bot in modalità: paper" e uscita pulita.

- [ ] **Step 3: Commit finale se necessario**

```bash
git status
```

Se ci sono modifiche non committate, fare commit.
