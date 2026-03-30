# Fase 3 — Backtesting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Creare un motore di backtesting che simuli l'esecuzione dei segnali della CombinedStrategy su dati storici OHLCV, calcolando metriche di performance (win rate, profit factor, max drawdown, Sharpe ratio) e salvando report JSON.

**Architecture:** Due moduli: `src/backtesting/engine.py` contiene la classe `Backtester` che itera sulle candele, applica indicatori e strategia, simula trade con stop-loss/take-profit. `src/backtesting/metrics.py` contiene funzioni pure per calcolare le metriche da una lista di trade. I report vengono salvati in `data/backtest_results/`.

**Tech Stack:** Python 3.10+, pandas, numpy, pytest, json

---

### File Structure

| File | Responsabilità |
|------|---------------|
| `src/backtesting/__init__.py` | Package init |
| `src/backtesting/metrics.py` | Funzioni pure: win_rate, profit_factor, max_drawdown, sharpe_ratio |
| `src/backtesting/engine.py` | Classe Backtester: loop su candele, simulazione trade |
| `tests/test_metrics.py` | Test per le metriche |
| `tests/test_backtester.py` | Test per il motore di backtesting |

---

### Task 1: Implementare metriche di performance (`src/backtesting/metrics.py`)

**Files:**
- Create: `src/backtesting/__init__.py`
- Create: `src/backtesting/metrics.py`
- Create: `tests/test_metrics.py`

- [ ] **Step 1: Scrivere i test per le metriche**

```python
# tests/test_metrics.py
"""Test per le metriche di backtesting."""

import pytest
from src.backtesting.metrics import win_rate, profit_factor, max_drawdown, sharpe_ratio


class TestWinRate:
    """Test per win_rate."""

    def test_all_winners(self):
        trades = [{"pnl": 10.0}, {"pnl": 20.0}, {"pnl": 5.0}]
        assert win_rate(trades) == 100.0

    def test_all_losers(self):
        trades = [{"pnl": -10.0}, {"pnl": -20.0}]
        assert win_rate(trades) == 0.0

    def test_mixed(self):
        trades = [{"pnl": 10.0}, {"pnl": -5.0}, {"pnl": 20.0}, {"pnl": -3.0}]
        assert win_rate(trades) == 50.0

    def test_empty(self):
        assert win_rate([]) == 0.0


class TestProfitFactor:
    """Test per profit_factor."""

    def test_profitable(self):
        trades = [{"pnl": 30.0}, {"pnl": -10.0}]
        assert profit_factor(trades) == 3.0

    def test_no_losses(self):
        trades = [{"pnl": 10.0}, {"pnl": 20.0}]
        assert profit_factor(trades) == float("inf")

    def test_no_wins(self):
        trades = [{"pnl": -10.0}, {"pnl": -20.0}]
        assert profit_factor(trades) == 0.0

    def test_empty(self):
        assert profit_factor([]) == 0.0


class TestMaxDrawdown:
    """Test per max_drawdown."""

    def test_simple_drawdown(self):
        # Equity: 100 -> 110 -> 90 -> 120
        trades = [{"pnl": 10.0}, {"pnl": -20.0}, {"pnl": 30.0}]
        dd = max_drawdown(trades, initial_capital=100.0)
        # Peak = 110, trough = 90, drawdown = 20/110 = 18.18%
        assert abs(dd - 18.18) < 0.1

    def test_no_drawdown(self):
        trades = [{"pnl": 10.0}, {"pnl": 20.0}]
        assert max_drawdown(trades, initial_capital=100.0) == 0.0

    def test_empty(self):
        assert max_drawdown([], initial_capital=100.0) == 0.0


class TestSharpeRatio:
    """Test per sharpe_ratio."""

    def test_positive_sharpe(self):
        trades = [{"pnl": 10.0}, {"pnl": 12.0}, {"pnl": 8.0}, {"pnl": 11.0}]
        sr = sharpe_ratio(trades)
        assert sr > 0

    def test_all_same_returns(self):
        trades = [{"pnl": 10.0}, {"pnl": 10.0}, {"pnl": 10.0}]
        # Std = 0, sharpe = inf o un valore molto alto
        sr = sharpe_ratio(trades)
        assert sr == float("inf")

    def test_empty(self):
        assert sharpe_ratio([]) == 0.0
```

