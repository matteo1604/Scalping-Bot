"""Test per il modulo sentiment Claude API."""

import json
import pytest
from unittest.mock import MagicMock, patch

from src.sentiment.claude_sentiment import ClaudeSentiment, SentimentResult


class TestSentimentResult:
    """Test per il dataclass SentimentResult."""

    def test_create_from_dict(self):
        """Deve creare un SentimentResult da un dict valido."""
        data = {
            "sentiment_score": 0.6,
            "confidence": 0.8,
            "top_events": ["BTC ETF inflows record"],
            "recommendation": "BUY",
        }
        result = SentimentResult.from_dict(data)
        assert result.sentiment_score == 0.6
        assert result.confidence == 0.8
        assert result.recommendation == "BUY"
        assert len(result.top_events) == 1

    def test_from_dict_clamps_score(self):
        """Score deve essere clampato tra -1 e 1."""
        data = {
            "sentiment_score": 2.5,
            "confidence": 0.8,
            "top_events": [],
            "recommendation": "BUY",
        }
        result = SentimentResult.from_dict(data)
        assert result.sentiment_score == 1.0

    def test_from_dict_clamps_negative_score(self):
        """Score negativo deve essere clampato a -1."""
        data = {
            "sentiment_score": -3.0,
            "confidence": 0.5,
            "top_events": [],
            "recommendation": "SELL",
        }
        result = SentimentResult.from_dict(data)
        assert result.sentiment_score == -1.0

    def test_from_dict_invalid_returns_neutral(self):
        """Dict invalido deve restituire un risultato neutro."""
        result = SentimentResult.from_dict({"bad": "data"})
        assert result.sentiment_score == 0.0
        assert result.confidence == 0.0
        assert result.recommendation == "HOLD"

    def test_is_bullish(self):
        """is_bullish con threshold di default (0.3)."""
        result = SentimentResult(
            sentiment_score=0.5, confidence=0.7,
            top_events=[], recommendation="BUY",
        )
        assert result.is_bullish(threshold=0.3) is True

    def test_is_bearish(self):
        """is_bearish con threshold di default (0.3)."""
        result = SentimentResult(
            sentiment_score=-0.5, confidence=0.7,
            top_events=[], recommendation="SELL",
        )
        assert result.is_bearish(threshold=0.3) is True

    def test_not_bullish_low_confidence(self):
        """Score alto ma confidence bassa non deve essere bullish."""
        result = SentimentResult(
            sentiment_score=0.8, confidence=0.2,
            top_events=[], recommendation="BUY",
        )
        assert result.is_bullish(threshold=0.3, min_confidence=0.5) is False


class TestClaudeSentimentAnalyze:
    """Test per ClaudeSentiment.analyze() con mock."""

    @patch("src.sentiment.claude_sentiment.Anthropic")
    def test_analyze_returns_sentiment_result(self, mock_anthropic_cls):
        """analyze() deve restituire un SentimentResult."""
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        # Simula risposta Claude con JSON nel testo
        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = json.dumps({
            "sentiment_score": 0.6,
            "confidence": 0.8,
            "top_events": ["ETF approval news"],
            "recommendation": "BUY",
        })

        mock_message = MagicMock()
        mock_message.content = [mock_text_block]
        mock_client.messages.create.return_value = mock_message

        sentiment = ClaudeSentiment(api_key="test-key")
        result = sentiment.analyze()

        assert isinstance(result, SentimentResult)
        assert result.sentiment_score == 0.6
        assert result.recommendation == "BUY"

    @patch("src.sentiment.claude_sentiment.Anthropic")
    def test_analyze_calls_api_with_web_search(self, mock_anthropic_cls):
        """analyze() deve chiamare l'API con web_search tool."""
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = json.dumps({
            "sentiment_score": 0.0,
            "confidence": 0.5,
            "top_events": [],
            "recommendation": "HOLD",
        })
        mock_message = MagicMock()
        mock_message.content = [mock_text_block]
        mock_client.messages.create.return_value = mock_message

        sentiment = ClaudeSentiment(api_key="test-key")
        sentiment.analyze()

        call_kwargs = mock_client.messages.create.call_args
        tools = call_kwargs.kwargs.get("tools") or call_kwargs[1].get("tools")
        assert any(t.get("type") == "web_search_20250305" for t in tools)

    @patch("src.sentiment.claude_sentiment.Anthropic")
    def test_analyze_returns_neutral_on_api_error(self, mock_anthropic_cls):
        """Se l'API fallisce, deve restituire un risultato neutro."""
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.side_effect = Exception("API error")

        sentiment = ClaudeSentiment(api_key="test-key")
        result = sentiment.analyze()

        assert result.sentiment_score == 0.0
        assert result.confidence == 0.0
        assert result.recommendation == "HOLD"

    @patch("src.sentiment.claude_sentiment.Anthropic")
    def test_analyze_handles_mixed_content_blocks(self, mock_anthropic_cls):
        """Deve estrarre il JSON anche se ci sono altri content block (web search results)."""
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        # Simula content con web_search_tool_result + text
        mock_search_block = MagicMock()
        mock_search_block.type = "server_tool_use"

        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = 'Based on my analysis:\n```json\n{"sentiment_score": -0.3, "confidence": 0.7, "top_events": ["Sell-off"], "recommendation": "SELL"}\n```'

        mock_message = MagicMock()
        mock_message.content = [mock_search_block, mock_text_block]
        mock_client.messages.create.return_value = mock_message

        sentiment = ClaudeSentiment(api_key="test-key")
        result = sentiment.analyze()

        assert result.sentiment_score == -0.3
        assert result.recommendation == "SELL"


