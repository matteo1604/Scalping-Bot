# CLAUDE.md — Scalping Bot Project

## Panoramica Progetto
Bot di trading automatico per scalping su criptovalute (Binance), progettato per eseguire molte piccole operazioni e massimizzare i guadagni percentuali. Il bot combina analisi tecnica classica con un layer di sentiment AI in tempo reale tramite Claude API.

## Stack Tecnologico
- **Linguaggio:** Python 3.11+
- **Exchange:** Binance (via ccxt)
- **Librerie principali:** ccxt, pandas, ta (technical analysis), anthropic SDK
- **Pair:** BTC/USDT
- **Timeframe:** 5 minuti

## Strategia di Trading
Approccio **dual-mode** che adatta automaticamente la logica al regime di mercato rilevato dall'ADX:

### Selezione Modalità
- **ADX ≤ 30** → Mean Reversion (mercato laterale)
- **ADX > 30** → Trend Following (mercato in trend)

### Modalità 1: Mean Reversion (ADX ≤ 30)
Entrata su inversioni agli estremi delle Bollinger Bands:
- **LONG cond A:** RSI ≤ 32 + Close ≤ BB_lower + Volume ok
- **LONG cond B:** RSI < 22 (basta da solo) + Volume ok
- **SHORT cond A:** RSI ≥ 68 + Close ≥ BB_upper + Volume ok
- **SHORT cond B:** RSI > 78 (basta da solo) + Volume ok
- Risk management: SL = ATR × 1.5, TP = ATR × 2.0

### Modalità 2: Trend Following (ADX > 30)
Entrata su pullback nella direzione del trend rilevata da DI+/DI-:
- **LONG:** DI+ > DI- AND Close > EMA_slow AND RSI in [40, 55] AND Close > BB_middle + Volume ok
- **SHORT:** DI- > DI+ AND Close < EMA_slow AND RSI in [45, 60] AND Close < BB_middle + Volume ok
- Risk management: SL = ATR × 1.5 × 1.5 (moltiplicatore extra per trend), TP = ATR × 2.0 × 1.5

### Filtro Comune
- **Volume:** volume ≥ volume_ma × 0.8
- **Sentiment AI:** filtro finale — LONG bloccato se bearish forte, SHORT bloccato se bullish forte
- Il sentiment AI agisce come filtro e modificatore del position sizing, NON come segnale standalone
- EMA 9/21 restano calcolati; EMA_slow (21) è usata come riferimento trend in modalità 2

### Filtro Multi-Timeframe (1h)
Il timeframe 1h agisce come semaforo sui segnali del 5min:
- Mean reversion LONG bloccato se RSI 1h ≥ 65 (overbought macro)
- Mean reversion SHORT bloccato se RSI 1h ≤ 35 (oversold macro)
- Trend following LONG permesso solo se trend 1h = UP o NEUTRAL
- Trend following SHORT permesso solo se trend 1h = DOWN o NEUTRAL
- Se il fetch 1h fallisce, il filtro è disattivato (fail-open)
- Ordine filtri: sentiment → HTF → apertura posizione

### Exit Intelligenti
Le posizioni vengono chiuse con logica multi-livello (in ordine di priorità):
1. **Stop Loss** → chiude tutto (priorità massima)
2. **Trailing Stop** → chiude tutto
3. **Partial Take Profit** → al 50% del percorso verso il TP, chiude metà posizione e sposta SL a break-even
4. **Signal Exit** → mean reversion chiude quando RSI torna a 50; trend following chiude quando DI+/DI- si invertono
5. **Take Profit** → chiude tutto il residuo

### Sentiment Engine (Claude API)
Il bot interroga Claude API con web search abilitato prima di ogni trade rilevato dai segnali tecnici. La risposta attesa è un JSON strutturato:
```json
{
  "sentiment_score": 0.6,       // da -1.0 (bearish) a +1.0 (bullish)
  "confidence": 0.8,            // da 0.0 a 1.0
  "top_events": ["..."],        // lista eventi rilevanti
  "recommendation": "BUY"       // BUY | SELL | HOLD
}
```

