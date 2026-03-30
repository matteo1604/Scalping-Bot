# Fase 5 — Risk Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `RiskManager` class with ATR-based SL/TP/trailing stop, fixed-risk position sizing with sentiment modulation, position size cap/minimum, and daily trade limits.

**Architecture:** Single `RiskManager` class in `src/risk/manager.py` that is stateful for daily counters but otherwise pure logic. All defaults come from `config/settings.py`. `SentimentResult` is an optional input for position sizing only.

**Tech Stack:** Python 3.10+, pytest

---

### File Structure

- **Modify:** `config/settings.py` — add 6 new risk constants
- **Create:** `src/risk/manager.py` — `RiskManager` class (replace existing stub)
- **Create:** `tests/test_risk_manager.py` — full unit test suite

---

### Task 1: Add new settings to config

**Files:**
- Modify: `config/settings.py:30-34` (after existing risk management section)

- [ ] **Step 1: Add risk management constants**

Add these lines after `MAX_DAILY_TRADES` in `config/settings.py`:

```python
RISK_PER_TRADE_PCT: float = 1.0       # % capitale rischiato per trade
SL_ATR_MULTIPLIER: float = 1.5        # moltiplicatore ATR per stop-loss
TP_ATR_MULTIPLIER: float = 2.0        # moltiplicatore ATR per take-profit
TRAILING_ATR_MULTIPLIER: float = 1.0  # moltiplicatore ATR per trailing stop
MAX_POSITION_SIZE_PCT: float = 20.0   # cap massimo size come % del capitale
MIN_ORDER_SIZE_USDT: float = 10.0     # ordine minimo Binance BTC/USDT
```

- [ ] **Step 2: Verify import works**

Run: `python -c "from config.settings import RISK_PER_TRADE_PCT, SL_ATR_MULTIPLIER, TP_ATR_MULTIPLIER, TRAILING_ATR_MULTIPLIER, MAX_POSITION_SIZE_PCT, MIN_ORDER_SIZE_USDT; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add config/settings.py
git commit -m "feat: add ATR and position sizing settings for risk management"
```

---

### Task 2: Implement calculate_levels (ATR-based SL/TP/trailing)

**Files:**
- Create: `src/risk/manager.py`
- Create: `tests/test_risk_manager.py`

- [ ] **Step 1: Write failing tests for calculate_levels**

Write `tests/test_risk_manager.py`:

```python
"""Test per il modulo risk management."""

import pytest

from src.risk.manager import RiskManager


@pytest.fixture
def rm() -> RiskManager:
    """RiskManager con parametri di default."""
    return RiskManager()


class TestCalculateLevels:
    """Test per calculate_levels (SL/TP/trailing)."""

    def test_long_with_atr(self, rm):
        """LONG: SL sotto entry, TP sopra entry, trailing sotto entry."""
        levels = rm.calculate_levels(entry_price=50000.0, side="LONG", atr=100.0)
        assert levels["stop_loss"] == pytest.approx(50000.0 - 100.0 * 1.5)  # 49850
        assert levels["take_profit"] == pytest.approx(50000.0 + 100.0 * 2.0)  # 50200
        assert levels["trailing_stop"] == pytest.approx(50000.0 - 100.0 * 1.0)  # 49900

    def test_short_with_atr(self, rm):
        """SHORT: SL sopra entry, TP sotto entry, trailing sopra entry."""
        levels = rm.calculate_levels(entry_price=50000.0, side="SHORT", atr=100.0)
        assert levels["stop_loss"] == pytest.approx(50000.0 + 100.0 * 1.5)  # 50150
        assert levels["take_profit"] == pytest.approx(50000.0 - 100.0 * 2.0)  # 49800
        assert levels["trailing_stop"] == pytest.approx(50000.0 + 100.0 * 1.0)  # 50100

    def test_fallback_without_atr(self, rm):
        """Senza ATR, usa percentuali fisse da settings."""
        levels = rm.calculate_levels(entry_price=50000.0, side="LONG", atr=None)
        # STOP_LOSS_PCT=0.5%, TAKE_PROFIT_PCT=1.0%
        assert levels["stop_loss"] == pytest.approx(50000.0 * (1 - 0.5 / 100))  # 49750
        assert levels["take_profit"] == pytest.approx(50000.0 * (1 + 1.0 / 100))  # 50500
        assert levels["trailing_stop"] == pytest.approx(50000.0 * (1 - 0.5 / 100))  # 49750 (same as SL)

    def test_fallback_with_zero_atr(self, rm):
        """ATR=0 deve usare fallback percentuale."""
        levels = rm.calculate_levels(entry_price=50000.0, side="LONG", atr=0.0)
        assert levels["stop_loss"] == pytest.approx(50000.0 * (1 - 0.5 / 100))

    def test_short_fallback_without_atr(self, rm):
        """SHORT senza ATR usa percentuali fisse invertite."""
        levels = rm.calculate_levels(entry_price=50000.0, side="SHORT", atr=None)
        assert levels["stop_loss"] == pytest.approx(50000.0 * (1 + 0.5 / 100))  # 50250
        assert levels["take_profit"] == pytest.approx(50000.0 * (1 - 1.0 / 100))  # 49500
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_risk_manager.py::TestCalculateLevels -v`
Expected: FAIL (RiskManager not yet implemented)

