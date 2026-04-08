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
RSI_OVERBOUGHT: float = 70.0   # legacy (non usato dalla strategia, mantenuto per retrocompat)
RSI_OVERSOLD: float = 30.0     # legacy (non usato dalla strategia, mantenuto per retrocompat)
VOLUME_MA_PERIOD: int = 20

# Bollinger Bands
BB_PERIOD: int = 20
BB_STD: float = 2.0

# ATR
ATR_PERIOD: int = 14

# ADX — filtro regime di mercato
ADX_PERIOD: int = 14
ADX_TREND_THRESHOLD: float = 25.0  # sopra questo = trend forte, no mean reversion

# RSI soglie entry — condizione A (RSI moderato + BB)
RSI_ENTRY_OVERSOLD: float = 30.0    # soglia entry LONG via cond A (era 25)
RSI_ENTRY_OVERBOUGHT: float = 70.0  # soglia entry SHORT via cond A (era 75)
RSI_EXIT_NEUTRAL: float = 50.0      # target uscita per mean reversion

# RSI soglie extreme — condizione B (RSI estremo, senza BB)
RSI_EXTREME_OVERSOLD: float = 20.0   # LONG senza BB se RSI < questa soglia
RSI_EXTREME_OVERBOUGHT: float = 80.0 # SHORT senza BB se RSI > questa soglia

# Volume filter ratio — volume >= volume_ma * ratio
VOLUME_FILTER_RATIO: float = 0.8    # rilassato del 20% rispetto alla MA

# --- Sentiment ---
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
SENTIMENT_MODEL: str = "claude-sonnet-4-20250514"
SENTIMENT_THRESHOLD: float = 0.3  # Score minimo per conferma
SENTIMENT_COOLDOWN_MIN: int = 15  # minuti minimo tra chiamate sentiment

# --- Risk Management ---
STOP_LOSS_PCT: float = 0.5   # fallback SL% quando ATR non disponibile
TAKE_PROFIT_PCT: float = 1.0  # fallback TP% quando ATR non disponibile
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