- [ ] **Step 2: Eseguire i test per verificare che falliscano**

Run: `pytest tests/test_metrics.py -v`
Expected: FAIL — modulo non esiste.

- [ ] **Step 3: Implementare le metriche**

```python
# src/backtesting/__init__.py
# (vuoto)

# src/backtesting/metrics.py
"""Metriche di performance per backtesting.

Funzioni pure che calcolano metriche da una lista di trade.
Ogni trade e' un dict con almeno la chiave "pnl" (profit/loss in USDT).
"""

import numpy as np


def win_rate(trades: list[dict]) -> float:
    """Percentuale di trade in profitto.

    Args:
        trades: Lista di trade con chiave "pnl".

    Returns:
        Win rate in percentuale (0-100).
    """
    if not trades:
        return 0.0
    winners = sum(1 for t in trades if t["pnl"] > 0)
    return (winners / len(trades)) * 100.0


def profit_factor(trades: list[dict]) -> float:
    """Rapporto tra profitti totali e perdite totali.

    Args:
        trades: Lista di trade con chiave "pnl".

    Returns:
        Profit factor (> 1.0 = profittevole). inf se non ci sono perdite.
    """
    if not trades:
        return 0.0
    gross_profit = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    gross_loss = abs(sum(t["pnl"] for t in trades if t["pnl"] < 0))
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def max_drawdown(trades: list[dict], initial_capital: float = 1000.0) -> float:
    """Massimo drawdown percentuale dalla equity curve.

    Args:
        trades: Lista di trade con chiave "pnl".
        initial_capital: Capitale iniziale.

    Returns:
        Max drawdown in percentuale (0-100).
    """
    if not trades:
        return 0.0
    equity = initial_capital
    peak = equity
    max_dd = 0.0
    for t in trades:
        equity += t["pnl"]
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak * 100.0 if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
    return max_dd


def sharpe_ratio(trades: list[dict], annualization: float = 252.0) -> float:
    """Sharpe ratio annualizzato dei rendimenti dei trade.

    Args:
        trades: Lista di trade con chiave "pnl".
        annualization: Fattore di annualizzazione (default: 252 giorni).

    Returns:
        Sharpe ratio. inf se std == 0 e media > 0.
    """
    if not trades:
        return 0.0
    returns = np.array([t["pnl"] for t in trades])
    mean_r = returns.mean()
    std_r = returns.std(ddof=1) if len(returns) > 1 else 0.0
    if std_r == 0:
        return float("inf") if mean_r > 0 else 0.0
    return float((mean_r / std_r) * np.sqrt(annualization))
```

- [ ] **Step 4: Eseguire i test e verificare che passino**

Run: `pytest tests/test_metrics.py -v`
Expected: 12 PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/backtesting/ tests/test_metrics.py
git commit -m "feat: implement backtesting metrics (win rate, profit factor, drawdown, sharpe)"
```

---

### Task 2: Implementare Backtester engine (`src/backtesting/engine.py`)

**Files:**
- Create: `src/backtesting/engine.py`
- Create: `tests/test_backtester.py`

- [ ] **Step 1: Scrivere i test per Backtester**

```python
# tests/test_backtester.py
"""Test per il motore di backtesting."""

import pandas as pd
import numpy as np
import json
import pytest

from src.backtesting.engine import Backtester


@pytest.fixture
def trending_up_df() -> pd.DataFrame:
    """DataFrame con trend rialzista che genera almeno un crossover bullish."""
    np.random.seed(42)
    n = 100
    # Trend inizialmente piatto poi rialzista -> genera crossover EMA
    close = np.concatenate([
        np.full(30, 35000.0) + np.random.randn(30) * 10,  # flat
        35000.0 + np.cumsum(np.abs(np.random.randn(70)) * 15),  # trend up
    ])
    df = pd.DataFrame({
        "open": close - np.random.rand(n) * 5,
        "high": close + np.random.rand(n) * 10,
        "low": close - np.random.rand(n) * 10,
        "close": close,
        "volume": np.random.rand(n) * 200 + 100,  # volume sempre sopra media
    }, index=pd.date_range("2026-01-01", periods=n, freq="5min"))
    return df


