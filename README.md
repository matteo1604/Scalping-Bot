# Scalping Bot — BTC/USDT

Bot di trading automatico per scalping su Binance con analisi tecnica multi-indicatore e sentiment AI (Claude API).

## Quick Start

```bash
# 1. Clona e entra nella directory
cd scalping-bot

# 2. Crea virtual environment
python -m venv venv
source venv/bin/activate

# 3. Installa dipendenze
pip install -r requirements.txt

# 4. Configura le API key
cp .env.example .env
# Modifica .env con le tue chiavi

# 5. Avvia in paper mode
python -m src.main --mode paper
```

## Strategia

| Indicatore | Ruolo | Parametri |
|---|---|---|
| EMA 9/21 | Direzione trend | Crossover |
| RSI(14) | Filtro | 30-70 range |
| Volume | Conferma | Sopra media 20 periodi |
| Claude AI | Sentiment filter | Score -1.0 / +1.0 |

## Struttura Progetto

Vedi `CLAUDE.md` per l'architettura completa e il piano di sviluppo.

## Disclaimer

Questo bot è a scopo educativo. Il trading di criptovalute comporta rischi significativi. Non investire più di quanto puoi permetterti di perdere.
