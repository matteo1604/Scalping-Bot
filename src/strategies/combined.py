"""Strategia combinata: EMA Crossover + RSI + Volume + Sentiment.

Logica segnali:
- LONG: EMA9 > EMA21 (cross up) + RSI < 70 + Volume > media + Sentiment > threshold
- SHORT: EMA9 < EMA21 (cross down) + RSI > 30 + Volume > media + Sentiment < -threshold
- Il sentiment modifica anche il position sizing
"""

# TODO: Fase 2 — Implementare classe CombinedStrategy
