"""Test per il modulo exchange.

Usa mock per evitare chiamate API reali.
"""

import pandas as pd
import pytest
from unittest.mock import MagicMock, patch

from src.exchange import BinanceExchange


class TestBinanceExchangeInit:
    """Test per l'inizializzazione dell'exchange."""

    @patch("src.exchange.ccxt.binance")
    def test_creates_ccxt_instance(self, mock_binance_cls):
        """BinanceExchange deve creare un'istanza ccxt.binance."""
        exchange = BinanceExchange(api_key="test", api_secret="secret")
        mock_binance_cls.assert_called_once()

    @patch("src.exchange.ccxt.binance")
    def test_sandbox_mode_sets_urls(self, mock_binance_cls):
        """In sandbox mode, deve attivare il sandbox di ccxt."""
        mock_instance = MagicMock()
        mock_binance_cls.return_value = mock_instance
        exchange = BinanceExchange(api_key="test", api_secret="secret", sandbox=True)
        mock_instance.set_sandbox_mode.assert_called_once_with(True)


class TestFetchOHLCV:
    """Test per il fetch dei dati OHLCV."""

    @patch("src.exchange.ccxt.binance")
    def test_fetch_ohlcv_returns_dataframe(self, mock_binance_cls):
        """fetch_ohlcv deve restituire un DataFrame con colonne OHLCV."""
        mock_instance = MagicMock()
        mock_binance_cls.return_value = mock_instance
        mock_instance.fetch_ohlcv.return_value = [
            [1700000000000, 35000.0, 35100.0, 34900.0, 35050.0, 100.5],
            [1700000300000, 35050.0, 35200.0, 35000.0, 35150.0, 120.3],
            [1700000600000, 35150.0, 35300.0, 35100.0, 35250.0, 90.1],
        ]

        exchange = BinanceExchange(api_key="test", api_secret="secret")
        df = exchange.fetch_ohlcv(symbol="BTC/USDT", timeframe="5m", limit=3)

        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]
        assert len(df) == 3
        assert df["close"].iloc[-1] == 35250.0

    @patch("src.exchange.ccxt.binance")
    def test_fetch_ohlcv_sets_datetime_index(self, mock_binance_cls):
        """Il DataFrame deve avere un indice datetime."""
        mock_instance = MagicMock()
        mock_binance_cls.return_value = mock_instance
        mock_instance.fetch_ohlcv.return_value = [
            [1700000000000, 35000.0, 35100.0, 34900.0, 35050.0, 100.5],
        ]

        exchange = BinanceExchange(api_key="test", api_secret="secret")
        df = exchange.fetch_ohlcv(symbol="BTC/USDT", timeframe="5m", limit=1)

        assert isinstance(df.index, pd.DatetimeIndex)

    @patch("src.exchange.ccxt.binance")
    def test_fetch_ohlcv_accepts_1h_timeframe(self, mock_binance_cls):
        """fetch_ohlcv deve accettare timeframe='1h' senza errori."""
        mock_instance = MagicMock()
        mock_binance_cls.return_value = mock_instance
        mock_instance.fetch_ohlcv.return_value = [
            [1700000000000, 35000.0, 35100.0, 34900.0, 35050.0, 100.5],
            [1700003600000, 35050.0, 35200.0, 35000.0, 35150.0, 120.3],
        ]

        exchange = BinanceExchange(api_key="test", api_secret="secret")
        df = exchange.fetch_ohlcv(symbol="BTC/USDT", timeframe="1h", limit=50)

        mock_instance.fetch_ohlcv.assert_called_once_with("BTC/USDT", "1h", limit=50)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2


class TestGetBalance:
    """Test per il recupero del balance."""

    @patch("src.exchange.ccxt.binance")
    def test_get_balance_returns_usdt(self, mock_binance_cls):
        """get_balance deve restituire il saldo USDT disponibile."""
        mock_instance = MagicMock()
        mock_binance_cls.return_value = mock_instance
        mock_instance.fetch_balance.return_value = {
            "free": {"USDT": 1000.0, "BTC": 0.01},
            "total": {"USDT": 1500.0, "BTC": 0.02},
        }

        exchange = BinanceExchange(api_key="test", api_secret="secret")
        balance = exchange.get_balance(currency="USDT")

        assert balance == 1000.0


class TestCreateOrder:
    """Test per la creazione di ordini."""

    @patch("src.exchange.ccxt.binance")
    def test_create_market_buy_order(self, mock_binance_cls):
        """create_order deve chiamare ccxt create_order con i parametri corretti."""
        mock_instance = MagicMock()
        mock_binance_cls.return_value = mock_instance
        mock_instance.create_order.return_value = {
            "id": "12345",
            "status": "closed",
            "filled": 0.001,
            "price": 35000.0,
        }

        exchange = BinanceExchange(api_key="test", api_secret="secret")
        order = exchange.create_order(
            symbol="BTC/USDT", side="buy", amount=0.001
        )

        mock_instance.create_order.assert_called_once_with(
            symbol="BTC/USDT",
            type="market",
            side="buy",
            amount=0.001,
        )
        assert order["id"] == "12345"