## Architettura del Progetto
```
scalping-bot/
├── CLAUDE.md              # Questo file
├── README.md              # Documentazione progetto
├── requirements.txt       # Dipendenze Python
├── .env.example           # Template variabili d'ambiente
├── .gitignore
├── config/
│   └── settings.py        # Configurazione centralizzata (pair, timeframe, soglie)
├── src/
│   ├── __init__.py
│   ├── main.py            # Entry point del bot
│   ├── exchange.py        # Connessione e interazione con Binance via ccxt
│   ├── strategies/
│   │   ├── __init__.py
│   │   └── combined.py    # Strategia combinata EMA+RSI+Volume+Sentiment
│   ├── indicators/
│   │   ├── __init__.py
│   │   └── technical.py   # Calcolo indicatori tecnici (EMA, RSI, Volume)
│   ├── sentiment/
│   │   ├── __init__.py
│   │   └── claude_sentiment.py  # Integrazione Claude API per sentiment
│   ├── risk/
│   │   ├── __init__.py
│   │   └── manager.py     # Risk management (stop-loss, take-profit, position sizing)
│   └── utils/
│       ├── __init__.py
│       ├── logger.py      # Logging configurato
│       └── helpers.py     # Funzioni di utilità
├── tests/
│   ├── __init__.py
│   ├── test_exchange.py
│   ├── test_indicators.py
│   ├── test_strategy.py
│   └── test_sentiment.py
├── data/
│   ├── historical/        # Dati OHLCV storici per backtesting
│   └── backtest_results/  # Report dei backtest
├── logs/                  # File di log del bot
└── docs/                  # Documentazione aggiuntiva
```

## Piano di Sviluppo (7 Fasi)

### Fase 1 — Setup Ambiente & Connessione Exchange
- Configurare virtual environment Python
- Installare dipendenze (requirements.txt)
- Implementare `exchange.py`: connessione a Binance, fetch OHLCV, test con API key
- Configurare `.env` con le API key
- Verificare che il fetch dei dati BTC/USDT 5min funzioni

### Fase 2 — Implementazione Strategia Tecnica
- Implementare `indicators/technical.py`: calcolo EMA9, EMA21, RSI(14), Volume MA
- Implementare `strategies/combined.py`: logica di generazione segnali
- Testare i segnali su dati storici scaricati

### Fase 3 — Backtesting
- Creare un modulo di backtesting che simuli l'esecuzione dei segnali su dati storici
- Calcolare metriche: win rate, profit factor, max drawdown, Sharpe ratio
- Salvare report in `data/backtest_results/`

### Fase 4 — Integrazione Claude AI Sentiment
- Implementare `sentiment/claude_sentiment.py` con Anthropic SDK
- Abilitare web search tool nelle chiamate API
- Parsare la risposta JSON strutturata
- Integrare il sentiment come filtro nella strategia combined

### Fase 5 — Risk Management Avanzato
- Implementare `risk/manager.py`: stop-loss dinamico, take-profit, trailing stop
- Position sizing basato su confidence del sentiment + volatilità
- Limiti giornalieri di perdita e numero massimo di trade

### Fase 6 — Paper Trading
- Modalità simulazione con dati live (no ordini reali)
- Logging completo di ogni decisione
- Dashboard minimale per monitoraggio

### Fase 7 — Deploy Live
- Deployment con capitale minimo
- Monitoraggio continuo e alerting
- Kill switch di emergenza

## Convenzioni di Codice
- Python 3.11+, type hints ovunque
- Docstring per ogni funzione/classe
- Logging strutturato (no print)
- Configurazione via environment variables (.env) — MAI hardcodare API key
- Gestione errori robusta con retry per le chiamate API
- Ogni modulo deve essere testabile indipendentemente

## Comandi Utili
```bash
# Setup ambiente
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt

# Eseguire i test
pytest tests/ -v

# Avviare il bot (paper mode)
python -m src.main --mode paper

# Avviare il bot (live mode)
python -m src.main --mode live
```

## Note Importanti
- Il proprietario del progetto (Matteo) ha esperienza intermedia nel trading ma limitata nella selezione di mercati e strategie
- Ogni decisione strategica importante è già stata presa e documentata sopra
- In caso di dubbio, privilegiare SEMPRE la sicurezza (risk management conservativo)
- Il bot deve partire in paper trading PRIMA di qualsiasi operazione live