@pytest.fixture
def flat_df() -> pd.DataFrame:
    """DataFrame piatto che non dovrebbe generare crossover."""
    n = 100
    close = np.full(n, 35000.0)
    df = pd.DataFrame({
        "open": close,
        "high": close + 1,
        "low": close - 1,
        "close": close,
        "volume": np.full(n, 100.0),
    }, index=pd.date_range("2026-01-01", periods=n, freq="5min"))
    return df


class TestBacktesterInit:
    """Test per inizializzazione Backtester."""

    def test_creates_with_defaults(self):
        bt = Backtester()
        assert bt.initial_capital > 0
        assert bt.stop_loss_pct > 0
        assert bt.take_profit_pct > 0

    def test_custom_params(self):
        bt = Backtester(initial_capital=5000.0, stop_loss_pct=1.0, take_profit_pct=2.0)
        assert bt.initial_capital == 5000.0
        assert bt.stop_loss_pct == 1.0
        assert bt.take_profit_pct == 2.0


class TestBacktesterRun:
    """Test per l'esecuzione del backtest."""

    def test_returns_result_dict(self, trending_up_df):
        bt = Backtester()
        result = bt.run(trending_up_df)
        assert isinstance(result, dict)
        assert "trades" in result
        assert "metrics" in result
        assert "equity_final" in result

    def test_metrics_keys(self, trending_up_df):
        bt = Backtester()
        result = bt.run(trending_up_df)
        metrics = result["metrics"]
        for key in ["win_rate", "profit_factor", "max_drawdown", "sharpe_ratio", "total_trades"]:
            assert key in metrics

    def test_no_trades_on_flat(self, flat_df):
        bt = Backtester()
        result = bt.run(flat_df)
        assert result["metrics"]["total_trades"] == 0

    def test_trades_have_required_fields(self, trending_up_df):
        bt = Backtester()
        result = bt.run(trending_up_df)
        if result["trades"]:
            trade = result["trades"][0]
            for key in ["entry_time", "exit_time", "side", "entry_price", "exit_price", "pnl"]:
                assert key in trade


class TestBacktesterSaveReport:
    """Test per il salvataggio del report."""

    def test_saves_json(self, trending_up_df, tmp_path):
        bt = Backtester()
        result = bt.run(trending_up_df)
        filepath = bt.save_report(result, output_dir=str(tmp_path))
        assert filepath.endswith(".json")
        with open(filepath) as f:
            data = json.load(f)
        assert "metrics" in data
        assert "trades" in data
```

- [ ] **Step 2: Eseguire i test per verificare che falliscano**

Run: `pytest tests/test_backtester.py -v`
Expected: FAIL — `Backtester` non esiste.

- [ ] **Step 3: Implementare Backtester**

```python
# src/backtesting/engine.py
"""Motore di backtesting per la strategia di scalping.

Simula l'esecuzione dei segnali su dati storici OHLCV con stop-loss e take-profit.
"""

import json
import os
from datetime import datetime

import pandas as pd

from config.settings import STOP_LOSS_PCT, TAKE_PROFIT_PCT, TRADE_AMOUNT_USDT
from src.indicators.technical import add_indicators, add_prev_indicators
from src.strategies.combined import CombinedStrategy
from src.backtesting.metrics import win_rate, profit_factor, max_drawdown, sharpe_ratio
from src.utils.logger import setup_logger

logger = setup_logger("backtester")


