"""Generazione report e visualizzazione risultati backtest."""

import os
from datetime import datetime


def print_summary(result: dict) -> None:
    """Stampa un riepilogo del backtest su console.

    Args:
        result: Risultato restituito da Backtester.run().
    """
    m = result["metrics"]
    print("=" * 50)
    print("RISULTATI BACKTEST")
    print("=" * 50)
    print(f"Capitale iniziale:     {result['initial_capital']:>12,.2f} USDT")
    print(f"Capitale finale:       {result['equity_final']:>12,.2f} USDT")
    net = m.get("net_pnl", 0.0)
    print(f"PnL netto:             {net:>12,.2f} USDT")
    pct = net / result["initial_capital"] * 100 if result["initial_capital"] else 0
    print(f"Rendimento:            {pct:>11.2f}%")
    print("-" * 50)
    print(f"Trade totali:          {m['total_trades']:>12d}")
    print(f"Win rate:              {m['win_rate']:>11.1f}%")
    pf = m["profit_factor"]
    print(f"Profit factor:         {str(pf) if pf == 'inf' else f'{pf:>12.2f}'}")
    sr = m["sharpe_ratio"]
    print(f"Sharpe ratio:          {str(sr) if isinstance(sr, str) else f'{sr:>12.4f}'}")
    cr = m.get("calmar_ratio", 0)
    print(f"Calmar ratio:          {str(cr) if cr == 'inf' else f'{cr:>12.4f}'}")
    print(f"Max drawdown:          {m['max_drawdown']:>11.2f}%")
    print(f"Max perdite consec.:   {m['max_consecutive_losses']:>12d}")
    print(f"Durata media trade:    {m['avg_trade_duration']:>10.1f} candele")
    print("-" * 50)

    # Extended metrics (added in engine upgrade)
    if "gross_profit" in m:
        print(f"Profitto lordo:        {m['gross_profit']:>12,.2f} USDT")
        print(f"Perdita lorda:         {m['gross_loss']:>12,.2f} USDT")
        print(f"Win medio:             {m['avg_win']:>12,.2f} USDT")
        print(f"Loss medio:            {m['avg_loss']:>12,.2f} USDT")
        print("-" * 50)
    print("=" * 50)

    # Breakdown per strategia
    trades = result.get("trades", [])
    if trades:
        strategies: dict[str, dict] = {}
        for t in trades:
            s = t.get("strategy", "unknown")
            if s not in strategies:
                strategies[s] = {"count": 0, "pnl": 0.0, "wins": 0}
            strategies[s]["count"] += 1
            strategies[s]["pnl"] += t["pnl"]
            if t["pnl"] > 0:
                strategies[s]["wins"] += 1

        if len(strategies) > 1 or "unknown" not in strategies:
            print("\nBREAKDOWN PER STRATEGIA:")
            for s, data in strategies.items():
                wr = data["wins"] / data["count"] * 100 if data["count"] > 0 else 0
                print(f"  {s:20s}  {data['count']:>4d} trade | WR {wr:5.1f}% | PnL {data['pnl']:>+10.2f}")

        # Breakdown per exit reason
        reasons: dict[str, int] = {}
        for t in trades:
            r = t.get("exit_reason", "unknown")
            reasons[r] = reasons.get(r, 0) + 1

        print("\nBREAKDOWN PER EXIT REASON:")
        for r, count in sorted(reasons.items()):
            print(f"  {r:20s}  {count:>4d} trade")


def plot_equity_curve(
    equity_curve: list[float],
    initial_capital: float,
    output_dir: str = "data/backtest_results",
) -> str | None:
    """Genera un grafico PNG dell'equity curve.

    Richiede matplotlib. Se non installato, stampa un avviso e ritorna None.

    Args:
        equity_curve: Lista dei valori equity nel tempo.
        initial_capital: Capitale iniziale (linea di riferimento).
        output_dir: Directory dove salvare il PNG.

    Returns:
        Path del file PNG salvato, o None se matplotlib non è disponibile.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")  # backend non-interattivo
        import matplotlib.pyplot as plt
        import pandas as pd
    except ImportError:
        print(
            "matplotlib non installato — equity curve non generata.\n"
            "Installa con: pip install matplotlib"
        )
        return None

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(14, 8), gridspec_kw={"height_ratios": [3, 1]}
    )

    # Equity curve
    ax1.plot(equity_curve, linewidth=1.0, color="#2196F3")
    ax1.axhline(
        y=initial_capital, color="#666", linestyle="--",
        linewidth=0.8, label="Capitale iniziale",
    )
    ax1.set_title("Equity Curve", fontsize=14)
    ax1.set_ylabel("Capitale (USDT)")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Drawdown
    import pandas as pd
    series = pd.Series(equity_curve)
    peak = series.cummax()
    drawdown = (series - peak) / peak * 100
    ax2.fill_between(range(len(drawdown)), drawdown, 0, alpha=0.4, color="#F44336")
    ax2.set_title("Drawdown %", fontsize=12)
    ax2.set_ylabel("Drawdown %")
    ax2.set_xlabel("Candela")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()

    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(output_dir, f"equity_{ts}.png")
    plt.savefig(filepath, dpi=150)
    plt.close()

    return filepath
