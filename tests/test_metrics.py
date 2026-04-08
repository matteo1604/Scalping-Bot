"""Test per le metriche di backtesting."""

import pytest
from src.backtesting.metrics import (
    win_rate,
    profit_factor,
    max_drawdown,
    sharpe_ratio,
    avg_trade_duration,
    max_consecutive_losses,
    net_pnl,
    calmar_ratio,
)


class TestWinRate:
    """Test per win_rate."""

    def test_all_winners(self):
        trades = [{"pnl": 10.0}, {"pnl": 20.0}, {"pnl": 5.0}]
        assert win_rate(trades) == 100.0

    def test_all_losers(self):
        trades = [{"pnl": -10.0}, {"pnl": -20.0}]
        assert win_rate(trades) == 0.0

    def test_mixed(self):
        trades = [{"pnl": 10.0}, {"pnl": -5.0}, {"pnl": 20.0}, {"pnl": -3.0}]
        assert win_rate(trades) == 50.0

    def test_empty(self):
        assert win_rate([]) == 0.0


class TestProfitFactor:
    """Test per profit_factor."""

    def test_profitable(self):
        trades = [{"pnl": 30.0}, {"pnl": -10.0}]
        assert profit_factor(trades) == 3.0

    def test_no_losses(self):
        trades = [{"pnl": 10.0}, {"pnl": 20.0}]
        assert profit_factor(trades) == float("inf")

    def test_no_wins(self):
        trades = [{"pnl": -10.0}, {"pnl": -20.0}]
        assert profit_factor(trades) == 0.0

    def test_empty(self):
        assert profit_factor([]) == 0.0


class TestMaxDrawdown:
    """Test per max_drawdown."""

    def test_simple_drawdown(self):
        # Equity: 100 -> 110 -> 90 -> 120
        trades = [{"pnl": 10.0}, {"pnl": -20.0}, {"pnl": 30.0}]
        dd = max_drawdown(trades, initial_capital=100.0)
        # Peak = 110, trough = 90, drawdown = 20/110 = 18.18%
        assert abs(dd - 18.18) < 0.1

    def test_no_drawdown(self):
        trades = [{"pnl": 10.0}, {"pnl": 20.0}]
        assert max_drawdown(trades, initial_capital=100.0) == 0.0

    def test_empty(self):
        assert max_drawdown([], initial_capital=100.0) == 0.0


class TestSharpeRatio:
    """Test per sharpe_ratio."""

    def test_positive_sharpe(self):
        trades = [{"pnl": 10.0}, {"pnl": 12.0}, {"pnl": 8.0}, {"pnl": 11.0}]
        sr = sharpe_ratio(trades)
        assert sr > 0

    def test_all_same_returns(self):
        trades = [{"pnl": 10.0}, {"pnl": 10.0}, {"pnl": 10.0}]
        sr = sharpe_ratio(trades)
        assert sr == float("inf")

    def test_empty(self):
        assert sharpe_ratio([]) == 0.0


class TestAvgTradeDuration:
    """Test per avg_trade_duration."""

    def test_basic_average(self):
        trades = [
            {"duration_candles": 3},
            {"duration_candles": 7},
            {"duration_candles": 5},
        ]
        assert avg_trade_duration(trades) == pytest.approx(5.0)

    def test_single_trade(self):
        trades = [{"duration_candles": 4}]
        assert avg_trade_duration(trades) == 4.0

    def test_empty_returns_zero(self):
        assert avg_trade_duration([]) == 0.0


class TestMaxConsecutiveLosses:
    """Test per max_consecutive_losses."""

    def test_basic_streak(self):
        trades = [
            {"pnl": 5.0}, {"pnl": -3.0}, {"pnl": -2.0}, {"pnl": -1.0},
            {"pnl": 4.0}, {"pnl": -1.0},
        ]
        assert max_consecutive_losses(trades) == 3

    def test_all_losses(self):
        trades = [{"pnl": -1.0}, {"pnl": -2.0}, {"pnl": -3.0}]
        assert max_consecutive_losses(trades) == 3

    def test_no_losses(self):
        trades = [{"pnl": 1.0}, {"pnl": 2.0}]
        assert max_consecutive_losses(trades) == 0

    def test_empty(self):
        assert max_consecutive_losses([]) == 0


class TestNetPnl:
    """Test per net_pnl."""

    def test_sum_of_pnls(self):
        trades = [{"pnl": 10.0}, {"pnl": -3.0}, {"pnl": 5.0}]
        assert net_pnl(trades) == pytest.approx(12.0)

    def test_all_negative(self):
        trades = [{"pnl": -5.0}, {"pnl": -3.0}]
        assert net_pnl(trades) == pytest.approx(-8.0)

    def test_empty(self):
        assert net_pnl([]) == 0.0


class TestCalmarRatio:
    """Test per calmar_ratio."""

    def test_profitable_low_drawdown(self):
        # Return = 100%, drawdown = 10%  → calmar = 10
        trades = [{"pnl": 1000.0}, {"pnl": -100.0}, {"pnl": 1000.0}]
        ratio = calmar_ratio(trades, initial_capital=1000.0)
        assert ratio > 1.0

    def test_zero_drawdown_returns_inf(self):
        trades = [{"pnl": 100.0}, {"pnl": 200.0}]
        assert calmar_ratio(trades, initial_capital=1000.0) == float("inf")

    def test_empty(self):
        assert calmar_ratio([]) == 0.0

    def test_no_profit(self):
        trades = [{"pnl": -100.0}]
        assert calmar_ratio(trades, initial_capital=1000.0) == 0.0
