"""Test per il motore di backtesting."""

import pandas as pd
import numpy as np
import json
import pytest

from src.backtesting.engine import Backtester


@pytest.fixture
def trending_up_df() -> pd.DataFrame:
    """DataFrame con trend rialzista che genera almeno un crossover bullish."""
    np.random.seed(42)
    n = 100
    # Trend inizialmente piatto poi rialzista -> genera crossover EMA
    close = np.concatenate([
        np.full(30, 35000.0) + np.random.randn(30) * 10,
        35000.0 + np.cumsum(np.abs(np.random.randn(70)) * 15),
    ])
    df = pd.DataFrame({
        "open": close - np.random.rand(n) * 5,
        "high": close + np.random.rand(n) * 10,
        "low": close - np.random.rand(n) * 10,
        "close": close,
        "volume": np.random.rand(n) * 200 + 100,
    }, index=pd.date_range("2026-01-01", periods=n, freq="5min"))
    return df


@pytest.fixture
def flat_df() -> pd.DataFrame:
    """DataFrame piatto che non dovrebbe generare crossover."""
    n = 100
    close = np.full(n, 35000.0)
    df = pd.DataFrame({
        "open": close,
        "high": close + 1,
        "low": close - 1,
        "close": close,
        "volume": np.full(n, 100.0),
    }, index=pd.date_range("2026-01-01", periods=n, freq="5min"))
    return df


class TestBacktesterInit:
    """Test per inizializzazione Backtester."""

    def test_creates_with_defaults(self):
        bt = Backtester()
        assert bt.initial_capital > 0
        assert bt.stop_loss_pct > 0
        assert bt.take_profit_pct > 0

    def test_custom_params(self):
        bt = Backtester(initial_capital=5000.0, stop_loss_pct=1.0, take_profit_pct=2.0)
        assert bt.initial_capital == 5000.0
        assert bt.stop_loss_pct == 1.0
        assert bt.take_profit_pct == 2.0


class TestBacktesterRun:
    """Test per l'esecuzione del backtest."""

    def test_returns_result_dict(self, trending_up_df):
        bt = Backtester()
        result = bt.run(trending_up_df)
        assert isinstance(result, dict)
        assert "trades" in result
        assert "metrics" in result
        assert "equity_final" in result

    def test_metrics_keys(self, trending_up_df):
        bt = Backtester()
        result = bt.run(trending_up_df)
        metrics = result["metrics"]
        for key in ["win_rate", "profit_factor", "max_drawdown", "sharpe_ratio", "total_trades"]:
            assert key in metrics

    def test_no_trades_on_flat(self, flat_df):
        bt = Backtester()
        result = bt.run(flat_df)
        assert result["metrics"]["total_trades"] == 0

    def test_trades_have_required_fields(self, trending_up_df):
        bt = Backtester()
        result = bt.run(trending_up_df)
        if result["trades"]:
            trade = result["trades"][0]
            for key in ["entry_time", "exit_time", "side", "entry_price", "exit_price", "pnl"]:
                assert key in trade


class TestBacktesterSaveReport:
    """Test per il salvataggio del report."""

    def test_saves_json(self, trending_up_df, tmp_path):
        bt = Backtester()
        result = bt.run(trending_up_df)
        filepath = bt.save_report(result, output_dir=str(tmp_path))
        assert filepath.endswith(".json")
        with open(filepath) as f:
            data = json.load(f)
        assert "metrics" in data
        assert "trades" in data
