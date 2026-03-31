"""Integrazione Claude API per analisi sentiment in tempo reale.

Responsabilità:
- Chiamare Claude API con web search abilitato
- Richiedere analisi sentiment su BTC/crypto
- Parsare risposta JSON: sentiment_score, confidence, top_events, recommendation
- Gestire errori, timeout e rate limits
"""

import json
import re
import time
from dataclasses import dataclass, field

from anthropic import Anthropic

from config.settings import ANTHROPIC_API_KEY, SENTIMENT_COOLDOWN_MIN, SENTIMENT_MODEL
from src.utils.logger import setup_logger

logger = setup_logger("sentiment")

_SENTIMENT_PROMPT = """Analyze the current Bitcoin/crypto market sentiment based on the latest news and data.
You MUST use the web search tool to find the most recent information.

After searching, respond with ONLY a JSON object in this exact format (no other text):
{
  "sentiment_score": <float from -1.0 (very bearish) to 1.0 (very bullish)>,
  "confidence": <float from 0.0 to 1.0>,
  "top_events": [<list of 1-3 key events driving sentiment>],
  "recommendation": "<BUY | SELL | HOLD>"
}"""


@dataclass
class SentimentResult:
    """Risultato dell'analisi sentiment.

    Attributes:
        sentiment_score: Da -1.0 (bearish) a 1.0 (bullish).
        confidence: Da 0.0 a 1.0.
        top_events: Lista eventi rilevanti.
        recommendation: BUY, SELL, o HOLD.
    """

    sentiment_score: float
    confidence: float
    top_events: list[str] = field(default_factory=list)
    recommendation: str = "HOLD"

    @classmethod
    def from_dict(cls, data: dict) -> "SentimentResult":
        """Crea un SentimentResult da un dizionario.

        Gestisce dati mancanti o invalidi restituendo valori neutri.

        Args:
            data: Dict con chiavi sentiment_score, confidence, top_events, recommendation.

        Returns:
            SentimentResult validato.
        """
        try:
            score = float(data["sentiment_score"])
            score = max(-1.0, min(1.0, score))
            confidence = float(data["confidence"])
            confidence = max(0.0, min(1.0, confidence))
            top_events = data.get("top_events", [])
            if not isinstance(top_events, list):
                top_events = []
            recommendation = data.get("recommendation", "HOLD")
            if recommendation not in ("BUY", "SELL", "HOLD"):
                recommendation = "HOLD"
            return cls(
                sentiment_score=score,
                confidence=confidence,
                top_events=top_events,
                recommendation=recommendation,
            )
        except (KeyError, TypeError, ValueError):
            return cls(sentiment_score=0.0, confidence=0.0, recommendation="HOLD")

    @classmethod
    def neutral(cls) -> "SentimentResult":
        """Restituisce un risultato neutro (fallback)."""
        return cls(sentiment_score=0.0, confidence=0.0, recommendation="HOLD")

    def is_bullish(self, threshold: float = 0.3, min_confidence: float = 0.0) -> bool:
        """Verifica se il sentiment e' bullish.

        Args:
            threshold: Soglia minima di score per essere bullish.
            min_confidence: Confidence minima richiesta.

        Returns:
            True se bullish con confidence sufficiente.
        """
        return self.sentiment_score >= threshold and self.confidence >= min_confidence

    def is_bearish(self, threshold: float = 0.3, min_confidence: float = 0.0) -> bool:
        """Verifica se il sentiment e' bearish.

        Args:
            threshold: Soglia minima di |score| per essere bearish.
            min_confidence: Confidence minima richiesta.

        Returns:
            True se bearish con confidence sufficiente.
        """
        return self.sentiment_score <= -threshold and self.confidence >= min_confidence


class ClaudeSentiment:
    """Client per analisi sentiment tramite Claude API con web search.

    Args:
        api_key: Anthropic API key.
        model: Modello Claude da usare.
    """

    def __init__(
        self,
        api_key: str = ANTHROPIC_API_KEY,
        model: str = SENTIMENT_MODEL,
        cooldown_minutes: int = SENTIMENT_COOLDOWN_MIN,
    ) -> None:
        self._client = Anthropic(api_key=api_key)
        self._model = model
        self._cooldown_seconds = cooldown_minutes * 60
        self._last_result: SentimentResult | None = None
        self._last_call_time: float = 0.0

    def analyze(self, symbol: str = "BTC") -> SentimentResult:
        """Esegue l'analisi sentiment tramite Claude API.

        Usa un cooldown cache: se l'ultima chiamata e' avvenuta meno di
        cooldown_seconds fa, restituisce il risultato cached.

        Args:
            symbol: Simbolo crypto da analizzare.

        Returns:
            SentimentResult con score, confidence, eventi e raccomandazione.
        """
        now = time.time()
        if self._last_result is not None and (now - self._last_call_time) < self._cooldown_seconds:
            remaining = self._cooldown_seconds - (now - self._last_call_time)
            logger.info("Sentiment cache hit (%.0fs remaining)", remaining)
            return self._last_result

        try:
            message = self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                tools=[{
                    "type": "web_search_20250305",
                    "name": "web_search",
                }],
                messages=[{
                    "role": "user",
                    "content": _SENTIMENT_PROMPT.replace("Bitcoin", symbol),
                }],
            )

            # Estrai il testo dalla risposta (ignora blocchi web search)
            text = ""
            for block in message.content:
                if block.type == "text":
                    text += block.text

            data = self._extract_json(text)
            result = SentimentResult.from_dict(data)
            logger.info(
                "Sentiment %s: score=%.2f confidence=%.2f rec=%s",
                symbol, result.sentiment_score, result.confidence, result.recommendation,
            )
            self._last_result = result
            self._last_call_time = now
            return result

        except Exception as e:
            logger.error("Errore analisi sentiment: %s", e)
            return SentimentResult.neutral()

    @staticmethod
    def _extract_json(text: str) -> dict:
        """Estrae un oggetto JSON dal testo della risposta.

        Cerca JSON in blocchi ```json ... ``` oppure come oggetto standalone.

        Args:
            text: Testo della risposta Claude.

        Returns:
            Dict parsato dal JSON trovato.
        """
        # Prova blocco ```json ... ```
        match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))

        # Prova JSON standalone
        match = re.search(r"\{[^{}]*\"sentiment_score\"[^{}]*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))

        # Prova tutto il testo come JSON
        return json.loads(text.strip())
