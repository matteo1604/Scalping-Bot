#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Script diagnostico: verifica che la strategia generi segnali su dati reali.

Uso: python scripts/diagnose.py

Non richiede API key Binance (OHLCV pubblico).
"""

import sys
import os

# Aggiungi la root del progetto al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import ccxt
import pandas as pd

from src.indicators.technical import add_indicators, add_prev_indicators
from src.indicators.htf_filter import HTFFilter
from src.strategies.combined import CombinedStrategy
from config.settings import (
    ADX_TREND_THRESHOLD,
    HTF_CANDLES,
    RSI_ENTRY_OVERSOLD,
    RSI_ENTRY_OVERBOUGHT,
    RSI_EXTREME_OVERSOLD,
    RSI_EXTREME_OVERBOUGHT,
    VOLUME_FILTER_RATIO,
)

SYMBOL = "BTC/USDT"
TIMEFRAME = "5m"
HTF_TIMEFRAME = "1h"
N_CANDLES = 500


def fetch_ohlcv(symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    """Scarica OHLCV da Binance senza API key (dati pubblici)."""
    exchange = ccxt.binance({"enableRateLimit": True})
    raw = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df.set_index("timestamp")
    return df.astype(float)


def main() -> None:
    print("=== DIAGNOSTICA BOT ===")
    print(f"Fetch {N_CANDLES} candele {SYMBOL} {TIMEFRAME} da Binance...")

    try:
        raw_df = fetch_ohlcv(SYMBOL, TIMEFRAME, N_CANDLES)
    except Exception as e:
        print(f"ERRORE fetch dati: {e}")
        sys.exit(1)

    print(f"Fetch {HTF_CANDLES} candele {SYMBOL} {HTF_TIMEFRAME} per HTF filter...")
    try:
        df_1h = fetch_ohlcv(SYMBOL, HTF_TIMEFRAME, HTF_CANDLES)
        htf_filter = HTFFilter()
        htf_data = htf_filter.compute_indicators(df_1h)
        rsi_str = f"{htf_data['rsi_1h']:.1f}" if htf_data["rsi_1h"] is not None else "N/A"
        print(f"HTF 1h: RSI={rsi_str}, trend={htf_data['trend_1h']}")
    except Exception as e:
        print(f"ATTENZIONE: Fetch 1h fallito ({e}) — HTF filter disabilitato")
        htf_filter = HTFFilter()
        htf_data = {"rsi_1h": None, "trend_1h": "NEUTRAL"}

    print(f"Candele scaricate: {len(raw_df)}")

    # Calcola indicatori
    df = add_indicators(raw_df)
    df = add_prev_indicators(df)
    df = df.dropna()

    n_valid = len(df)
    print(f"Candele valide (no NaN): {n_valid}")
    if n_valid == 0:
        print("ERRORE: nessuna candela valida dopo dropna!")
        sys.exit(1)

    print()
    print("Distribuzione indicatori:")

    rsi = df["rsi"]
    adx = df["adx"]
    close = df["close"]
    bb_upper = df["bb_upper"]
    bb_lower = df["bb_lower"]
    bb_width_pct = ((bb_upper - bb_lower) / close) * 100

    print(f"  RSI:      min={rsi.min():.1f}, max={rsi.max():.1f}, mean={rsi.mean():.1f}")
    print(f"  ADX:      min={adx.min():.1f}, max={adx.max():.1f}, mean={adx.mean():.1f}")
    print(f"  BB width: min={bb_width_pct.min():.2f}%, max={bb_width_pct.max():.2f}%, mean={bb_width_pct.mean():.2f}%")

    print()
    print("Filtri (soglie attuali in settings.py):")

    adx_ok = (adx <= ADX_TREND_THRESHOLD).sum()
    rsi_oversold = (rsi <= RSI_ENTRY_OVERSOLD).sum()
    rsi_overbought = (rsi >= RSI_ENTRY_OVERBOUGHT).sum()
    rsi_extreme_os = (rsi < RSI_EXTREME_OVERSOLD).sum()
    rsi_extreme_ob = (rsi > RSI_EXTREME_OVERBOUGHT).sum()
    close_at_lower = (close <= bb_lower).sum()
    close_at_upper = (close >= bb_upper).sum()
    volume_ok = (df["volume"] >= df["volume_ma"] * VOLUME_FILTER_RATIO).sum()

    def pct(n: int) -> str:
        return f"{n}/{n_valid} ({n / n_valid * 100:.1f}%)"

    print(f"  ADX <= {ADX_TREND_THRESHOLD} (range/sideways):          {pct(adx_ok)}")
    print(f"  RSI <= {RSI_ENTRY_OVERSOLD} (cond A oversold):          {pct(rsi_oversold)}")
    print(f"  RSI >= {RSI_ENTRY_OVERBOUGHT} (cond A overbought):        {pct(rsi_overbought)}")
    print(f"  RSI <  {RSI_EXTREME_OVERSOLD} (cond B extreme oversold):  {pct(rsi_extreme_os)}")
    print(f"  RSI >  {RSI_EXTREME_OVERBOUGHT} (cond B extreme overbought): {pct(rsi_extreme_ob)}")
    print(f"  Close <= BB lower:                   {pct(close_at_lower)}")
    print(f"  Close >= BB upper:                   {pct(close_at_upper)}")
    print(f"  Volume >= volume_ma * {VOLUME_FILTER_RATIO}:          {pct(volume_ok)}")

    # Simula segnali su ogni candela, separati per modalita'
    strategy = CombinedStrategy()
    mr_long = mr_short = tf_long = tf_short = n_none = 0
    htf_blocked = 0

    for i in range(1, n_valid):
        window = df.iloc[: i + 1]
        row = window.iloc[-1]
        sig = strategy.generate_signal(window)
        adx_val = row["adx"]
        in_trend = adx_val > ADX_TREND_THRESHOLD
        if sig == "LONG":
            if in_trend:
                tf_long += 1
            else:
                mr_long += 1
        elif sig == "SHORT":
            if in_trend:
                tf_short += 1
            else:
                mr_short += 1
        else:
            n_none += 1

        # Verifica filtro HTF
        if sig is not None:
            strategy_mode = "trend" if in_trend else "reversion"
            if not htf_filter.allows_signal(sig, strategy_mode, htf_data):
                htf_blocked += 1

    total_evaluated = n_valid - 1
    total_mr = mr_long + mr_short
    total_tf = tf_long + tf_short
    total_signals = total_mr + total_tf
    total_after_htf = total_signals - htf_blocked
    segnali_per_giorno = total_signals / max(total_evaluated / 288, 1)
    segnali_per_giorno_htf = total_after_htf / max(total_evaluated / 288, 1)

    print()
    print(f"Segnali su {total_evaluated} candele valutate:")
    print(f"  Mean Reversion (ADX <= {ADX_TREND_THRESHOLD}):  LONG={mr_long}  SHORT={mr_short}  tot={total_mr}")
    print(f"  Trend Following (ADX > {ADX_TREND_THRESHOLD}):   LONG={tf_long}  SHORT={tf_short}  tot={total_tf}")
    print(f"  Totale pre-HTF:  {total_signals}   None: {n_none}")

    print()
    if total_signals > 0:
        htf_pct = htf_blocked / total_signals * 100
        print(f"Filtro HTF 1h:")
        print(f"  Segnali pre-HTF:         {total_signals} (~{segnali_per_giorno:.1f}/giorno)")
        print(f"  Segnali bloccati da HTF: {htf_blocked} ({htf_pct:.0f}%)")
        print(f"  Segnali finali:          {total_after_htf} (~{segnali_per_giorno_htf:.1f}/giorno)")

    print()
    if total_after_htf == 0:
        print("!! SEGNALI = 0 -- IL BOT NON FARA' TRADE.")
        print("   Verifica i filtri sopra: quale percentuale e' troppo bassa?")
        print("   ADX basso + RSI estremo + BB + volume devono coincidere.")
    elif total_after_htf < 5:
        print(f"[SCARSI] {total_after_htf} segnali (~{segnali_per_giorno_htf:.1f}/giorno). "
              f"Valuta di rilassare le soglie.")
    elif total_after_htf > 50:
        print(f"[TROPPI] {total_after_htf} segnali (~{segnali_per_giorno_htf:.1f}/giorno). "
              f"Valuta di stringere le soglie.")
    else:
        print(f"[OK] {total_after_htf} segnali su {total_evaluated} candele "
              f"(~{segnali_per_giorno_htf:.1f}/giorno) -- PRONTI PER PAPER TRADING")


if __name__ == "__main__":
    main()
