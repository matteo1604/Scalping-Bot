# Fase 5 — Risk Management Avanzato: Design Spec

## Goal

Implementare `RiskManager` in `src/risk/manager.py` per gestire stop-loss/take-profit dinamici (ATR-based), trailing stop, position sizing a rischio fisso con modulazione sentiment, e limiti giornalieri.

## Architecture

Una singola classe `RiskManager` stateful (per conteggi giornalieri) che:
- Calcola SL/TP/trailing stop basati su ATR
- Determina position sizing con rischio fisso per trade
- Traccia limiti giornalieri e decide se un nuovo trade e' consentito

Nessuna dipendenza esterna. Pura logica, facilmente testabile.

## Components

### 1. Stop-Loss & Take-Profit (ATR-based)

- SL = `entry_price -/+ atr * sl_atr_multiplier` (LONG/SHORT)
- TP = `entry_price +/- atr * tp_atr_multiplier` (LONG/SHORT)
- Default multipliers: SL=1.5, TP=2.0
- Fallback: se ATR non disponibile (None/0), usa percentuali fisse da settings (`STOP_LOSS_PCT`, `TAKE_PROFIT_PCT`)

### 2. Trailing Stop (ATR-based)

- Distanza trailing = `atr * trailing_atr_multiplier` (default: 1.0)
- LONG: trailing = max(current_trailing, current_price - trailing_distance)
- SHORT: trailing = min(current_trailing, current_price + trailing_distance)
- Il trailing si muove solo a favore, mai contro la posizione

### 3. Position Sizing (rischio fisso)

Formula:
```
sl_distance = abs(entry_price - sl_price) / entry_price  # in percentuale
raw_size = (capital * risk_per_trade_pct / 100) * confidence_multiplier / sl_distance
size = min(raw_size, capital * MAX_POSITION_SIZE_PCT / 100)  # cap massimo
if size < MIN_ORDER_SIZE_USDT: return 0.0                    # minimo exchange
return size
```

- `risk_per_trade_pct`: default 1.0% del capitale
- `confidence_multiplier`: da sentiment.confidence, clampato in [0.5, 1.0]
- Senza sentiment: multiplier = 1.0
- `MAX_POSITION_SIZE_PCT`: 20.0% del capitale (hard cap)
- `MIN_ORDER_SIZE_USDT`: 10.0 USDT (minimo Binance BTC/USDT)

### 4. Limiti giornalieri

- `can_trade(capital)` -> bool: verifica entrambi i limiti
  - trades giornalieri < MAX_DAILY_TRADES
  - perdita giornaliera < MAX_DAILY_LOSS_PCT del capitale
- `record_trade(pnl)` -> aggiorna contatori interni
- `reset_daily()` -> resetta contatori a inizio giornata

## Interface

```python
class RiskManager:
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
    ) -> None: ...

    def calculate_levels(self, entry_price: float, side: str, atr: float | None = None) -> dict:
        """Returns {"stop_loss": float, "take_profit": float, "trailing_stop": float}"""

    def calculate_position_size(
        self, capital: float, entry_price: float, sl_price: float,
        sentiment: SentimentResult | None = None,
    ) -> float:
        """Returns size in USDT. 0.0 if below exchange minimum."""

    def update_trailing_stop(
        self, side: str, current_price: float, current_trailing: float, atr: float,
    ) -> float:
        """Returns updated trailing stop price."""

    def can_trade(self, capital: float) -> bool:
        """True if daily limits allow a new trade."""

    def record_trade(self, pnl: float) -> None:
        """Records a completed trade for daily tracking."""

    def reset_daily(self) -> None:
        """Resets daily counters."""
```

## New Settings (config/settings.py)

```python
RISK_PER_TRADE_PCT: float = 1.0       # % capitale rischiato per trade
SL_ATR_MULTIPLIER: float = 1.5        # moltiplicatore ATR per stop-loss
TP_ATR_MULTIPLIER: float = 2.0        # moltiplicatore ATR per take-profit
TRAILING_ATR_MULTIPLIER: float = 1.0  # moltiplicatore ATR per trailing stop
MAX_POSITION_SIZE_PCT: float = 20.0   # cap massimo size come % del capitale
MIN_ORDER_SIZE_USDT: float = 10.0     # ordine minimo Binance BTC/USDT
```

## Testing

Unit test in `tests/test_risk_manager.py`:
- `calculate_levels`: LONG/SHORT con ATR, fallback senza ATR
- `calculate_position_size`: caso normale, cap massimo, sotto minimo, con/senza sentiment, confidence bassa/alta
- `update_trailing_stop`: trailing sale per LONG, scende per SHORT, mai contromano
- `can_trade`: sotto/sopra limiti trades, sotto/sopra limiti perdita
- `record_trade` + `reset_daily`: conteggio corretto, reset funzionante
- Edge case: capital=0, ATR=0, entry=sl (divisione per zero)

## Dependencies

- `config.settings` per tutti i default
- `SentimentResult` (import opzionale, solo in `calculate_position_size`)
- Nessuna dipendenza esterna
