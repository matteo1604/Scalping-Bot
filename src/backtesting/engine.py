"""Motore di backtesting per la strategia di scalping.

Simula l'esecuzione dei segnali su dati storici OHLCV con stop-loss e take-profit.
"""

import json
import os
from datetime import datetime

import pandas as pd

from config.settings import STOP_LOSS_PCT, TAKE_PROFIT_PCT, TRADE_AMOUNT_USDT
from src.indicators.technical import add_indicators, add_prev_indicators
from src.strategies.combined import CombinedStrategy
from src.backtesting.metrics import win_rate, profit_factor, max_drawdown, sharpe_ratio
from src.utils.logger import setup_logger

logger = setup_logger("backtester")


class Backtester:
    """Motore di backtesting per simulare trade su dati storici.

    Args:
        initial_capital: Capitale iniziale in USDT.
        stop_loss_pct: Stop loss in percentuale.
        take_profit_pct: Take profit in percentuale.
        trade_amount: Importo per trade in USDT.
    """

    def __init__(
        self,
        initial_capital: float = 1000.0,
        stop_loss_pct: float = STOP_LOSS_PCT,
        take_profit_pct: float = TAKE_PROFIT_PCT,
        trade_amount: float = TRADE_AMOUNT_USDT,
    ) -> None:
        self.initial_capital = initial_capital
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.trade_amount = trade_amount
        self.strategy = CombinedStrategy()

    def run(self, df: pd.DataFrame) -> dict:
        """Esegue il backtest su un DataFrame OHLCV.

        Args:
            df: DataFrame con colonne [open, high, low, close, volume].

        Returns:
            Dict con chiavi: trades, metrics, equity_final.
        """
        # Prepara indicatori
        data = add_indicators(df)
        data = add_prev_indicators(data)
        data = data.dropna()

        trades: list[dict] = []
        position: dict | None = None
        equity = self.initial_capital

        for i in range(len(data)):
            row = data.iloc[i]

            # Se abbiamo una posizione aperta, controlla SL/TP
            if position is not None:
                pnl_pct = self._calc_pnl_pct(position, row["close"])

                hit_sl = pnl_pct <= -self.stop_loss_pct
                hit_tp = pnl_pct >= self.take_profit_pct

                if hit_sl or hit_tp:
                    pnl = (pnl_pct / 100.0) * self.trade_amount
                    trade = {
                        "entry_time": str(position["entry_time"]),
                        "exit_time": str(data.index[i]),
                        "side": position["side"],
                        "entry_price": position["entry_price"],
                        "exit_price": row["close"],
                        "pnl_pct": round(pnl_pct, 4),
                        "pnl": round(pnl, 4),
                        "exit_reason": "stop_loss" if hit_sl else "take_profit",
                    }
                    trades.append(trade)
                    equity += pnl
                    position = None
                continue  # Non aprire nuove posizioni mentre siamo in trade

            # Genera segnale
            window = data.iloc[: i + 1]
            signal = self.strategy.generate_signal(window)

            if signal in ("LONG", "SHORT"):
                position = {
                    "side": signal,
                    "entry_price": row["close"],
                    "entry_time": data.index[i],
                }

        # Chiudi posizione aperta a fine backtest
        if position is not None:
            last_row = data.iloc[-1]
            pnl_pct = self._calc_pnl_pct(position, last_row["close"])
            pnl = (pnl_pct / 100.0) * self.trade_amount
            trade = {
                "entry_time": str(position["entry_time"]),
                "exit_time": str(data.index[-1]),
                "side": position["side"],
                "entry_price": position["entry_price"],
                "exit_price": last_row["close"],
                "pnl_pct": round(pnl_pct, 4),
                "pnl": round(pnl, 4),
                "exit_reason": "end_of_data",
            }
            trades.append(trade)
            equity += pnl

        pf = profit_factor(trades)
        sr = sharpe_ratio(trades)
        metrics = {
            "total_trades": len(trades),
            "win_rate": round(win_rate(trades), 2),
            "profit_factor": round(pf, 2) if pf != float("inf") else "inf",
            "max_drawdown": round(max_drawdown(trades, self.initial_capital), 2),
            "sharpe_ratio": round(sr, 2) if sr != float("inf") else "inf",
        }

        logger.info("Backtest completato: %d trade, WR=%.1f%%, PF=%s",
                     metrics["total_trades"], metrics["win_rate"], metrics["profit_factor"])

        return {
            "trades": trades,
            "metrics": metrics,
            "equity_final": round(equity, 2),
            "initial_capital": self.initial_capital,
        }

    def save_report(self, result: dict, output_dir: str = "data/backtest_results") -> str:
        """Salva il report del backtest in formato JSON.

        Args:
            result: Risultato del backtest da run().
            output_dir: Directory di output.

        Returns:
            Path del file salvato.
        """
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"backtest_{timestamp}.json"
        filepath = os.path.join(output_dir, filename)
        with open(filepath, "w") as f:
            json.dump(result, f, indent=2, default=str)
        logger.info("Report salvato: %s", filepath)
        return filepath

    @staticmethod
    def _calc_pnl_pct(position: dict, current_price: float) -> float:
        """Calcola il PnL percentuale di una posizione.

        Args:
            position: Dict con "side" e "entry_price".
            current_price: Prezzo corrente.

        Returns:
            PnL in percentuale.
        """
        entry = position["entry_price"]
        if position["side"] == "LONG":
            return ((current_price - entry) / entry) * 100.0
        else:  # SHORT
            return ((entry - current_price) / entry) * 100.0