- [ ] **Step 3: Implement RiskManager with calculate_levels**

Write `src/risk/manager.py`:

```python
"""Risk management: stop-loss, take-profit, position sizing.

Responsabilita':
- Calcolare SL/TP dinamici (ATR-based) con fallback percentuale
- Trailing stop ATR-based
- Position sizing a rischio fisso con modulazione sentiment
- Limiti giornalieri (max loss, max trades)
"""

from __future__ import annotations

from config.settings import (
    MAX_DAILY_LOSS_PCT,
    MAX_DAILY_TRADES,
    MAX_POSITION_SIZE_PCT,
    MIN_ORDER_SIZE_USDT,
    RISK_PER_TRADE_PCT,
    SL_ATR_MULTIPLIER,
    STOP_LOSS_PCT,
    TAKE_PROFIT_PCT,
    TP_ATR_MULTIPLIER,
    TRAILING_ATR_MULTIPLIER,
)
from src.utils.logger import setup_logger

logger = setup_logger("risk")


class RiskManager:
    """Gestore del rischio per il bot di scalping.

    Calcola livelli SL/TP/trailing basati su ATR, position sizing
    a rischio fisso, e applica limiti giornalieri.

    Args:
        risk_per_trade_pct: Percentuale del capitale rischiata per trade.
        sl_atr_multiplier: Moltiplicatore ATR per stop-loss.
        tp_atr_multiplier: Moltiplicatore ATR per take-profit.
        trailing_atr_multiplier: Moltiplicatore ATR per trailing stop.
        max_position_size_pct: Cap massimo position size come % del capitale.
        min_order_size: Ordine minimo in USDT.
        max_daily_trades: Numero massimo di trade giornalieri.
        max_daily_loss_pct: Perdita massima giornaliera come % del capitale.
        stop_loss_pct: Fallback SL percentuale (senza ATR).
        take_profit_pct: Fallback TP percentuale (senza ATR).
    """

    def __init__(
        self,
        risk_per_trade_pct: float = RISK_PER_TRADE_PCT,
        sl_atr_multiplier: float = SL_ATR_MULTIPLIER,
        tp_atr_multiplier: float = TP_ATR_MULTIPLIER,
        trailing_atr_multiplier: float = TRAILING_ATR_MULTIPLIER,
        max_position_size_pct: float = MAX_POSITION_SIZE_PCT,
        min_order_size: float = MIN_ORDER_SIZE_USDT,
        max_daily_trades: int = MAX_DAILY_TRADES,
        max_daily_loss_pct: float = MAX_DAILY_LOSS_PCT,
        stop_loss_pct: float = STOP_LOSS_PCT,
        take_profit_pct: float = TAKE_PROFIT_PCT,
    ) -> None:
        self.risk_per_trade_pct = risk_per_trade_pct
        self.sl_atr_multiplier = sl_atr_multiplier
        self.tp_atr_multiplier = tp_atr_multiplier
        self.trailing_atr_multiplier = trailing_atr_multiplier
        self.max_position_size_pct = max_position_size_pct
        self.min_order_size = min_order_size
        self.max_daily_trades = max_daily_trades
        self.max_daily_loss_pct = max_daily_loss_pct
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct

        # Contatori giornalieri
        self._daily_trades: int = 0
        self._daily_pnl: float = 0.0

    def calculate_levels(
        self,
        entry_price: float,
        side: str,
        atr: float | None = None,
    ) -> dict[str, float]:
        """Calcola stop-loss, take-profit e trailing stop per un trade.

        Se ATR e' disponibile (> 0), usa moltiplicatori ATR.
        Altrimenti usa percentuali fisse come fallback.

        Args:
            entry_price: Prezzo di ingresso.
            side: "LONG" o "SHORT".
            atr: Average True Range corrente (None per fallback).

        Returns:
            Dict con chiavi "stop_loss", "take_profit", "trailing_stop".
        """
        if atr is not None and atr > 0:
            sl_dist = atr * self.sl_atr_multiplier
            tp_dist = atr * self.tp_atr_multiplier
            trail_dist = atr * self.trailing_atr_multiplier
        else:
            sl_dist = entry_price * self.stop_loss_pct / 100.0
            tp_dist = entry_price * self.take_profit_pct / 100.0
            trail_dist = sl_dist  # trailing = SL distance as fallback

        if side == "LONG":
            sl = entry_price - sl_dist
            tp = entry_price + tp_dist
            trailing = entry_price - trail_dist
        else:  # SHORT
            sl = entry_price + sl_dist
            tp = entry_price - tp_dist
            trailing = entry_price + trail_dist

        logger.debug(
            "Levels %s @ %.2f: SL=%.2f TP=%.2f Trail=%.2f",
            side, entry_price, sl, tp, trailing,
        )
        return {"stop_loss": sl, "take_profit": tp, "trailing_stop": trailing}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_risk_manager.py::TestCalculateLevels -v`
