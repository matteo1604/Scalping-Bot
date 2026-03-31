# Guida Operativa — Scalping Bot BTC/USDT

## Avvio

### Paper mode (soldi finti)
```bash
python -m src.main --mode paper
```
Usa 50 USDT simulati. Nessun ordine reale. Ideale per testare la strategia.

### Live mode (soldi reali)
```bash
python -m src.main --mode live
```
Prima di avviare in live:
- Assicurati di avere almeno 10 USDT su Binance spot
- Verifica che `.env` contenga le API key corrette
- Il bot esegue pre-flight checks automatici (balance, chiavi, connessione)

## Monitoraggio

### Status in tempo reale
```bash
type data\paper_status.json
```
Campi principali:
- `mode` — paper o live
- `position` — posizione aperta (null se nessuna)
- `daily.trades` — numero trade del giorno
- `daily.pnl` — profitto/perdita giornaliero in USDT
- `daily.win_rate` — percentuale trade vincenti
- `last_signal` — ultimo segnale generato (LONG/SHORT/null)
- `last_sentiment` — ultimo risultato sentiment AI

### Log completi
```bash
type logs\bot.log
```
Ogni azione e' loggata con timestamp: aperture, chiusure, PnL, errori.

### Notifiche Slack
Se configurato (`SLACK_WEBHOOK_URL` nel `.env`), ricevi automaticamente:
- Apertura/chiusura posizioni con PnL
- Errori critici
- Kill switch attivato
- Avvio/shutdown del bot

## Spegnimento

### Metodo 1: Ctrl+C
Se il bot gira in primo piano, premi `Ctrl+C`. Si spegne in modo pulito.

### Metodo 2: Kill switch (consigliato da remoto)
```bash
echo kill > data/kill.flag
```
Il bot si ferma al prossimo tick (entro 5 minuti). Per riavviarlo, cancella il file:
```bash
del data\kill.flag
```

## Valutazione risultati

| Metrica | Buono | Preoccupante |
|---------|-------|--------------|
| Win rate | > 50% | < 40% |
| PnL giornaliero | positivo | negativo per 3+ giorni |
| Drawdown | < 3% del capitale | > 5% |

Lascia girare il bot in paper per almeno 3-5 giorni prima di valutare.

## Limiti di sicurezza attivi

- Max 20 trade al giorno
- Max 3% perdita giornaliera (poi si ferma)
- Stop-loss su ogni trade (ATR-based)
- Trailing stop che protegge i profitti
- In live: solo LONG (no SHORT su spot)
- Sentiment AI come filtro aggiuntivo prima di ogni trade

## Risoluzione problemi

### Il bot non parte in live
Controlla il log: `type logs\bot.log`. Cause comuni:
- API key mancanti o errate nel `.env`
- IP non autorizzato su Binance
- Balance sotto 10 USDT
- Kill switch attivo (`data/kill.flag` presente)

### Nessun trade dopo ore
Normale. Il bot opera solo quando tutti i segnali convergono (EMA crossover + RSI + volume + sentiment). In mercati laterali puo' non fare trade per ore.

### Errore "Invalid API-key, IP, or permissions"
Il tuo IP e' cambiato. Vai su Binance → API Management → aggiorna l'IP autorizzato.

## File importanti

```
.env                      # Chiavi API (MAI condividere)
config/settings.py        # Parametri strategia e rischio
data/paper_status.json    # Stato corrente del bot
data/kill.flag            # Crea questo file per fermare il bot
logs/bot.log              # Log completo
```
