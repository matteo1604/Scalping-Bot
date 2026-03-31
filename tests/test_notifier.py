"""Test per SlackNotifier."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.utils.notifier import SlackNotifier


class TestSlackNotifierInit:
    """Test per inizializzazione SlackNotifier."""

    def test_enabled_with_url(self):
        """Deve essere abilitato se webhook URL fornito."""
        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/test")
        assert notifier.enabled is True

    def test_disabled_with_empty_url(self):
        """Deve essere disabilitato se webhook URL vuoto."""
        notifier = SlackNotifier(webhook_url="")
        assert notifier.enabled is False

    def test_disabled_with_no_url(self):
        """Deve essere disabilitato se webhook URL non fornito."""
        notifier = SlackNotifier()
        assert notifier.enabled is False


class TestSlackNotifierNotify:
    """Test per SlackNotifier.notify()."""

    @patch("src.utils.notifier.urlopen")
    def test_sends_post_request(self, mock_urlopen):
        """Deve inviare POST con payload JSON corretto."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"ok"
        mock_response.__enter__ = lambda s: mock_response
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/test")
        notifier.notify("Test message")

        mock_urlopen.assert_called_once()
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        assert "Test message" in body["text"]

    @patch("src.utils.notifier.urlopen")
    def test_info_level_prefix(self, mock_urlopen):
        """Livello info: prefisso INFO."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"ok"
        mock_response.__enter__ = lambda s: mock_response
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/test")
        notifier.notify("Trade aperto", level="info")

        request = mock_urlopen.call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        assert body["text"] == "[INFO] Trade aperto"

    @patch("src.utils.notifier.urlopen")
    def test_error_level_prefix(self, mock_urlopen):
        """Livello error: prefisso ERROR."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"ok"
        mock_response.__enter__ = lambda s: mock_response
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/test")
        notifier.notify("Ordine fallito", level="error")

        request = mock_urlopen.call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        assert body["text"] == "[ERROR] Ordine fallito"

    @patch("src.utils.notifier.urlopen")
    def test_warning_level_prefix(self, mock_urlopen):
        """Livello warning: prefisso WARNING."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"ok"
        mock_response.__enter__ = lambda s: mock_response
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/test")
        notifier.notify("Kill switch", level="warning")

        request = mock_urlopen.call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        assert body["text"] == "[WARNING] Kill switch"

    def test_no_call_when_disabled(self):
        """Non deve fare nulla se disabilitato."""
        notifier = SlackNotifier(webhook_url="")
        # Non deve lanciare eccezioni
        notifier.notify("This should be silently ignored")

    @patch("src.utils.notifier.urlopen")
    def test_does_not_raise_on_network_error(self, mock_urlopen):
        """Errore di rete non deve propagarsi."""
        mock_urlopen.side_effect = Exception("Connection refused")

        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/test")
        # Non deve lanciare eccezioni
        notifier.notify("Test message")
