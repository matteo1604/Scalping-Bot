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
Approccio multi-indicatore combinato:
1. **EMA Crossover** → direzione del trend (EMA 9 / EMA 21)
2. **RSI** → filtro (evita overbought/oversold)
3. **Volume** → conferma (volume sopra la media = segnale valido)
4. **Claude AI Sentiment** → filtro finale prima dell'esecuzione

### Logica dei Segnali
- **LONG:** EMA9 incrocia sopra EMA21 + RSI < 70 + Volume sopra media + Sentiment positivo
- **SHORT:** EMA9 incrocia sotto EMA21 + RSI > 30 + Volume sopra media + Sentiment negativo
- Il sentiment AI agisce come filtro e modificatore del position sizing, NON come segnale standalone

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
