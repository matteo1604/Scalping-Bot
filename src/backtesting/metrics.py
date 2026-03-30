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