class TestSentimentCooldown:
    """Test per il cooldown cache di ClaudeSentiment."""

    @patch("src.sentiment.claude_sentiment.Anthropic")
    @patch("src.sentiment.claude_sentiment.time")
    def test_cache_hit_within_cooldown(self, mock_time, mock_anthropic_cls):
        """Seconda chiamata entro il cooldown deve restituire il risultato cached."""
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = json.dumps({
            "sentiment_score": 0.6, "confidence": 0.8,
            "top_events": ["Rally"], "recommendation": "BUY",
        })
        mock_message = MagicMock()
        mock_message.content = [mock_text_block]
        mock_client.messages.create.return_value = mock_message

        mock_time.time.side_effect = [1000.0, 1500.0]  # 500s < 900s cooldown

        sentiment = ClaudeSentiment(api_key="test-key", cooldown_minutes=15)
        result1 = sentiment.analyze()
        result2 = sentiment.analyze()

        assert result1.sentiment_score == 0.6
        assert result2.sentiment_score == 0.6
        assert mock_client.messages.create.call_count == 1  # solo 1 chiamata API

    @patch("src.sentiment.claude_sentiment.Anthropic")
    @patch("src.sentiment.claude_sentiment.time")
    def test_cache_miss_after_cooldown(self, mock_time, mock_anthropic_cls):
        """Chiamata dopo il cooldown deve fare una nuova richiesta API."""
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = json.dumps({
            "sentiment_score": 0.6, "confidence": 0.8,
            "top_events": ["Rally"], "recommendation": "BUY",
        })
        mock_message = MagicMock()
        mock_message.content = [mock_text_block]
        mock_client.messages.create.return_value = mock_message

        mock_time.time.side_effect = [1000.0, 2000.0]  # 1000s > 900s cooldown

        sentiment = ClaudeSentiment(api_key="test-key", cooldown_minutes=15)
        sentiment.analyze()
        sentiment.analyze()

        assert mock_client.messages.create.call_count == 2  # 2 chiamate API

    @patch("src.sentiment.claude_sentiment.Anthropic")
    def test_first_call_always_hits_api(self, mock_anthropic_cls):
        """Prima chiamata deve sempre fare la richiesta API."""
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = json.dumps({
            "sentiment_score": 0.0, "confidence": 0.5,
            "top_events": [], "recommendation": "HOLD",
        })
        mock_message = MagicMock()
        mock_message.content = [mock_text_block]
        mock_client.messages.create.return_value = mock_message

        sentiment = ClaudeSentiment(api_key="test-key")
        sentiment.analyze()

        assert mock_client.messages.create.call_count == 1
