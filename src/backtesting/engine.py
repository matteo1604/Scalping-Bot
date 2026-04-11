"""Motore di backtesting per la strategia di scalping.

Simula l'esecuzione dei segnali su dati storici OHLCV con:
- RiskManager per SL/TP/trailing ATR-based
- Commissioni e spread realistici
- Entry alla open della candela successiva al segnale (no look-ahead bias)
- SL/TP controllati su HIGH/LOW della candela (non solo close)
- Position sizing dinamico via RiskManager.calculate_position_size
- Tracking strategia per trade (mean_reversion vs trend)
- Equity curve e metriche estese
- Daily reset dei contatori RiskManager
"""

import json
import os
from datetime import datetime, date

import pandas as pd
import ta

from config.settings import ADX_TREND_THRESHOLD
from src.indicators.htf_filter import HTFFilter
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
from src.indicators.technical import add_indicators, add_prev_indicators
from src.risk.manager import RiskManager
from src.strategies.combined import CombinedStrategy
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
    """

    def __init__(
        self,
        initial_capital: float = 1000.0,
        commission_pct: float = DEFAULT_COMMISSION_PCT,
        spread_pct: float = DEFAULT_SPREAD_PCT,
    ) -> None:
        self.initial_capital = initial_capital
        self.commission_pct = commission_pct
        self.spread_pct = spread_pct
        self.strategy = CombinedStrategy()
        self.risk_manager = RiskManager()

    def run(self, df: pd.DataFrame) -> dict:
        """Esegue il backtest su un DataFrame OHLCV.

        Il DataFrame può essere raw (senza indicatori) o già arricchito.
        Se mancano le colonne indicatori, vengono calcolate automaticamente.

        Entry avviene all'OPEN della candela SUCCESSIVA al segnale.
        SL/TP vengono controllati su HIGH/LOW della candela (non solo close).

        Args:
            df: DataFrame con colonne [open, high, low, close, volume].

        Returns:
            Dict con chiavi: trades, metrics, equity_final, initial_capital, equity_curve.
        """
        # Calcola indicatori se mancanti
        if "rsi" not in df.columns:
            data = add_indicators(df)
            data = add_prev_indicators(data)
            data = data.dropna()
        else:
            data = df

        # --- Pre-calcola dati HTF (1h) per filtro multi-timeframe ---
        htf_filter = HTFFilter()
        htf_series: dict = {}

        try:
            df_1h = (
                data[["open", "high", "low", "close", "volume"]]
                .resample("1h")
                .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
                .dropna()
            )
            if len(df_1h) >= 25:
                rsi_1h = ta.momentum.rsi(df_1h["close"], window=htf_filter.rsi_period)
                ema_fast_1h = ta.trend.ema_indicator(df_1h["close"], window=htf_filter.ema_fast_period)
                ema_slow_1h = ta.trend.ema_indicator(df_1h["close"], window=htf_filter.ema_slow_period)

                for idx_h, ts in enumerate(df_1h.index):
                    r = rsi_1h.iloc[idx_h]
                    ef = ema_fast_1h.iloc[idx_h]
                    es = ema_slow_1h.iloc[idx_h]
                    if pd.isna(r) or pd.isna(ef) or pd.isna(es):
                        htf_series[ts] = {"rsi_1h": None, "trend_1h": "NEUTRAL"}
                    else:
                        trend = "UP" if ef > es else ("DOWN" if ef < es else "NEUTRAL")
                        htf_series[ts] = {"rsi_1h": float(r), "trend_1h": trend}
        except Exception as e:
            logger.warning("HTF precompute fallito: %s — filtro disabilitato", e)

        trades: list[dict] = []
        position: dict | None = None
        pending_signal: str | None = None
        equity = self.initial_capital
        equity_curve: list[float] = [equity]
        current_date: date | None = None

        for i in range(len(data)):
            row = data.iloc[i]
            row_date = row.name.date() if hasattr(row.name, "date") else date.today()

            # --- Daily reset ---
            if current_date is not None and row_date != current_date:
                self.risk_manager.reset_daily()
            current_date = row_date

            # --- Apri posizione pendente (look-ahead bias fix) ---
            if pending_signal is not None and position is None:
                side = pending_signal
                pending_signal = None

                if self.risk_manager.can_trade(equity):
                    entry_open = row["open"]
                    atr = row["atr"]

                    # Spread sull'entry: LONG paga prezzo più alto, SHORT prezzo più basso
                    spread_amt = entry_open * self.spread_pct / 100.0
                    effective_entry = entry_open + spread_amt if side == "LONG" else entry_open - spread_amt

                    levels = self.risk_manager.calculate_levels(effective_entry, side, atr)

                    size = self.risk_manager.calculate_position_size(
                        capital=equity,
                        entry_price=effective_entry,
                        sl_price=levels["stop_loss"],
                        sentiment=None,
                    )

                    # Determina tipo strategia dal ADX della candela precedente
                    prev_row = data.iloc[i - 1] if i > 0 else row
                    adx_val = float(prev_row.get("adx", 0.0))
                    strategy_type = "trend" if adx_val > ADX_TREND_THRESHOLD else "mean_reversion"

                    if size > 0:
                        position = {
                            "side": side,
                            "strategy": strategy_type,
                            "entry_price": effective_entry,
                            "entry_time": data.index[i],
                            "entry_candle": i,
                            "stop_loss": levels["stop_loss"],
                            "take_profit": levels["take_profit"],
                            "trailing_stop": levels["trailing_stop"],
                            "atr": atr,
                            "size_usdt": size,
                        }
                        logger.debug(
                            "Aperta posizione %s @ %.2f (SL=%.2f TP=%.2f size=%.0f)",
                            side, effective_entry, levels["stop_loss"],
                            levels["take_profit"], size,
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
                        "strategy": position["strategy"],
                        "entry_price": round(position["entry_price"], 4),
                        "exit_price": round(exit_price, 4),
                        "stop_loss": round(position["stop_loss"], 4),
                        "take_profit": round(position["take_profit"], 4),
                        "size_usdt": round(position["size_usdt"], 2),
                        "pnl_pct": round(self._raw_pnl_pct(position, exit_price), 4),
                        "pnl": round(pnl, 4),
                        "exit_reason": exit_reason,
                        "duration_candles": i - position["entry_candle"],
                    }
                    trades.append(trade)
                    equity += pnl
                    self.risk_manager.record_trade(pnl)
                    position = None
                    equity_curve.append(equity)
                    continue  # Non generare segnale nella stessa iterazione

            # --- Genera segnale (nessuna posizione aperta, nessun pending) ---
            if position is None and pending_signal is None:
                window = data.iloc[: i + 1]
                signal = self.strategy.generate_signal(window)
                if signal in ("LONG", "SHORT"):
                    # Filtro HTF: usa l'ultima ora COMPLETATA (no look-ahead bias)
                    candle_ts = data.index[i]
                    last_completed_hour = candle_ts.floor("1h") - pd.Timedelta(hours=1)
                    htf_data = htf_series.get(last_completed_hour, {"rsi_1h": None, "trend_1h": "NEUTRAL"})
                    adx_now = float(data.iloc[i].get("adx", 0.0))
                    strategy_mode = "trend" if adx_now > ADX_TREND_THRESHOLD else "reversion"
                    if htf_filter.allows_signal(signal, strategy_mode, htf_data):
                        pending_signal = signal

            equity_curve.append(equity)

        # --- Chiudi posizione aperta a fine backtest ---
        if position is not None:
            last_row = data.iloc[-1]
            exit_price = last_row["close"]
            pnl = self._calc_net_pnl(position, exit_price)
            trade = {
                "entry_time": str(position["entry_time"]),
                "exit_time": str(data.index[-1]),
                "side": position["side"],
                "strategy": position["strategy"],
                "entry_price": round(position["entry_price"], 4),
                "exit_price": round(exit_price, 4),
                "stop_loss": round(position["stop_loss"], 4),
                "take_profit": round(position["take_profit"], 4),
                "size_usdt": round(position["size_usdt"], 2),
                "pnl_pct": round(self._raw_pnl_pct(position, exit_price), 4),
                "pnl": round(pnl, 4),
                "exit_reason": "end_of_data",
                "duration_candles": len(data) - 1 - position["entry_candle"],
            }
            trades.append(trade)
            equity += pnl
            self.risk_manager.record_trade(pnl)
            equity_curve.append(equity)

        metrics = self._compute_metrics(trades)

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
            "equity_curve": equity_curve,
        }

    def save_report(self, result: dict, output_dir: str = "data/backtest_results") -> str:
        """Salva il report del backtest in formato JSON.

        L'equity_curve è esclusa per mantenere il JSON leggibile.

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
        report = {k: v for k, v in result.items() if k != "equity_curve"}
        with open(filepath, "w") as f:
            json.dump(report, f, indent=2, default=str)
        logger.info("Report salvato: %s", filepath)
        return filepath

    def _calc_net_pnl(self, position: dict, exit_price: float) -> float:
        """Calcola il PnL netto detraendo commissioni e spread.

        Costi: commissione entry + commissione exit + spread entry + spread exit.
        Il PnL è scalato su position["size_usdt"].

        Args:
            position: Dict posizione aperta (include "size_usdt").
            exit_price: Prezzo di chiusura (lordo, prima dello spread di uscita).

        Returns:
            PnL netto in USDT.
        """
        side = position["side"]
        size = position["size_usdt"]

        # Spread sull'exit (inverso rispetto all'entry)
        spread_amt = exit_price * self.spread_pct / 100.0
        effective_exit = exit_price - spread_amt if side == "LONG" else exit_price + spread_amt

        # PnL lordo percentuale
        raw_pct = self._raw_pnl_pct(position, effective_exit)

        # Commissioni (entry + exit) come % del valore nozionale
        commission_pct_total = self.commission_pct * 2

        net_pct = raw_pct - commission_pct_total
        return (net_pct / 100.0) * size

    def _compute_metrics(self, trades: list[dict]) -> dict:
        """Calcola tutte le metriche di performance."""
        pf = profit_factor(trades)
        sr = sharpe_ratio(trades)
        cr = calmar_ratio(trades, initial_capital=self.initial_capital)

        winners = [t["pnl"] for t in trades if t["pnl"] > 0]
        losers = [t["pnl"] for t in trades if t["pnl"] < 0]
        gross_profit = sum(winners)
        gross_loss = sum(losers)
        avg_win = gross_profit / len(winners) if winners else 0.0
        avg_loss = gross_loss / len(losers) if losers else 0.0

        return {
            "total_trades": len(trades),
            "win_rate": round(win_rate(trades), 2),
            "profit_factor": round(pf, 2) if pf != float("inf") else "inf",
            "max_drawdown": round(max_drawdown(trades, self.initial_capital), 2),
            "sharpe_ratio": round(sr, 2) if sr not in (float("inf"), float("-inf")) else str(sr),
            "calmar_ratio": round(cr, 2) if cr != float("inf") else "inf",
            "avg_trade_duration": round(avg_trade_duration(trades), 2),
            "max_consecutive_losses": max_consecutive_losses(trades),
            "net_pnl": round(net_pnl(trades), 4),
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
        }

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
