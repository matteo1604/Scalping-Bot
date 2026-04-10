"""Esegue un backtest su dati storici CSV.

Uso:
    python scripts/run_backtest.py --data data/ohlcv/BTC_USDT_5m_2025-10-01_2026-04-01.csv
    python scripts/run_backtest.py --data "data/ohlcv/BTC_USDT_5m_*.csv" --capital 5000

Output: report JSON + equity curve PNG in data/backtest_results/
"""

import argparse
import glob
import os
import sys

import pandas as pd

# Aggiungi la root del progetto al path per import relativi
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.backtesting.engine import Backtester
from src.backtesting.report import plot_equity_curve, print_summary


def load_data(pattern: str) -> pd.DataFrame:
    """Carica uno o più CSV e li concatena ordinandoli per timestamp.

    Args:
        pattern: Path esatto o glob pattern (es. "data/ohlcv/*.csv").

    Returns:
        DataFrame OHLCV concatenato e de-duplicato.
    """
    files = sorted(glob.glob(pattern))
    if not files:
        print(f"Nessun file trovato: {pattern}")
        sys.exit(1)

    dfs = []
    for f in files:
        df = pd.read_csv(f, index_col=0, parse_dates=True)
        dfs.append(df)
        print(f"  Caricato: {f} ({len(df)} candele)")

    combined = pd.concat(dfs).sort_index()
    combined = combined[~combined.index.duplicated(keep="first")]
    return combined


def main() -> None:
    """Entry point per il CLI runner del backtest."""
    parser = argparse.ArgumentParser(description="Esegui backtest su dati storici")
    parser.add_argument(
        "--data", required=True,
        help="Path o glob pattern del CSV OHLCV (usa virgolette per i glob)",
    )
    parser.add_argument(
        "--capital", type=float, default=10_000.0,
        help="Capitale iniziale in USDT (default: 10000)",
    )
    parser.add_argument(
        "--commission", type=float, default=0.1,
        help="Commissione %% per lato (default: 0.1)",
    )
    parser.add_argument(
        "--spread", type=float, default=0.01,
        help="Spread simulato %% (default: 0.01)",
    )
    parser.add_argument(
        "--output", type=str, default="data/backtest_results",
        help="Directory output per report e chart",
    )
    args = parser.parse_args()

    print("=== BACKTEST ===")
    df = load_data(args.data)
    print(f"Totale: {len(df)} candele | {df.index[0]} — {df.index[-1]}")
    print()

    bt = Backtester(
        initial_capital=args.capital,
        commission_pct=args.commission,
        spread_pct=args.spread,
    )

    result = bt.run(df)

    print_summary(result)

    report_path = bt.save_report(result, output_dir=args.output)

    chart_path = plot_equity_curve(
        result["equity_curve"],
        initial_capital=args.capital,
        output_dir=args.output,
    )

    if chart_path:
        print(f"\nEquity curve: {chart_path}")
    print(f"Report JSON:  {report_path}")


if __name__ == "__main__":
    main()
