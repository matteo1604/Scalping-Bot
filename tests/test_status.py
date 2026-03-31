"""Test per StatusWriter."""

import json
import os
import pytest

from src.utils.status import StatusWriter


@pytest.fixture
def tmp_status(tmp_path):
    """StatusWriter con path temporaneo."""
    path = str(tmp_path / "status.json")
    return StatusWriter(output_path=path), path


class TestStatusWriterWrite:
    """Test per StatusWriter.write()."""

    def test_writes_valid_json(self, tmp_status):
        """Deve scrivere un file JSON valido."""
        sw, path = tmp_status
        data = {
            "timestamp": "2026-03-31T14:35:00Z",
            "mode": "paper",
            "position": None,
            "daily": {"trades": 0, "pnl": 0.0, "win_rate": 0.0},
            "last_signal": None,
            "last_sentiment": None,
        }
        sw.write(data)
        with open(path) as f:
            loaded = json.load(f)
        assert loaded["timestamp"] == "2026-03-31T14:35:00Z"
        assert loaded["mode"] == "paper"
        assert loaded["position"] is None

    def test_overwrites_existing(self, tmp_status):
        """Deve sovrascrivere il file ad ogni chiamata."""
        sw, path = tmp_status
        sw.write({"timestamp": "first", "mode": "paper", "position": None,
                   "daily": {}, "last_signal": None, "last_sentiment": None})
        sw.write({"timestamp": "second", "mode": "paper", "position": None,
                   "daily": {}, "last_signal": None, "last_sentiment": None})
        with open(path) as f:
            loaded = json.load(f)
        assert loaded["timestamp"] == "second"

    def test_creates_parent_directory(self, tmp_path):
        """Deve creare la directory se non esiste."""
        path = str(tmp_path / "subdir" / "status.json")
        sw = StatusWriter(output_path=path)
        sw.write({"timestamp": "test", "mode": "paper", "position": None,
                   "daily": {}, "last_signal": None, "last_sentiment": None})
        assert os.path.exists(path)

    def test_writes_position_data(self, tmp_status):
        """Deve scrivere i dati della posizione aperta."""
        sw, path = tmp_status
        data = {
            "timestamp": "2026-03-31T14:35:00Z",
            "mode": "paper",
            "position": {
                "side": "LONG",
                "entry_price": 50000.0,
                "entry_time": "2026-03-31T14:25:00Z",
                "stop_loss": 49850.0,
                "take_profit": 50200.0,
                "trailing_stop": 49950.0,
                "unrealized_pnl_pct": 0.15,
            },
            "daily": {"trades": 3, "pnl": 12.50, "win_rate": 66.7},
            "last_signal": "LONG",
            "last_sentiment": {"score": 0.4, "confidence": 0.7, "recommendation": "BUY"},
        }
        sw.write(data)
        with open(path) as f:
            loaded = json.load(f)
        assert loaded["position"]["side"] == "LONG"
        assert loaded["position"]["entry_price"] == 50000.0


class TestStatusWriterRead:
    """Test per StatusWriter.read()."""

    def test_read_existing_file(self, tmp_status):
        """Deve leggere un file JSON esistente."""
        sw, path = tmp_status
        data = {"timestamp": "test", "mode": "paper", "position": {"side": "LONG"},
                "daily": {}, "last_signal": None, "last_sentiment": None}
        sw.write(data)
        loaded = sw.read()
        assert loaded is not None
        assert loaded["position"]["side"] == "LONG"

    def test_read_missing_file(self, tmp_path):
        """Deve restituire None se il file non esiste."""
        sw = StatusWriter(output_path=str(tmp_path / "nonexistent.json"))
        assert sw.read() is None

    def test_read_corrupted_file(self, tmp_status):
        """Deve restituire None se il file e' corrotto."""
        sw, path = tmp_status
        with open(path, "w") as f:
            f.write("not valid json{{{")
        assert sw.read() is None
