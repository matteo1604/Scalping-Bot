"""Motore di backtesting per la strategia di scalping.

Simula l'esecuzione dei segnali su dati storici OHLCV con:
- SL/TP ATR-based via RiskManager (no percentuali fisse)
- Look-ahead bias fix: entry all'open della candela successiva al segnale
- Commissioni e spread realistici
- Check SL/TP con high/low (non solo close)
- Trailing stop aggiornato ad ogni candela
- Limiti giornalieri via RiskManager.can_trade()
"""

import json
import os
from datetime import datetime

import pandas as pd

from config.settings import TRADE_AMOUNT_USDT
from src.indicators.technical import add_indicators, add_prev_indicators
from src.strategies.combined import CombinedStrategy
from src.risk.manager import RiskManager
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
from src.utils.logger import setup_logger

logger = setup_logger("backtester")

# Commissioni Binance spot e spread tipico BTC/USDT
DEFAULT_COMMISSION_PCT: float = 0.1   # 0.1% per lato
DEFAULT_SPREAD_PCT: float = 0.01      # 0.01%


class Backtester:
    """Motore di backtesting per simulare trade su dati storici.

    Args:
        initial_capital: Capitale iniziale in USDT.
        commission_pct: Commissione per lato in percentuale (default: 0.1%).
        spread_pct: Spread tipico in percentuale (default: 0.01%).
        trade_amount: Importo per trade in USDT.
    """

    def __init__(
        self,
        initial_capital: float = 1000.0,
        commission_pct: float = DEFAULT_COMMISSION_PCT,
        spread_pct: float = DEFAULT_SPREAD_PCT,
        trade_amount: float = TRADE_AMOUNT_USDT,
    ) -> None:
        self.initial_capital = initial_capital
        self.commission_pct = commission_pct
        self.spread_pct = spread_pct
        self.trade_amount = trade_amount
        self.strategy = CombinedStrategy()
        self.risk_manager = RiskManager()

    def run(self, df: pd.DataFrame) -> dict:
        """Esegue il backtest su un DataFrame OHLCV.

        Args:
            df: DataFrame con colonne [open, high, low, close, volume].

        Returns:
            Dict con chiavi: trades, metrics, equity_final, initial_capital.
        """
        data = add_indicators(df)
        data = add_prev_indicators(data)
        data = data.dropna()

        trades: list[dict] = []
        position: dict | None = None
        pending_signal: str | None = None  # segnale salvato per entry alla candela successiva
        equity = self.initial_capital

        for i in range(len(data)):
            row = data.iloc[i]

            # --- Apri posizione pendente (look-ahead bias fix) ---
            if pending_signal is not None and position is None:
                side = pending_signal
                pending_signal = None

                if self.risk_manager.can_trade(equity):
                    entry_open = row["open"]
                    atr = row["atr"]

                    # Spread sull'entry: LONG paga prezzo più alto, SHORT prezzo più basso
                    spread_amt = entry_open * self.spread_pct / 100.0
                    if side == "LONG":
                        effective_entry = entry_open + spread_amt
                    else:
                        effective_entry = entry_open - spread_amt

                    levels = self.risk_manager.calculate_levels(effective_entry, side, atr)
                    position = {
                        "side": side,
                        "entry_price": effective_entry,
                        "entry_time": data.index[i],
                        "entry_candle": i,
                        "stop_loss": levels["stop_loss"],
                        "take_profit": levels["take_profit"],
                        "trailing_stop": levels["trailing_stop"],
                        "atr": atr,
                    }
                    logger.debug(
                        "Aperta posizione %s @ %.2f (SL=%.2f TP=%.2f)",
                        side, effective_entry, levels["stop_loss"], levels["take_profit"],
                    )

            # --- Gestisci posizione aperta ---
            if position is not None:
                high = row["high"]
                low = row["low"]
                close = row["close"]
                atr = row["atr"]

                # Aggiorna trailing stop
                position["trailing_stop"] = self.risk_manager.update_trailing_stop(
                    side=position["side"],
                    current_price=close,
                    current_trailing=position["trailing_stop"],
                    atr=atr,
                )

                # Check SL con high/low (priorità SL su TP)
                exit_price: float | None = None
                exit_reason: str | None = None

                if position["side"] == "LONG":
                    sl = max(position["stop_loss"], position["trailing_stop"])
                    if low <= sl:
                        exit_price = sl
                        exit_reason = "stop_loss"
                    elif high >= position["take_profit"]:
                        exit_price = position["take_profit"]
                        exit_reason = "take_profit"
                else:  # SHORT
                    sl = min(position["stop_loss"], position["trailing_stop"])
                    if high >= sl:
                        exit_price = sl
                        exit_reason = "stop_loss"
                    elif low <= position["take_profit"]:
                        exit_price = position["take_profit"]
                        exit_reason = "take_profit"

                if exit_price is not None:
                    pnl = self._calc_net_pnl(position, exit_price)
                    trade = {
                        "entry_time": str(position["entry_time"]),
                        "exit_time": str(data.index[i]),
                        "side": position["side"],
                        "entry_price": round(position["entry_price"], 4),
                        "exit_price": round(exit_price, 4),
                        "stop_loss": round(position["stop_loss"], 4),
                        "take_profit": round(position["take_profit"], 4),
                        "pnl_pct": round(self._raw_pnl_pct(position, exit_price), 4),
                        "pnl": round(pnl, 4),
                        "exit_reason": exit_reason,
                        "duration_candles": i - position["entry_candle"],
                    }
                    trades.append(trade)
                    equity += pnl
                    self.risk_manager.record_trade(pnl)
                    position = None
                continue  # Non generare segnale nella stessa iterazione

            # --- Genera segnale (nessuna posizione aperta, nessun pending) ---
            window = data.iloc[: i + 1]
            signal = self.strategy.generate_signal(window)
            if signal in ("LONG", "SHORT"):
                pending_signal = signal  # entry alla prossima candela

        # --- Chiudi posizione aperta a fine backtest ---
        if position is not None:
            last_row = data.iloc[-1]
            exit_price = last_row["close"]
            pnl = self._calc_net_pnl(position, exit_price)
            trade = {
                "entry_time": str(position["entry_time"]),
                "exit_time": str(data.index[-1]),
                "side": position["side"],
                "entry_price": round(position["entry_price"], 4),
                "exit_price": round(exit_price, 4),
                "stop_loss": round(position["stop_loss"], 4),
                "take_profit": round(position["take_profit"], 4),
                "pnl_pct": round(self._raw_pnl_pct(position, exit_price), 4),
                "pnl": round(pnl, 4),
                "exit_reason": "end_of_data",
                "duration_candles": len(data) - 1 - position["entry_candle"],
            }
            trades.append(trade)
            equity += pnl
            self.risk_manager.record_trade(pnl)

        pf = profit_factor(trades)
        sr = sharpe_ratio(trades)
        cr = calmar_ratio(trades, initial_capital=self.initial_capital)
        metrics = {
            "total_trades": len(trades),
            "win_rate": round(win_rate(trades), 2),
            "profit_factor": round(pf, 2) if pf != float("inf") else "inf",
            "max_drawdown": round(max_drawdown(trades, self.initial_capital), 2),
            "sharpe_ratio": round(sr, 2) if sr not in (float("inf"), float("-inf")) else str(sr),
            "avg_trade_duration": round(avg_trade_duration(trades), 2),
            "max_consecutive_losses": max_consecutive_losses(trades),
            "net_pnl": round(net_pnl(trades), 4),
            "calmar_ratio": round(cr, 2) if cr != float("inf") else "inf",
        }

        logger.info(
            "Backtest completato: %d trade, WR=%.1f%%, PF=%s, NetPnL=%.2f",
            metrics["total_trades"], metrics["win_rate"],
            metrics["profit_factor"], metrics["net_pnl"],
        )

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

    def _calc_net_pnl(self, position: dict, exit_price: float) -> float:
        """Calcola il PnL netto detraendo commissioni e spread.

        Costi: commissione entry + commissione exit + spread entry + spread exit.
        Il PnL è scalato su self.trade_amount.

        Args:
            position: Dict posizione aperta.
            exit_price: Prezzo di chiusura (lordo, prima dello spread di uscita).

        Returns:
            PnL netto in USDT.
        """
        entry = position["entry_price"]
        side = position["side"]

        # Spread sull'exit (inverso rispetto all'entry)
        spread_amt = exit_price * self.spread_pct / 100.0
        if side == "LONG":
            effective_exit = exit_price - spread_amt
        else:
            effective_exit = exit_price + spread_amt

        # PnL lordo percentuale (su effective_entry e effective_exit)
        raw_pct = self._raw_pnl_pct(position, effective_exit)

        # Commissioni (entry + exit) come % del valore nozionale
        commission_pct_total = self.commission_pct * 2

        net_pct = raw_pct - commission_pct_total
        return (net_pct / 100.0) * self.trade_amount

    @staticmethod
    def _raw_pnl_pct(position: dict, price: float) -> float:
        """PnL percentuale lordo (senza costi).

        Args:
            position: Dict con "side" e "entry_price".
            price: Prezzo di riferimento per il calcolo.

        Returns:
            PnL in percentuale.
        """
        entry = position["entry_price"]
        if position["side"] == "LONG":
            return ((price - entry) / entry) * 100.0
        else:
            return ((entry - price) / entry) * 100.0
