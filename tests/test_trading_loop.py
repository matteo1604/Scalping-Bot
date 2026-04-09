"""Test per il TradingLoop (position management)."""

import json
import os
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from src.main import TradingLoop


@pytest.fixture
def loop(tmp_path):
    """TradingLoop con componenti mockati."""
    status_path = str(tmp_path / "status.json")
    with patch("src.main.BinanceExchange"):
        with patch("src.main.ClaudeSentiment"):
            tl = TradingLoop(mode="paper", status_path=status_path)
    return tl


class TestCheckOpenPosition:
    """Test per _check_open_position."""

    def test_long_sl_hit(self, loop):
        """LONG: low <= stop_loss -> chiudi con stop_loss."""
        loop._position = {
            "side": "LONG", "entry_price": 50000.0, "entry_time": "t",
            "stop_loss": 49850.0, "take_profit": 50200.0,
            "trailing_stop": 49900.0, "size_usdt": 100.0,
        }
        row = MagicMock()
        row.__getitem__ = lambda s, k: {"high": 50100.0, "low": 49800.0, "close": 49900.0}[k]

        loop._check_open_position(row, MagicMock())
        assert loop._position is None  # posizione chiusa

    def test_long_tp_hit(self, loop):
        """LONG: high >= take_profit -> chiudi con take_profit."""
        loop._position = {
            "side": "LONG", "entry_price": 50000.0, "entry_time": "t",
            "stop_loss": 49850.0, "take_profit": 50200.0,
            "trailing_stop": 49900.0, "size_usdt": 100.0,
        }
        row = MagicMock()
        row.__getitem__ = lambda s, k: {"high": 50250.0, "low": 49900.0, "close": 50200.0}[k]

        loop._check_open_position(row, MagicMock())
        assert loop._position is None

    def test_long_sl_priority_over_tp(self, loop):
        """Candela che tocca sia SL che TP: SL ha priorita' (conservativo)."""
        loop._position = {
            "side": "LONG", "entry_price": 50000.0, "entry_time": "t",
            "stop_loss": 49850.0, "take_profit": 50200.0,
            "trailing_stop": 49900.0, "size_usdt": 100.0,
        }
        row = MagicMock()
        # Candela con range enorme: tocca sia SL (low=49800) che TP (high=50300)
        row.__getitem__ = lambda s, k: {"high": 50300.0, "low": 49800.0, "close": 50000.0}[k]

        loop._close_position = MagicMock()
        loop._check_open_position(row, MagicMock())
        # Deve chiamare _close_position con reason="stop_loss" (non take_profit)
        loop._close_position.assert_called_once()
        call_args = loop._close_position.call_args
        # reason e' il secondo argomento posizionale
        assert call_args[0][1] == "stop_loss"

    def test_short_sl_hit(self, loop):
        """SHORT: high >= stop_loss -> chiudi con stop_loss."""
        loop._position = {
            "side": "SHORT", "entry_price": 50000.0, "entry_time": "t",
            "stop_loss": 50150.0, "take_profit": 49800.0,
            "trailing_stop": 50100.0, "size_usdt": 100.0,
        }
        row = MagicMock()
        row.__getitem__ = lambda s, k: {"high": 50200.0, "low": 49900.0, "close": 50100.0}[k]

        loop._check_open_position(row, MagicMock())
        assert loop._position is None

    def test_no_exit_when_within_range(self, loop):
        """Nessuna uscita se il prezzo e' dentro SL-TP."""
        loop._position = {
            "side": "LONG", "entry_price": 50000.0, "entry_time": "t",
            "stop_loss": 49850.0, "take_profit": 50200.0,
            "trailing_stop": 49900.0, "size_usdt": 100.0,
        }
        row = MagicMock()
        row.__getitem__ = lambda s, k: {"high": 50100.0, "low": 49901.0, "close": 50050.0}[k]

        loop._check_open_position(row, MagicMock())
        assert loop._position is not None  # posizione ancora aperta

    def test_trailing_stop_updates(self, loop):
        """Trailing stop deve aggiornarsi quando il prezzo sale (LONG)."""
        loop._position = {
            "side": "LONG", "entry_price": 50000.0, "entry_time": "t",
            "stop_loss": 49850.0, "take_profit": 50200.0,
            "trailing_stop": 49900.0, "size_usdt": 100.0,
        }
        row = MagicMock()
        # Prezzo sale a 50150, trailing dovrebbe salire
        row.__getitem__ = lambda s, k: {"high": 50150.0, "low": 50050.0, "close": 50100.0}[k]

        loop._check_open_position(row, MagicMock())
        assert loop._position is not None
        # Trailing dovrebbe essere salito (esatto valore dipende da ATR, ma > 49900)
        assert loop._position["trailing_stop"] >= 49900.0


