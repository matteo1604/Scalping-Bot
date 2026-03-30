"""Connessione e interazione con Binance via ccxt.

Responsabilità:
- Inizializzare la connessione a Binance (API key da .env)
- Fetch candele OHLCV (BTC/USDT, 5min)
- Piazzare ordini (market buy/sell)
- Ottenere balance e posizioni aperte
- Gestire rate limits e retry
"""

import ccxt
import pandas as pd

from src.utils.logger import setup_logger

logger = setup_logger("exchange")


class BinanceExchange:
    """Wrapper attorno a ccxt.binance per operazioni di trading.

    Args:
        api_key: Binance API key.
        api_secret: Binance API secret.
        sandbox: Se True, usa il testnet di Binance.
    """

    def __init__(self, api_key: str, api_secret: str, sandbox: bool = False) -> None:
        self._exchange = ccxt.binance({
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        })
        if sandbox:
            self._exchange.set_sandbox_mode(True)
        logger.info("Connesso a Binance (sandbox=%s)", sandbox)

    def fetch_ohlcv(
        self,
        symbol: str = "BTC/USDT",
        timeframe: str = "5m",
        limit: int = 100,
    ) -> pd.DataFrame:
        """Scarica candele OHLCV dall'exchange.

        Args:
            symbol: Coppia di trading.
            timeframe: Intervallo temporale delle candele.
            limit: Numero massimo di candele da scaricare.

        Returns:
            DataFrame con colonne [open, high, low, close, volume]
            e indice DatetimeIndex.
        """
        logger.debug("Fetch OHLCV: %s %s (limit=%d)", symbol, timeframe, limit)
        raw = self._exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)
        logger.info("Scaricate %d candele %s %s", len(df), symbol, timeframe)
        return df

    def get_balance(self, currency: str = "USDT") -> float:
        """Restituisce il saldo disponibile (free) per una valuta.

        Args:
            currency: Valuta di cui ottenere il saldo.

        Returns:
            Saldo disponibile.
        """
        balance = self._exchange.fetch_balance()
        free = balance["free"].get(currency, 0.0)
        logger.info("Balance %s: %.4f", currency, free)
        return free

    def create_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        order_type: str = "market",
    ) -> dict:
        """Crea un ordine sull'exchange.

        Args:
            symbol: Coppia di trading.
            side: 'buy' o 'sell'.
            amount: Quantità da comprare/vendere.
            order_type: Tipo di ordine (default: market).

        Returns:
            Risposta dell'ordine da ccxt.
        """
        logger.info("Ordine %s %s: %.6f %s", order_type, side, amount, symbol)
        order = self._exchange.create_order(
            symbol=symbol,
            type=order_type,
            side=side,
            amount=amount,
        )
        logger.info("Ordine eseguito: id=%s status=%s", order.get("id"), order.get("status"))
        return order
