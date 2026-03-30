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

# --- Sentiment ---
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
SENTIMENT_MODEL: str = "claude-sonnet-4-20250514"
SENTIMENT_THRESHOLD: float = 0.3  # Score minimo per conferma

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
