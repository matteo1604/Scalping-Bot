"""Configurazione centralizzata del bot."""

import os
from dotenv import load_dotenv

load_dotenv()

# --- Exchange ---
BINANCE_API_KEY: str = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET: str = os.getenv("BINANCE_API_SECRET", "")

# --- Trading ---
SYMBOL: str = "BTC/USDT"
TIMEFRAME: str = "5m"
TRADE_AMOUNT_USDT: float = 10.0  # Capitale per trade (minimo per test)

# --- Indicatori ---
EMA_FAST: int = 9
EMA_SLOW: int = 21
RSI_PERIOD: int = 14
RSI_OVERBOUGHT: float = 70.0
RSI_OVERSOLD: float = 30.0
VOLUME_MA_PERIOD: int = 20

# Bollinger Bands
BB_PERIOD: int = 20
BB_STD: float = 2.0

# ATR
ATR_PERIOD: int = 14

# ADX — filtro regime di mercato
ADX_PERIOD: int = 14
ADX_TREND_THRESHOLD: float = 25.0  # sopra questo = trend forte, no mean reversion

# RSI soglie entry (più strette di RSI_OVERBOUGHT/RSI_OVERSOLD)
RSI_ENTRY_OVERSOLD: float = 25.0    # soglia entry LONG
RSI_ENTRY_OVERBOUGHT: float = 75.0  # soglia entry SHORT
RSI_EXIT_NEUTRAL: float = 50.0      # target uscita per mean reversion

# --- Sentiment ---
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
SENTIMENT_MODEL: str = "claude-sonnet-4-20250514"
SENTIMENT_THRESHOLD: float = 0.3  # Score minimo per conferma
SENTIMENT_COOLDOWN_MIN: int = 15  # minuti minimo tra chiamate sentiment

# --- Risk Management ---
STOP_LOSS_PCT: float = 0.5   # 0.5%
TAKE_PROFIT_PCT: float = 1.0  # 1.0%
MAX_DAILY_LOSS_PCT: float = 3.0
MAX_DAILY_TRADES: int = 20
RISK_PER_TRADE_PCT: float = 1.0       # % capitale rischiato per trade
SL_ATR_MULTIPLIER: float = 1.5        # moltiplicatore ATR per stop-loss
TP_ATR_MULTIPLIER: float = 2.0        # moltiplicatore ATR per take-profit
TRAILING_ATR_MULTIPLIER: float = 1.0  # moltiplicatore ATR per trailing stop
MAX_POSITION_SIZE_PCT: float = 20.0   # cap massimo size come % del capitale
MIN_ORDER_SIZE_USDT: float = 10.0     # ordine minimo Binance BTC/USDT

# --- Bot ---
BOT_MODE: str = os.getenv("BOT_MODE", "paper")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# --- Notifiche ---
SLACK_WEBHOOK_URL: str = os.getenv("SLACK_WEBHOOK_URL", "")

# --- Live ---
LIVE_CAPITAL_USDT: float = 50.0  # capitale allocato per live trading
KILL_SWITCH_PATH: str = "data/kill.flag"
