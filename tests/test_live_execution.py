"""Test per la logica live del TradingLoop."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from src.main import TradingLoop


@pytest.fixture
def live_loop(tmp_path):
    """TradingLoop in mode live con componenti mockati."""
    status_path = str(tmp_path / "status.json")
    kill_path = str(tmp_path / "kill.flag")
    with patch("src.main.BinanceExchange") as mock_ex_cls:
        with patch("src.main.ClaudeSentiment"):
            with patch("src.main.SlackNotifier"):
                tl = TradingLoop(
                    mode="live",
                    status_path=status_path,
                    kill_switch_path=kill_path,
                )
    tl._exchange = mock_ex_cls.return_value
    return tl, tmp_path, kill_path


@pytest.fixture
def paper_loop(tmp_path):
    """TradingLoop in mode paper con componenti mockati."""
    status_path = str(tmp_path / "status.json")
    with patch("src.main.BinanceExchange"):
        with patch("src.main.ClaudeSentiment"):
            with patch("src.main.SlackNotifier"):
                tl = TradingLoop(mode="paper", status_path=status_path)
    return tl


class TestKillSwitch:
    """Test per il kill switch file-based."""

    def test_kill_switch_stops_bot(self, live_loop):
        """Kill switch file presente deve fermare il bot."""
        tl, tmp_path, kill_path = live_loop
        tl._running = True
        with open(kill_path, "w") as f:
            f.write("kill")

        result = tl._check_kill_switch()
        assert result is True
        assert tl._running is False

    def test_no_kill_switch_continues(self, live_loop):
        """Nessun kill switch file: il bot continua."""
        tl, tmp_path, kill_path = live_loop
        tl._running = True

        result = tl._check_kill_switch()
        assert result is False
        assert tl._running is True

    def test_kill_switch_notifies_slack(self, live_loop):
        """Kill switch deve inviare notifica Slack."""
        tl, tmp_path, kill_path = live_loop
        tl._running = True
        with open(kill_path, "w") as f:
            f.write("kill")

        tl._check_kill_switch()
        tl._notifier.notify.assert_called()

    def test_kill_switch_warns_open_position(self, live_loop):
        """Kill switch con posizione aperta: posizione NON chiusa."""
        tl, tmp_path, kill_path = live_loop
        tl._running = True
        tl._position = {
            "side": "LONG", "entry_price": 50000.0, "entry_time": "t",
            "stop_loss": 49850.0, "take_profit": 50200.0,
            "trailing_stop": 49900.0, "size_usdt": 100.0,
        }
        with open(kill_path, "w") as f:
            f.write("kill")

        tl._check_kill_switch()
        assert tl._position is not None
        assert tl._running is False


class TestPreflightChecks:
    """Test per i pre-flight checks."""

    def test_preflight_fails_empty_api_key(self, tmp_path):
        """Deve fallire se API key vuota."""
        status_path = str(tmp_path / "status.json")
        with patch("src.main.BinanceExchange"):
            with patch("src.main.ClaudeSentiment"):
                with patch("src.main.SlackNotifier"):
                    with patch("src.main.BINANCE_API_KEY", ""):
                        tl = TradingLoop(mode="live", status_path=status_path)
                        assert tl._preflight_checks() is False

    def test_preflight_fails_low_balance(self, tmp_path):
        """Deve fallire se balance sotto il minimo."""
        status_path = str(tmp_path / "status.json")
        with patch("src.main.BinanceExchange") as mock_ex_cls:
            with patch("src.main.ClaudeSentiment"):
                with patch("src.main.SlackNotifier"):
                    with patch("src.main.BINANCE_API_KEY", "test-key"):
                        with patch("src.main.BINANCE_API_SECRET", "test-secret"):
                            tl = TradingLoop(mode="live", status_path=status_path)
        tl._exchange.get_balance.return_value = 5.0
        assert tl._preflight_checks() is False

    def test_preflight_fails_kill_switch_exists(self, tmp_path):
        """Deve fallire se kill switch gia' presente."""
        status_path = str(tmp_path / "status.json")
        kill_path = str(tmp_path / "kill.flag")
        with open(kill_path, "w") as f:
            f.write("kill")
        with patch("src.main.BinanceExchange") as mock_ex_cls:
            with patch("src.main.ClaudeSentiment"):
                with patch("src.main.SlackNotifier"):
                    with patch("src.main.BINANCE_API_KEY", "test-key"):
                        with patch("src.main.BINANCE_API_SECRET", "test-secret"):
                            tl = TradingLoop(
                                mode="live",
                                status_path=status_path,
                                kill_switch_path=kill_path,
                            )
        tl._exchange.get_balance.return_value = 100.0
        assert tl._preflight_checks() is False

    def test_preflight_passes_all_ok(self, tmp_path):
        """Deve passare se tutto OK."""
        status_path = str(tmp_path / "status.json")
        kill_path = str(tmp_path / "kill.flag")
        with patch("src.main.BinanceExchange") as mock_ex_cls:
            with patch("src.main.ClaudeSentiment"):
                with patch("src.main.SlackNotifier"):
                    with patch("src.main.BINANCE_API_KEY", "test-key"):
                        with patch("src.main.BINANCE_API_SECRET", "test-secret"):
                            tl = TradingLoop(
                                mode="live",
                                status_path=status_path,
                                kill_switch_path=kill_path,
                            )
        tl._exchange.get_balance.return_value = 100.0
        with patch("src.main.BINANCE_API_KEY", "test-key"):
            with patch("src.main.BINANCE_API_SECRET", "test-secret"):
                assert tl._preflight_checks() is True

    def test_preflight_skipped_in_paper(self, paper_loop):
        """In paper mode pre-flight restituisce True."""
        assert paper_loop._preflight_checks() is True


