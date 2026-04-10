# Design: Signal Quality Improvements

**Date:** 2026-04-10  
**Status:** Approved  
**Goal:** Aumentare il win rate dal ~7% verso il 40%+ riducendo i falsi segnali.

## Problema

Il backtest su 6 mesi (51.840 candele BTC/USDT 5min) ha mostrato:
- 96%+ di trade chiusi con stop-loss nella stessa candela di entry (durata media 1.6 candele)
- Win rate 6.8% — quasi tutti i segnali entrano in pieno momentum, non a inversione avvenuta

**Root cause:** `_mean_reversion_signal` emette LONG quando RSI ≤ 32, ma RSI 32 indica
momentum ribassista attivo, non esaurimento. Il prezzo continua spesso a scendere per 2–5
candele prima di rimbalzare. Il backtester entra alla open della candela successiva al segnale,
nel pieno del momentum, e lo SL viene toccato immediatamente.

## Soluzione

Due fix complementari:

### Fix 1 — RSI Turning Confirmation (in `combined.py`)

Aggiungere a ogni condizione di entry il requisito che il RSI stia già girando nella
direzione della trade:

- **LONG mean-rev cond A:** RSI[-1] ≤ 32 AND close ≤ BB_lower AND rsi[-1] > rsi[-2]
- **LONG mean-rev cond B:** RSI[-1] < 22 AND rsi[-1] > rsi[-2]
- **SHORT mean-rev cond A:** RSI[-1] ≥ 68 AND close ≥ BB_upper AND rsi[-1] < rsi[-2]
- **SHORT mean-rev cond B:** RSI[-1] > 78 AND rsi[-1] < rsi[-2]

Per il trend following, conferma che il DI dominante stia aumentando:
- **LONG trend:** condizioni esistenti AND di_plus[-1] > di_plus[-2]
- **SHORT trend:** condizioni esistenti AND di_minus[-1] > di_minus[-2]

**Implementazione:**
- `_mean_reversion_signal(self, df)` riceve `df` invece di `row`; legge `df.iloc[-1]` e `df.iloc[-2]`
- `_trend_following_signal(self, df)` analogamente
- Se `len(df) < 2` → entrambi i metodi ritornano `None` (nessun segnale, nessun crash)
- `generate_signal` passa `df` ai metodi privati (già disponibile)
- `add_prev_indicators` aggiunge `di_plus_prev` e `di_minus_prev`

### Fix 2 — HTF Filter nel Backtester (in `engine.py`)

`HTFFilter` è già implementata e usata in `main.py`. Il backtester la ignorava.

**Implementazione:**
- All'inizio di `run()`: resample 5min → 1h, pre-calcola `htf_data` per ogni ora completata
- Lookup: per la candela 5min a timestamp T, usa l'ora completata `T.floor("1h") - 1h`
- Applica `HTFFilter.allows_signal(signal, strategy_mode, htf_data)` prima di impostare `pending_signal`
- Fail-open se dati 1h insufficienti (coerente con `main.py`)
- Nessuna modifica all'API di `generate_signal`

## Architettura

```
combined.py
  generate_signal(df, sentiment)
    ├── _mean_reversion_signal(df)        ← ora riceve df, legge [-1] e [-2]
    └── _trend_following_signal(df)       ← ora riceve df, legge [-1] e [-2]

indicators/technical.py
  add_prev_indicators(df)
    ├── ema_fast_prev (esistente)
    ├── ema_slow_prev (esistente)
    ├── di_plus_prev  ← NUOVO
    └── di_minus_prev ← NUOVO

backtesting/engine.py
  run(df)
    ├── Precomputa htf_series: {timestamp_1h → htf_data}
    └── Per ogni segnale: htf_filter.allows_signal() prima di pending_signal
```

## Scope escluso

- Nessuna modifica all'API pubblica di `generate_signal`
- Nessun cambiamento a `main.py` (il filtro HTF lì è già attivo)
- Nessuna modifica ai parametri RSI/ADX in `settings.py`
- Nessun nuovo timeframe oltre 1h

## Testing

- `test_strategy.py`: aggiornare fixture per passare `df` con ≥ 2 righe; aggiungere test per
  il turning requirement (segnale NON emesso se RSI non gira, emesso se gira)
- `test_indicators.py`: aggiungere test per `di_plus_prev` e `di_minus_prev`
- `test_backtester.py`: invariato (HTF filter trasparente all'esterno del backtester)
- Run backtest post-implementazione per confrontare WR con baseline 6.8%