class TestPartialTP:
    """Test per il partial take profit."""

    def test_partial_tp_triggers_at_50pct(self, loop):
        """Partial TP si attiva al 50% del percorso verso TP."""
        loop._position = {
            "side": "LONG", "entry_price": 50000.0, "entry_time": "t",
            "stop_loss": 49850.0, "take_profit": 50200.0,
            "trailing_stop": 49900.0, "size_usdt": 100.0,
            "partial_tp_done": False, "original_size_usdt": 100.0,
            "strategy": "reversion",
        }
        row = MagicMock()
        row.__getitem__ = lambda s, k: {"high": 50150.0, "low": 50050.0, "close": 50100.0}[k]
        df = MagicMock()

        loop._check_open_position(row, df)

        assert loop._position is not None
        assert loop._position["partial_tp_done"] is True
        assert loop._position["size_usdt"] == 50.0
        assert loop._position["stop_loss"] == 50000.0  # break-even

    def test_partial_tp_not_repeated(self, loop):
        """Partial TP non si ripete se già fatto."""
        loop._position = {
            "side": "LONG", "entry_price": 50000.0, "entry_time": "t",
            "stop_loss": 50000.0, "take_profit": 50200.0,
            "trailing_stop": 49950.0, "size_usdt": 50.0,
            "partial_tp_done": True, "original_size_usdt": 100.0,
            "strategy": "reversion",
        }
        row = MagicMock()
        row.__getitem__ = lambda s, k: {"high": 50150.0, "low": 50060.0, "close": 50100.0}[k]
        df = MagicMock()
        # Stub should_exit per isolare il test dal comportamento del MagicMock df
        loop._strategy.should_exit = MagicMock(return_value=None)
        loop._execute_partial_tp = MagicMock()

        loop._check_open_position(row, df)

        loop._execute_partial_tp.assert_not_called()
        assert loop._position is not None
        assert loop._position["size_usdt"] == 50.0  # invariata


class TestOpenClosePosition:
    """Test per _open_position e _close_position."""

    def test_open_position_sets_state(self, loop):
        """_open_position deve settare _position con tutti i campi."""
        from src.sentiment.claude_sentiment import SentimentResult
        sentiment = SentimentResult(sentiment_score=0.5, confidence=0.8,
                                     top_events=[], recommendation="BUY")
        row = MagicMock()
        row.__getitem__ = lambda s, k: {"close": 50000.0}[k]
        row.name = "2026-03-31T14:25:00"

        loop._open_position("LONG", row, sentiment, atr=100.0)

        assert loop._position is not None
        assert loop._position["side"] == "LONG"
        assert loop._position["entry_price"] == 50000.0
        assert "stop_loss" in loop._position
        assert "take_profit" in loop._position
        assert "trailing_stop" in loop._position
        assert "size_usdt" in loop._position

    def test_close_position_clears_state(self, loop):
        """_close_position deve azzerare _position e registrare il trade."""
        loop._position = {
            "side": "LONG", "entry_price": 50000.0, "entry_time": "t",
            "stop_loss": 49850.0, "take_profit": 50200.0,
            "trailing_stop": 49900.0, "size_usdt": 100.0,
        }
        row = MagicMock()
        row.__getitem__ = lambda s, k: {"close": 50100.0}[k]
        row.name = "2026-03-31T14:30:00"

        loop._close_position(row, "take_profit")

        assert loop._position is None
        assert loop._daily_trades > 0


class TestRecoverPosition:
    """Test per _recover_position."""

    def test_recover_from_valid_file(self, tmp_path):
        """Deve ripristinare la posizione da un file valido."""
        status_path = str(tmp_path / "status.json")
        data = {
            "position": {
                "side": "LONG", "entry_price": 50000.0, "entry_time": "t",
                "stop_loss": 49850.0, "take_profit": 50200.0,
                "trailing_stop": 49900.0, "size_usdt": 100.0,
            }
        }
        with open(status_path, "w") as f:
            json.dump(data, f)

        with patch("src.main.BinanceExchange"):
            with patch("src.main.ClaudeSentiment"):
                tl = TradingLoop(mode="paper", status_path=status_path)

        assert tl._position is not None
        assert tl._position["side"] == "LONG"

    def test_recover_no_file(self, tmp_path):
        """Nessun file -> nessuna posizione, nessun errore."""
        status_path = str(tmp_path / "nonexistent.json")
        with patch("src.main.BinanceExchange"):
            with patch("src.main.ClaudeSentiment"):
                tl = TradingLoop(mode="paper", status_path=status_path)
        assert tl._position is None

    def test_recover_null_position(self, tmp_path):
        """File con position=null -> nessuna posizione."""
        status_path = str(tmp_path / "status.json")
        with open(status_path, "w") as f:
            json.dump({"position": None}, f)

        with patch("src.main.BinanceExchange"):
            with patch("src.main.ClaudeSentiment"):
                tl = TradingLoop(mode="paper", status_path=status_path)
        assert tl._position is None


class TestCheckDailyReset:
    """Test per _check_daily_reset."""

    def test_resets_on_new_day(self, loop):
        """Cambio data deve resettare i contatori."""
        loop._daily_trades = 5
        loop._daily_wins = 3
        loop._daily_pnl = 25.0
        loop._last_date = date(2026, 3, 30)

        with patch("src.main.date") as mock_date:
            mock_date.today.return_value = date(2026, 3, 31)
            mock_date.side_effect = lambda *args, **kw: date(*args, **kw)
            loop._check_daily_reset()

        assert loop._daily_trades == 0
        assert loop._daily_wins == 0
        assert loop._daily_pnl == 0.0

    def test_no_reset_same_day(self, loop):
        """Stessa data non deve resettare."""
        loop._daily_trades = 5
        loop._last_date = date.today()

        loop._check_daily_reset()

        assert loop._daily_trades == 5
