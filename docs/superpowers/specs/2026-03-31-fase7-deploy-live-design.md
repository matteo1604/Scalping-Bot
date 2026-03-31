# Fase 7 — Deploy Live Design Spec

## Obiettivo

Rendere il bot operativo in modalita' live con capitale reale minimo su Binance spot, con monitoraggio via Slack, kill switch file-based, e pre-flight checks di sicurezza.

## Vincoli

- **Solo spot** — niente futures/margin. I segnali SHORT vengono ignorati in live.
- **Capitale minimo** — ~50 USDT allocati, ordini da ~10 USDT.
- **Deploy locale** — il bot gira sul PC dell'utente. Migrazione VPS futura.
- **Slack opzionale** — se il webhook non e' configurato, il bot funziona comunque (solo log).

## Architettura

### File da modificare

- `config/settings.py` — 3 nuove settings
- `.env.example` — aggiunta `SLACK_WEBHOOK_URL`
- `src/main.py` — live execution, kill switch, pre-flight checks, integrazione notifier

### File da creare

- `src/utils/notifier.py` — `SlackNotifier`
- `tests/test_notifier.py` — test per SlackNotifier
- `tests/test_live_execution.py` — test per logica live (ordini, pre-flight, kill switch)

---

## Componente 1: Settings

Aggiunte a `config/settings.py`:

```python
SLACK_WEBHOOK_URL: str = os.getenv("SLACK_WEBHOOK_URL", "")
LIVE_CAPITAL_USDT: float = 50.0
KILL_SWITCH_PATH: str = "data/kill.flag"
```

Aggiunta a `.env.example`:

```
SLACK_WEBHOOK_URL=
```

`LIVE_CAPITAL_USDT` sostituisce il placeholder `TRADE_AMOUNT_USDT * 100` attualmente usato nel TradingLoop.

---

## Componente 2: SlackNotifier

Nuovo modulo `src/utils/notifier.py`.

### Classe `SlackNotifier`

- `__init__(webhook_url: str)` — salva URL. Se vuoto, disabilita notifiche silenziosamente.
- `notify(message: str, level: str = "info") -> None` — POST HTTP al webhook Slack. Level: `info`, `warning`, `error`. Non blocca il bot se la chiamata fallisce (catch + log).
- Usa `urllib.request` dalla stdlib — nessuna dipendenza aggiuntiva.

### Messaggi inviati

| Evento | Livello | Esempio |
|--------|---------|---------|
| Avvio bot | info | `"Bot avviato in modalita' live"` |
| Shutdown bot | info | `"Bot fermato"` |
| Apertura posizione | info | `"APERTA LONG @ 50000.00 \| SL=49850 TP=50200 \| Size=10.50 USDT"` |
| Chiusura posizione | info | `"CHIUSA LONG @ 50100.00 \| Reason=take_profit \| PnL=+0.20% (+0.02 USDT)"` |
| Kill switch | warning | `"KILL SWITCH attivato — bot fermato"` |
| Daily limit | warning | `"Daily loss limit raggiunto — trading sospeso"` |
| Errore critico | error | `"ERRORE: ordine live fallito"` |
| Errore fetch | error | `"ERRORE: fetch OHLCV fallito"` |

---

## Componente 3: Kill Switch

Logica in `TradingLoop._tick()`, come **primo check** prima di qualsiasi operazione:

1. Controlla `os.path.exists(KILL_SWITCH_PATH)`
2. Se esiste: log + notifica Slack + `self._running = False`
3. Se c'e' una posizione aperta: **NON la chiude automaticamente**. Logga warning + notifica Slack con i dettagli della posizione. L'utente gestisce manualmente.
4. Per riattivare: cancellare `data/kill.flag` e riavviare il bot.

Implementato come metodo `_check_kill_switch() -> bool`.

---

## Componente 4: Live Execution

### `_open_position` (modifiche)

- **Paper mode:** comportamento invariato (posizione in memoria).
- **Live mode:**
  1. `exchange.get_balance("USDT")` per capitale reale
  2. Calcola size via `RiskManager.calculate_position_size()`
  3. Segnali SHORT vengono ignorati (log + skip) — spot only
  4. `exchange.create_order(SYMBOL, "buy", amount)` per LONG
  5. Se ordine OK: salva posizione in memoria + notifica Slack
  6. Se ordine fallisce: log + notifica Slack livello `error`, non salva posizione

### `_close_position` (modifiche)

- **Paper mode:** comportamento invariato.
- **Live mode:**
  1. Piazza ordine inverso: `exchange.create_order(SYMBOL, "sell", amount)` per chiudere LONG
  2. Se ordine OK: log PnL + notifica Slack + cancella posizione
  3. Se ordine fallisce: log + notifica Slack `error`, **NON cancella la posizione** (ritenta al prossimo tick)

### Capitale

- Paper: usa `LIVE_CAPITAL_USDT` come simulazione
- Live: usa `exchange.get_balance("USDT")` — saldo reale

### Conversione USDT -> BTC

Per piazzare ordini su spot BTC/USDT, serve convertire `size_usdt` in quantita' BTC:
`amount_btc = size_usdt / entry_price`

---

## Componente 5: Pre-flight Checks

Metodo `_preflight_checks() -> bool` chiamato da `run()` prima del loop. Solo in `mode="live"`.

Checks in ordine:

1. **API keys** — `BINANCE_API_KEY` e `BINANCE_API_SECRET` non vuoti
2. **Connessione exchange** — `exchange.get_balance("USDT")` funziona
3. **Balance minimo** — saldo >= `MIN_ORDER_SIZE_USDT` (10 USDT)
4. **Kill switch** — `data/kill.flag` non esiste
5. **Slack webhook** — se configurato, invia messaggio di test. Se non configurato, log warning ma procede

Se qualsiasi check (tranne Slack) fallisce: log errore, bot non parte (`return False`).

---

## Flusso completo

```
Avvio → mode == "live"? → Pre-flight checks → [FAIL → log + exit]
                                              → [OK → Slack "Bot avviato"]
Loop:
  → _check_kill_switch() → [kill.flag? → Slack "Kill switch" → exit]
  → _wait_for_candle()
  → _tick():
    → daily reset check
    → fetch OHLCV + indicators
    → Posizione aperta?
      → SI: update trailing → check SL/TP/trailing → chiudi con ordine reale → Slack PnL
      → NO: genera segnale
        → SHORT in live? → skip (log "SHORT ignorato su spot")
        → LONG? → sentiment → balance reale → ordine reale → Slack
    → write status JSON
```

## Cosa NON e' in scope

- Dashboard web (futuro, quando su VPS)
- Futures/margin trading (solo spot)
- Deploy automatizzato su VPS
- Alerting via email/Telegram
