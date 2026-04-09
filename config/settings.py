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
ADX_TREND_THRESHOLD: float = 30.0  # era 25 — alzato perché BTC ha ADX medio ~28

# RSI soglie entry — condizione A (RSI moderato + BB)
RSI_ENTRY_OVERSOLD: float = 32.0    # era 30 — lieve rilassamento
RSI_ENTRY_OVERBOUGHT: float = 68.0  # era 70 — lieve rilassamento
RSI_EXIT_NEUTRAL: float = 50.0      # target uscita per mean reversion

# RSI soglie extreme — condizione B (RSI estremo, senza BB)
RSI_EXTREME_OVERSOLD: float = 22.0   # era 20 — lieve rilassamento
RSI_EXTREME_OVERBOUGHT: float = 78.0 # era 80 — lieve rilassamento

# Volume filter ratio — volume >= volume_ma * ratio
VOLUME_FILTER_RATIO: float = 0.8    # rilassato del 20% rispetto alla MA

# Trend following — RSI pullback zones (usate quando ADX > ADX_TREND_THRESHOLD)
TREND_RSI_PULLBACK_BULL_MIN: float = 40.0  # RSI min per pullback long in uptrend
TREND_RSI_PULLBACK_BULL_MAX: float = 55.0  # RSI max per pullback long in uptrend
TREND_RSI_PULLBACK_BEAR_MIN: float = 45.0  # RSI min per pullback short in downtrend
TREND_RSI_PULLBACK_BEAR_MAX: float = 60.0  # RSI max per pullback short in downtrend

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

# --- Higher Timeframe Filter (1h) ---
HTF_TIMEFRAME: str = "1h"
HTF_CANDLES: int = 50  # quante candele 1h scaricare (50 = ~2 giorni, abbastanza per EMA 21)
HTF_RSI_OVERBOUGHT: float = 65.0  # RSI 1h sopra questo → blocca LONG mean reversion
HTF_RSI_OVERSOLD: float = 35.0    # RSI 1h sotto questo → blocca SHORT mean reversion

# --- Exit intelligenti ---
PARTIAL_TP_RATIO: float = 0.5       # chiudi metà posizione al 50% del percorso verso TP
PARTIAL_TP_SIZE_RATIO: float = 0.5   # percentuale della posizione da chiudere (50%)
RSI_EXIT_MEAN_REVERSION: float = 50.0  # RSI target per uscita mean reversion

# --- Notifiche ---
SLACK_WEBHOOK_URL: str = os.getenv("SLACK_WEBHOOK_URL", "")

# --- Live ---
LIVE_CAPITAL_USDT: float = 50.0  # capitale allocato per live trading
KILL_SWITCH_PATH: str = "data/kill.flag"