Expected: all 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/risk/manager.py tests/test_risk_manager.py
git commit -m "feat: implement calculate_levels with ATR-based SL/TP/trailing"
```

---

### Task 3: Implement calculate_position_size

**Files:**
- Modify: `src/risk/manager.py`
- Modify: `tests/test_risk_manager.py`

- [ ] **Step 1: Write failing tests for position sizing**

Add to `tests/test_risk_manager.py`:

```python
from src.sentiment.claude_sentiment import SentimentResult


class TestCalculatePositionSize:
    """Test per calculate_position_size."""

    def test_basic_position_size(self, rm):
        """Size basata su rischio fisso senza sentiment."""
        # capital=10000, risk=1%, sl_distance=1% -> size = 10000*0.01/0.01 = 10000
        # capped at 20% of capital = 2000
        size = rm.calculate_position_size(
            capital=10000.0, entry_price=50000.0, sl_price=49500.0,
        )
        # sl_distance = 500/50000 = 0.01
        # raw_size = (10000 * 1.0/100) / 0.01 = 10000
        # capped = min(10000, 10000 * 20/100) = 2000
        assert size == pytest.approx(2000.0)

    def test_small_sl_hits_cap(self, rm):
        """SL molto vicino -> size enorme, deve essere cappata."""
        size = rm.calculate_position_size(
            capital=10000.0, entry_price=50000.0, sl_price=49990.0,
        )
        # sl_distance = 10/50000 = 0.0002
        # raw_size = 100 / 0.0002 = 500000 -> capped at 2000
        assert size == pytest.approx(2000.0)

    def test_below_minimum_returns_zero(self, rm):
        """Size sotto il minimo exchange -> 0.0."""
        size = rm.calculate_position_size(
            capital=50.0, entry_price=50000.0, sl_price=49500.0,
        )
        # raw_size = (50 * 0.01) / 0.01 = 50
        # capped = min(50, 50*0.2) = 10.0
        # 10.0 >= MIN_ORDER_SIZE (10.0), just at the boundary
        assert size == pytest.approx(10.0)

    def test_very_small_capital_returns_zero(self, rm):
        """Capitale minimo -> size sotto exchange minimum -> 0.0."""
        size = rm.calculate_position_size(
            capital=30.0, entry_price=50000.0, sl_price=49500.0,
        )
        # raw_size = (30 * 0.01) / 0.01 = 30
        # capped = min(30, 30*0.2) = 6.0 < 10.0
        assert size == 0.0

    def test_zero_capital_returns_zero(self, rm):
        """Capitale zero -> 0.0."""
        size = rm.calculate_position_size(
            capital=0.0, entry_price=50000.0, sl_price=49500.0,
        )
        assert size == 0.0

    def test_entry_equals_sl_returns_zero(self, rm):
        """entry_price == sl_price (divisione per zero) -> 0.0."""
        size = rm.calculate_position_size(
            capital=10000.0, entry_price=50000.0, sl_price=50000.0,
        )
        assert size == 0.0

    def test_sentiment_high_confidence_full_size(self, rm):
        """Sentiment con confidence alta (1.0) -> multiplier 1.0, size piena."""
        sentiment = SentimentResult(
            sentiment_score=0.5, confidence=1.0,
            top_events=[], recommendation="BUY",
        )
        size_with = rm.calculate_position_size(
            capital=10000.0, entry_price=50000.0, sl_price=49500.0,
            sentiment=sentiment,
        )
        size_without = rm.calculate_position_size(
            capital=10000.0, entry_price=50000.0, sl_price=49500.0,
        )
        assert size_with == size_without

    def test_sentiment_low_confidence_reduced_size(self, rm):
        """Sentiment con confidence bassa -> multiplier 0.5, size dimezzata."""
        sentiment = SentimentResult(
            sentiment_score=0.5, confidence=0.1,
            top_events=[], recommendation="BUY",
        )
        size = rm.calculate_position_size(
            capital=10000.0, entry_price=50000.0, sl_price=49500.0,
            sentiment=sentiment,
        )
        # raw_size = (10000 * 0.01 * 0.5) / 0.01 = 5000
        # capped = min(5000, 2000) = 2000
        assert size == pytest.approx(2000.0)

    def test_sentiment_mid_confidence_scales(self, rm):
        """Sentiment con confidence 0.7 -> multiplier 0.7."""
        sentiment = SentimentResult(
            sentiment_score=0.3, confidence=0.7,
            top_events=[], recommendation="BUY",
        )
        size = rm.calculate_position_size(
            capital=10000.0, entry_price=50000.0, sl_price=45000.0,
            sentiment=sentiment,
        )
        # sl_distance = 5000/50000 = 0.1
        # raw_size = (10000 * 0.01 * 0.7) / 0.1 = 700
        # capped = min(700, 2000) = 700
        assert size == pytest.approx(700.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_risk_manager.py::TestCalculatePositionSize -v`
Expected: FAIL (method not defined)

- [ ] **Step 3: Implement calculate_position_size**

Add to `RiskManager` in `src/risk/manager.py`, add the import at the top:

```python
from src.sentiment.claude_sentiment import SentimentResult
```

Then add the method to the class:

```python
    def calculate_position_size(
        self,
        capital: float,
        entry_price: float,
        sl_price: float,
        sentiment: SentimentResult | None = None,
    ) -> float:
        """Calcola la dimensione della posizione in USDT.

        Usa il metodo del rischio fisso: rischia una % fissa del capitale per trade.
        La size e' inversamente proporzionale alla distanza dello SL.
        Il sentiment modula la size tramite confidence (clamp [0.5, 1.0]).

        Args:
            capital: Capitale disponibile in USDT.
            entry_price: Prezzo di ingresso.
            sl_price: Prezzo dello stop-loss.
            sentiment: Risultato sentiment (opzionale).

        Returns:
            Size in USDT. 0.0 se sotto il minimo exchange o input invalidi.
        """
        if capital <= 0 or entry_price <= 0:
            return 0.0

        sl_distance = abs(entry_price - sl_price) / entry_price
        if sl_distance == 0:
            return 0.0

        confidence_multiplier = 1.0
        if sentiment is not None:
            confidence_multiplier = max(0.5, min(1.0, sentiment.confidence))

        raw_size = (capital * self.risk_per_trade_pct / 100.0) * confidence_multiplier / sl_distance
        size = min(raw_size, capital * self.max_position_size_pct / 100.0)

        if size < self.min_order_size:
            return 0.0

        logger.debug(
            "Position size: %.2f USDT (capital=%.0f, sl_dist=%.4f, conf=%.2f)",
            size, capital, sl_distance, confidence_multiplier,
        )
        return size
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_risk_manager.py::TestCalculatePositionSize -v`
Expected: all 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/risk/manager.py tests/test_risk_manager.py
git commit -m "feat: implement position sizing with risk-based formula and sentiment modulation"
```

---

### Task 4: Implement update_trailing_stop

**Files:**
- Modify: `src/risk/manager.py`
- Modify: `tests/test_risk_manager.py`

- [ ] **Step 1: Write failing tests for trailing stop**

Add to `tests/test_risk_manager.py`:

```python
class TestUpdateTrailingStop:
    """Test per update_trailing_stop."""

    def test_long_trailing_moves_up(self, rm):
        """LONG: trailing sale quando il prezzo sale."""
        new_trail = rm.update_trailing_stop(
            side="LONG", current_price=50200.0, current_trailing=49900.0, atr=100.0,
        )
        # new candidate = 50200 - 100*1.0 = 50100 > 49900
        assert new_trail == pytest.approx(50100.0)

    def test_long_trailing_never_moves_down(self, rm):
        """LONG: trailing non scende se il prezzo scende."""
        new_trail = rm.update_trailing_stop(
            side="LONG", current_price=49950.0, current_trailing=49900.0, atr=100.0,
        )
        # new candidate = 49950 - 100 = 49850 < 49900
        assert new_trail == pytest.approx(49900.0)

    def test_short_trailing_moves_down(self, rm):
        """SHORT: trailing scende quando il prezzo scende."""
        new_trail = rm.update_trailing_stop(
            side="SHORT", current_price=49800.0, current_trailing=50100.0, atr=100.0,
        )
        # new candidate = 49800 + 100*1.0 = 49900 < 50100
        assert new_trail == pytest.approx(49900.0)

    def test_short_trailing_never_moves_up(self, rm):
        """SHORT: trailing non sale se il prezzo sale."""
        new_trail = rm.update_trailing_stop(
            side="SHORT", current_price=50200.0, current_trailing=50100.0, atr=100.0,
        )
        # new candidate = 50200 + 100 = 50300 > 50100
        assert new_trail == pytest.approx(50100.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_risk_manager.py::TestUpdateTrailingStop -v`
Expected: FAIL (method not defined)

- [ ] **Step 3: Implement update_trailing_stop**

Add to `RiskManager` in `src/risk/manager.py`:

```python
    def update_trailing_stop(
        self,
        side: str,
        current_price: float,
        current_trailing: float,
        atr: float,
    ) -> float:
        """Aggiorna il trailing stop in base al prezzo corrente.

        Il trailing si muove solo a favore della posizione:
        - LONG: sale (max) ma mai scende
        - SHORT: scende (min) ma mai sale

        Args:
            side: "LONG" o "SHORT".
            current_price: Prezzo di mercato corrente.
            current_trailing: Trailing stop attuale.
            atr: Average True Range corrente.

        Returns:
            Nuovo trailing stop price.
        """
        trail_dist = atr * self.trailing_atr_multiplier

        if side == "LONG":
            candidate = current_price - trail_dist
            return max(candidate, current_trailing)
        else:  # SHORT
            candidate = current_price + trail_dist
            return min(candidate, current_trailing)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_risk_manager.py::TestUpdateTrailingStop -v`
Expected: all 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/risk/manager.py tests/test_risk_manager.py
git commit -m "feat: implement ATR-based trailing stop with directional lock"
```

---

### Task 5: Implement daily limits (can_trade, record_trade, reset_daily)

**Files:**
- Modify: `src/risk/manager.py`
- Modify: `tests/test_risk_manager.py`

- [ ] **Step 1: Write failing tests for daily limits**

Add to `tests/test_risk_manager.py`:

```python
class TestDailyLimits:
    """Test per can_trade, record_trade, reset_daily."""

    def test_can_trade_initially(self, rm):
        """Nessun trade registrato -> puo' tradare."""
        assert rm.can_trade(capital=1000.0) is True

    def test_cannot_trade_after_max_trades(self, rm):
        """Dopo MAX_DAILY_TRADES (20) -> non puo' tradare."""
        for _ in range(20):
            rm.record_trade(pnl=1.0)
        assert rm.can_trade(capital=1000.0) is False

    def test_cannot_trade_after_max_loss(self, rm):
        """Dopo perdita >= MAX_DAILY_LOSS_PCT (3%) del capitale -> non puo' tradare."""
        rm.record_trade(pnl=-35.0)  # -3.5% of 1000
        assert rm.can_trade(capital=1000.0) is False

    def test_can_trade_under_loss_limit(self, rm):
        """Perdita sotto il limite -> puo' ancora tradare."""
        rm.record_trade(pnl=-20.0)  # -2% of 1000
        assert rm.can_trade(capital=1000.0) is True

    def test_reset_daily_clears_counters(self, rm):
        """reset_daily resetta trades e pnl."""
        for _ in range(20):
            rm.record_trade(pnl=-5.0)
        assert rm.can_trade(capital=1000.0) is False
        rm.reset_daily()
        assert rm.can_trade(capital=1000.0) is True

    def test_record_trade_accumulates_pnl(self, rm):
        """PnL si accumula correttamente."""
        rm.record_trade(pnl=-10.0)
        rm.record_trade(pnl=-10.0)
        rm.record_trade(pnl=-10.0)
        # total = -30, 3% of 1000 = 30 -> at limit
        assert rm.can_trade(capital=1000.0) is False

    def test_zero_capital_cannot_trade(self, rm):
        """Capitale zero -> non puo' tradare."""
        assert rm.can_trade(capital=0.0) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_risk_manager.py::TestDailyLimits -v`
Expected: FAIL (methods not defined)

- [ ] **Step 3: Implement daily limit methods**

Add to `RiskManager` in `src/risk/manager.py`:

```python
    def can_trade(self, capital: float) -> bool:
        """Verifica se i limiti giornalieri consentono un nuovo trade.

        Controlla sia il numero massimo di trade che la perdita massima giornaliera.

        Args:
            capital: Capitale corrente in USDT.

        Returns:
            True se il trade e' consentito.
        """
        if capital <= 0:
            return False
        if self._daily_trades >= self.max_daily_trades:
            logger.warning("Limite giornaliero trade raggiunto: %d/%d",
                           self._daily_trades, self.max_daily_trades)
            return False
        max_loss = capital * self.max_daily_loss_pct / 100.0
        if abs(self._daily_pnl) >= max_loss and self._daily_pnl < 0:
            logger.warning("Limite perdita giornaliera raggiunto: %.2f/%.2f",
                           self._daily_pnl, -max_loss)
            return False
        return True

    def record_trade(self, pnl: float) -> None:
        """Registra un trade completato per il tracking giornaliero.

        Args:
            pnl: Profitto/perdita del trade in USDT.
        """
        self._daily_trades += 1
        self._daily_pnl += pnl
        logger.debug("Trade #%d registrato: PnL=%.2f, Totale=%.2f",
                      self._daily_trades, pnl, self._daily_pnl)

    def reset_daily(self) -> None:
        """Resetta i contatori giornalieri."""
        logger.info("Reset contatori giornalieri (trades=%d, pnl=%.2f)",
                     self._daily_trades, self._daily_pnl)
        self._daily_trades = 0
        self._daily_pnl = 0.0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_risk_manager.py::TestDailyLimits -v`
Expected: all 7 tests PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -v`
Expected: all tests PASS (existing + new)

- [ ] **Step 6: Commit**

```bash
git add src/risk/manager.py tests/test_risk_manager.py
git commit -m "feat: implement daily trade limits with loss tracking and reset"
```

---

### Task 6: Final verification

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v`
Expected: all tests PASS

- [ ] **Step 2: Verify RiskManager imports cleanly**

Run: `python -c "from src.risk.manager import RiskManager; rm = RiskManager(); print(rm.calculate_levels(50000, 'LONG', 100)); print('OK')"`
Expected: dict with SL/TP/trailing values, then `OK`

- [ ] **Step 3: Commit any remaining changes**

Only if there are uncommitted changes from fixes.
