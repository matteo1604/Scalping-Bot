# Fase 6 — Paper Trading: Design Spec

## Goal

Implementare il loop principale del bot in modalita' paper trading: orchestrare tutti i componenti esistenti (exchange, indicatori, strategia, sentiment, risk management) in un ciclo continuo sincronizzato alle candele 5min, con simulazione trade e file di stato JSON per monitoraggio.

## Architecture

Il loop vive in `src/main.py` come classe `TradingLoop`. Ad ogni chiusura candela 5min:
1. Fetch OHLCV da Binance
2. Calcola indicatori → genera segnale
3. Se segnale tecnico → chiama sentiment (con cooldown 15min) → filtra
4. Se confermato → risk check → simula apertura posizione
5. Se posizione aperta → controlla SL/TP/trailing
6. Aggiorna file di stato JSON

Graceful shutdown su SIGINT/SIGTERM. Paper mode non piazza ordini reali.

## Components

### 1. TradingLoop (`src/main.py`)

Classe che orchestra il ciclo principale.

```python
class TradingLoop:
    def __init__(self, mode: str = "paper") -> None: ...
    def run(self) -> None:                    # loop infinito con graceful shutdown
    def _wait_for_candle(self) -> None:       # sleep fino a prossima chiusura 5min
    def _tick(self) -> None:                  # singolo ciclo completo
    def _check_open_position(self, row) -> None:  # SL/TP/trailing su posizione aperta
    def _open_position(self, signal, row, sentiment) -> None:  # apri nuova posizione
    def _close_position(self, row, reason) -> None:  # chiudi posizione
```

**Logica di `_tick()`:**
- Fetch 100 candele OHLCV
- Calcola indicatori + prev indicators, dropna
- Se posizione aperta: check trailing stop update + SL/TP hit sulla ultima candela
- Se nessuna posizione: genera segnale
- Se segnale tecnico: chiama sentiment (via cache), rigenera con filtro
- Se segnale confermato: `risk_manager.can_trade()` → `calculate_levels()` → `calculate_position_size()` → apri
- Aggiorna status file

**Gestione posizione aperta:**
- Tiene un dict `_position` con: side, entry_price, entry_time, stop_loss, take_profit, trailing_stop, size_usdt
- Ad ogni tick: aggiorna trailing stop via `risk_manager.update_trailing_stop()`
- Check: close price <= SL (LONG) o >= SL (SHORT) → chiudi con "stop_loss"
- Check: close price >= TP (LONG) o <= TP (SHORT) → chiudi con "take_profit"
- Check: close price <= trailing (LONG) o >= trailing (SHORT) → chiudi con "trailing_stop"
- Alla chiusura: calcola PnL, `risk_manager.record_trade()`, log

**Paper vs Live:**
- Paper: log del trade, nessun ordine. `_position` gestita internamente.
- Live (futuro): chiama `exchange.create_order()`. Stessa logica, solo flag diverso.

**Graceful shutdown:**
- Registra handler per SIGINT/SIGTERM
- Setta `_running = False`
- Il loop esce dopo il tick corrente

**Sincronizzazione candele:**
- Calcola secondi mancanti alla prossima chiusura 5min: `300 - (time() % 300) + 5` (5s di buffer per propagazione)
- Sleep per quel tempo
- Non usa scheduling libraries, solo `time.sleep()`

### 2. SentimentCache (`src/sentiment/claude_sentiment.py`)

Aggiunto alla classe `ClaudeSentiment` esistente. Non una classe separata.

```python
class ClaudeSentiment:
    def __init__(self, ..., cooldown_minutes: int = SENTIMENT_COOLDOWN_MIN) -> None:
        self._cooldown_seconds = cooldown_minutes * 60
        self._last_result: SentimentResult | None = None
        self._last_call_time: float = 0.0

    def analyze(self, symbol: str = "BTC") -> SentimentResult:
        now = time.time()
        if self._last_result is not None and (now - self._last_call_time) < self._cooldown_seconds:
            logger.info("Sentiment cache hit (%.0fs remaining)", self._cooldown_seconds - (now - self._last_call_time))
            return self._last_result
        # ... chiamata API esistente ...
        self._last_result = result
        self._last_call_time = now
        return result
```

### 3. StatusWriter (`src/utils/status.py`)

Scrive `data/paper_status.json` ad ogni tick (overwrite).

```python
class StatusWriter:
    def __init__(self, output_path: str = "data/paper_status.json") -> None: ...
    def write(self, data: dict) -> None:  # scrive JSON atomicamente
```

**Contenuto del file:**
```json
{
  "timestamp": "2026-03-31T14:35:00Z",
  "mode": "paper",
  "position": {
    "side": "LONG",
    "entry_price": 50000.0,
    "entry_time": "2026-03-31T14:25:00Z",
    "stop_loss": 49850.0,
    "take_profit": 50200.0,
    "trailing_stop": 49950.0,
    "unrealized_pnl_pct": 0.15
  },
  "daily": {
    "trades": 3,
    "pnl": 12.50,
    "win_rate": 66.7
  },
  "last_signal": "LONG",
  "last_sentiment": {
    "score": 0.4,
    "confidence": 0.7,
    "recommendation": "BUY"
  }
}
```

Quando non c'e' posizione aperta, `position` e' `null`. Scrittura atomica: scrivi su file temporaneo, poi rinomina.

## New Settings

```python
SENTIMENT_COOLDOWN_MIN: int = 15  # minuti tra chiamate sentiment
```

## Testing

- **`StatusWriter`**: test che il JSON scritto sia valido e contenga tutte le chiavi attese
- **`SentimentCache`**: test cooldown (mock `time.time()`), test cache hit/miss
- **`TradingLoop._tick()`**: test con mock di exchange, verifica il flusso corretto senza loop infinito
- **`_check_open_position`**: test SL/TP/trailing hit per LONG e SHORT
- **`_open_position` / `_close_position`**: test che aggiornino correttamente lo stato
- Il loop infinito `run()` non viene testato — si verifica via esecuzione paper manuale

## Error Handling

- Se fetch OHLCV fallisce: log errore, skip tick, riprova al prossimo ciclo
- Se sentiment API fallisce: `ClaudeSentiment.analyze()` gia' restituisce `SentimentResult.neutral()`
- Se `StatusWriter` fallisce: log errore, non blocca il bot
- Tutti gli errori dentro `_tick()` sono catturati con try/except per non interrompere il loop

## Dependencies

Tutti componenti gia' implementati:
- `BinanceExchange` (exchange.py)
- `add_indicators`, `add_prev_indicators` (indicators/technical.py)
- `CombinedStrategy` (strategies/combined.py)
- `ClaudeSentiment`, `SentimentResult` (sentiment/claude_sentiment.py)
- `RiskManager` (risk/manager.py)

Nessuna nuova dipendenza esterna.
