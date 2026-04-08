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


def avg_trade_duration(trades: list[dict]) -> float:
    """Durata media dei trade in numero di candele.

    Args:
        trades: Lista di trade con chiave "duration_candles".

    Returns:
        Durata media in candele. 0.0 se nessun trade.
    """
    if not trades:
        return 0.0
    return float(np.mean([t["duration_candles"] for t in trades]))


def max_consecutive_losses(trades: list[dict]) -> int:
    """Massimo numero di perdite consecutive.

    Args:
        trades: Lista di trade con chiave "pnl".

    Returns:
        Massimo numero di trade in perdita consecutivi.
    """
    if not trades:
        return 0
    max_streak = 0
    current_streak = 0
    for t in trades:
        if t["pnl"] < 0:
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 0
    return max_streak


def net_pnl(trades: list[dict]) -> float:
    """PnL netto totale (già netto di commissioni dal backtester).

    Args:
        trades: Lista di trade con chiave "pnl".

    Returns:
        Somma di tutti i PnL.
    """
    if not trades:
        return 0.0
    return float(sum(t["pnl"] for t in trades))


def calmar_ratio(trades: list[dict], initial_capital: float = 1000.0) -> float:
    """Return totale percentuale / max drawdown percentuale.

    Args:
        trades: Lista di trade con chiave "pnl".
        initial_capital: Capitale iniziale.

    Returns:
        Calmar ratio. inf se max_drawdown == 0 e return > 0. 0.0 se nessun trade.
    """
    if not trades:
        return 0.0
    total_return_pct = (net_pnl(trades) / initial_capital) * 100.0
    if total_return_pct <= 0:
        return 0.0
    dd = max_drawdown(trades, initial_capital=initial_capital)
    if dd == 0.0:
        return float("inf")
    return total_return_pct / dd