class TestLiveExecution:
    """Test per ordini live."""

    def test_open_position_live_calls_create_order(self, live_loop):
        """In live mode, _open_position deve chiamare exchange.create_order."""
        from src.sentiment.claude_sentiment import SentimentResult
        tl, tmp_path, kill_path = live_loop
        tl._exchange.get_balance.return_value = 100.0
        tl._exchange.create_order.return_value = {"id": "123", "status": "filled"}

        sentiment = SentimentResult(
            sentiment_score=0.5, confidence=0.8,
            top_events=[], recommendation="BUY",
        )
        row = MagicMock()
        row.__getitem__ = lambda s, k: {"close": 50000.0}[k]
        row.name = "2026-03-31T14:25:00"

        tl._open_position("LONG", row, sentiment, atr=100.0)

        tl._exchange.create_order.assert_called_once()

    def test_open_position_short_skipped_in_live(self, live_loop):
        """In live mode, segnali SHORT devono essere ignorati (spot only)."""
        from src.sentiment.claude_sentiment import SentimentResult
        tl, tmp_path, kill_path = live_loop

        sentiment = SentimentResult(
            sentiment_score=-0.5, confidence=0.8,
            top_events=[], recommendation="SELL",
        )
        row = MagicMock()
        row.__getitem__ = lambda s, k: {"close": 50000.0}[k]
        row.name = "2026-03-31T14:25:00"

        tl._open_position("SHORT", row, sentiment, atr=100.0)

        tl._exchange.create_order.assert_not_called()
        assert tl._position is None

    def test_close_position_live_calls_sell_order(self, live_loop):
        """In live mode, _close_position deve piazzare ordine sell."""
        tl, tmp_path, kill_path = live_loop
        tl._exchange.create_order.return_value = {"id": "456", "status": "filled"}
        tl._position = {
            "side": "LONG", "entry_price": 50000.0, "entry_time": "t",
            "stop_loss": 49850.0, "take_profit": 50200.0,
            "trailing_stop": 49900.0, "size_usdt": 100.0,
        }
        row = MagicMock()
        row.__getitem__ = lambda s, k: {"close": 50100.0}[k]
        row.name = "2026-03-31T14:30:00"

        tl._close_position(row, "take_profit")

        tl._exchange.create_order.assert_called_once()
        assert tl._position is None

    def test_close_position_live_keeps_position_on_order_failure(self, live_loop):
        """Se l'ordine di chiusura fallisce, la posizione resta aperta."""
        tl, tmp_path, kill_path = live_loop
        tl._exchange.create_order.side_effect = Exception("Order failed")
        tl._position = {
            "side": "LONG", "entry_price": 50000.0, "entry_time": "t",
            "stop_loss": 49850.0, "take_profit": 50200.0,
            "trailing_stop": 49900.0, "size_usdt": 100.0,
        }
        row = MagicMock()
        row.__getitem__ = lambda s, k: {"close": 50100.0}[k]
        row.name = "2026-03-31T14:30:00"

        tl._close_position(row, "take_profit")

        assert tl._position is not None

    def test_open_position_live_no_position_on_order_failure(self, live_loop):
        """Se l'ordine di apertura fallisce, nessuna posizione salvata."""
        from src.sentiment.claude_sentiment import SentimentResult
        tl, tmp_path, kill_path = live_loop
        tl._exchange.get_balance.return_value = 100.0
        tl._exchange.create_order.side_effect = Exception("Order failed")

        sentiment = SentimentResult(
            sentiment_score=0.5, confidence=0.8,
            top_events=[], recommendation="BUY",
        )
        row = MagicMock()
        row.__getitem__ = lambda s, k: {"close": 50000.0}[k]
        row.name = "2026-03-31T14:25:00"

        tl._open_position("LONG", row, sentiment, atr=100.0)

        assert tl._position is None