class Backtester:
    """Motore di backtesting per simulare trade su dati storici.

    Args:
        initial_capital: Capitale iniziale in USDT.
        stop_loss_pct: Stop loss in percentuale.
        take_profit_pct: Take profit in percentuale.
        trade_amount: Importo per trade in USDT.
    """

    def __init__(
        self,
        initial_capital: float = 1000.0,
        stop_loss_pct: float = STOP_LOSS_PCT,
        take_profit_pct: float = TAKE_PROFIT_PCT,
        trade_amount: float = TRADE_AMOUNT_USDT,
    ) -> None:
        self.initial_capital = initial_capital
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.trade_amount = trade_amount
        self.strategy = CombinedStrategy()

    def run(self, df: pd.DataFrame) -> dict:
        """Esegue il backtest su un DataFrame OHLCV.

        Args:
            df: DataFrame con colonne [open, high, low, close, volume].

        Returns:
            Dict con chiavi: trades, metrics, equity_final.
        """
        # Prepara indicatori
        data = add_indicators(df)
        data = add_prev_indicators(data)
        data = data.dropna()

        trades: list[dict] = []
        position: dict | None = None
        equity = self.initial_capital

        for i in range(len(data)):
            row = data.iloc[i]

            # Se abbiamo una posizione aperta, controlla SL/TP
            if position is not None:
                pnl_pct = self._calc_pnl_pct(position, row["close"])

                hit_sl = pnl_pct <= -self.stop_loss_pct
                hit_tp = pnl_pct >= self.take_profit_pct

                if hit_sl or hit_tp:
                    pnl = (pnl_pct / 100.0) * self.trade_amount
                    trade = {
                        "entry_time": str(position["entry_time"]),
                        "exit_time": str(data.index[i]),
                        "side": position["side"],
                        "entry_price": position["entry_price"],
                        "exit_price": row["close"],
                        "pnl_pct": round(pnl_pct, 4),
                        "pnl": round(pnl, 4),
                        "exit_reason": "stop_loss" if hit_sl else "take_profit",
                    }
                    trades.append(trade)
                    equity += pnl
                    position = None
                continue  # Non aprire nuove posizioni mentre siamo in trade

            # Genera segnale
            window = data.iloc[: i + 1]
            signal = self.strategy.generate_signal(window)

            if signal in ("LONG", "SHORT"):
                position = {
                    "side": signal,
                    "entry_price": row["close"],
                    "entry_time": data.index[i],
                }

        # Chiudi posizione aperta a fine backtest
        if position is not None:
            last_row = data.iloc[-1]
            pnl_pct = self._calc_pnl_pct(position, last_row["close"])
            pnl = (pnl_pct / 100.0) * self.trade_amount
            trade = {
                "entry_time": str(position["entry_time"]),
                "exit_time": str(data.index[-1]),
                "side": position["side"],
                "entry_price": position["entry_price"],
                "exit_price": last_row["close"],
                "pnl_pct": round(pnl_pct, 4),
                "pnl": round(pnl, 4),
                "exit_reason": "end_of_data",
            }
            trades.append(trade)
            equity += pnl

        metrics = {
            "total_trades": len(trades),
            "win_rate": round(win_rate(trades), 2),
            "profit_factor": round(profit_factor(trades), 2) if profit_factor(trades) != float("inf") else "inf",
            "max_drawdown": round(max_drawdown(trades, self.initial_capital), 2),
            "sharpe_ratio": round(sharpe_ratio(trades), 2) if sharpe_ratio(trades) != float("inf") else "inf",
        }

        logger.info("Backtest completato: %d trade, WR=%.1f%%, PF=%s",
                     metrics["total_trades"], metrics["win_rate"], metrics["profit_factor"])

        return {
            "trades": trades,
            "metrics": metrics,
            "equity_final": round(equity, 2),
            "initial_capital": self.initial_capital,
        }

    def save_report(self, result: dict, output_dir: str = "data/backtest_results") -> str:
        """Salva il report del backtest in formato JSON.

        Args:
            result: Risultato del backtest da run().
            output_dir: Directory di output.

        Returns:
            Path del file salvato.
        """
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"backtest_{timestamp}.json"
        filepath = os.path.join(output_dir, filename)
        with open(filepath, "w") as f:
            json.dump(result, f, indent=2, default=str)
        logger.info("Report salvato: %s", filepath)
        return filepath

    @staticmethod
    def _calc_pnl_pct(position: dict, current_price: float) -> float:
        """Calcola il PnL percentuale di una posizione.

        Args:
            position: Dict con "side" e "entry_price".
            current_price: Prezzo corrente.

        Returns:
            PnL in percentuale.
        """
        entry = position["entry_price"]
        if position["side"] == "LONG":
            return ((current_price - entry) / entry) * 100.0
        else:  # SHORT
            return ((entry - current_price) / entry) * 100.0
```

- [ ] **Step 4: Eseguire i test e verificare che passino**

Run: `pytest tests/test_backtester.py -v`
Expected: 7 PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/backtesting/engine.py tests/test_backtester.py
git commit -m "feat: implement Backtester engine with SL/TP simulation"
```

---

### Task 3: Verifica finale

- [ ] **Step 1: Eseguire tutti i test unitari**

```bash
pytest tests/ -v --ignore=tests/test_exchange_integration.py
```

Expected: tutti PASSED.

- [ ] **Step 2: Commit piano e file residui**

```bash
git status
```
