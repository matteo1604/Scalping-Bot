"""Scarica dati storici OHLCV da Binance e li salva in CSV.

Uso:
    python scripts/download_data.py --months 6
    python scripts/download_data.py --start 2025-10-01 --end 2026-03-31

Non richiede API key (dati pubblici).
Paginazione automatica: Binance restituisce max 1000 candele per request.
"""

import argparse
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import ccxt
import pandas as pd

SYMBOL = "BTC/USDT"
TIMEFRAME = "5m"
CANDLES_PER_REQUEST = 1000
RATE_LIMIT_SLEEP = 0.5  # secondi tra request
OUTPUT_DIR = "data/ohlcv"


def download_ohlcv(
    symbol: str,
    timeframe: str,
    start_dt: datetime,
    end_dt: datetime,
) -> pd.DataFrame:
    """Scarica OHLCV paginando automaticamente.

    Args:
        symbol: Coppia di trading.
        timeframe: Intervallo candele.
        start_dt: Data inizio (UTC).
        end_dt: Data fine (UTC).

    Returns:
        DataFrame completo con tutte le candele nel range.
    """
    exchange = ccxt.binance({"enableRateLimit": True})
    all_candles: list = []
    since_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)

    print(f"Download {symbol} {timeframe} dal {start_dt.date()} al {end_dt.date()}...")

    while since_ms < end_ms:
        candles = exchange.fetch_ohlcv(
            symbol,
            timeframe,
            since=since_ms,
            limit=CANDLES_PER_REQUEST,
        )
        if not candles:
            break

        all_candles.extend(candles)
        since_ms = candles[-1][0] + 1  # +1ms per evitare duplicati
        last_ts = datetime.fromtimestamp(candles[-1][0] / 1000, tz=timezone.utc)
        print(f"  Scaricate {len(all_candles)} candele (fino a {last_ts.date()})...")
        time.sleep(RATE_LIMIT_SLEEP)

    if not all_candles:
        print("Nessuna candela scaricata.")
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    df = pd.DataFrame(
        all_candles,
        columns=["timestamp", "open", "high", "low", "close", "volume"],
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df.set_index("timestamp", inplace=True)
    df = df[~df.index.duplicated(keep="first")]
    df = df[df.index <= pd.Timestamp(end_dt)]

    return df.astype(float)


def main() -> None:
    """Entry point per lo script di download."""
    parser = argparse.ArgumentParser(description="Download dati storici OHLCV")
    parser.add_argument(
        "--months", type=int, default=6,
        help="Mesi di dati da scaricare (default: 6)",
    )
    parser.add_argument(
        "--start", type=str,
        help="Data inizio (YYYY-MM-DD), override --months",
    )
    parser.add_argument(
        "--end", type=str,
        help="Data fine (YYYY-MM-DD), default: oggi",
    )
    parser.add_argument("--symbol", type=str, default=SYMBOL)
    parser.add_argument("--timeframe", type=str, default=TIMEFRAME)
    args = parser.parse_args()

    end_dt = datetime.now(timezone.utc)
    if args.end:
        end_dt = datetime.strptime(args.end, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    if args.start:
        start_dt = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        start_dt = end_dt - timedelta(days=args.months * 30)

    df = download_ohlcv(args.symbol, args.timeframe, start_dt, end_dt)

    if df.empty:
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    symbol_safe = args.symbol.replace("/", "_")
    filename = f"{symbol_safe}_{args.timeframe}_{start_dt.date()}_{end_dt.date()}.csv"
    filepath = os.path.join(OUTPUT_DIR, filename)
    df.to_csv(filepath)
    print(f"\nSalvate {len(df)} candele in {filepath}")
    print(f"Range: {df.index[0]} — {df.index[-1]}")


if __name__ == "__main__":
    main()
