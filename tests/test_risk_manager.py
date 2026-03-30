"""Test per il modulo risk management."""

import pytest

from src.risk.manager import RiskManager


@pytest.fixture
def rm() -> RiskManager:
    """RiskManager con parametri di default."""
    return RiskManager()


class TestCalculateLevels:
    """Test per calculate_levels (SL/TP/trailing)."""

    def test_long_with_atr(self, rm):
        """LONG: SL sotto entry, TP sopra entry, trailing sotto entry."""
        levels = rm.calculate_levels(entry_price=50000.0, side="LONG", atr=100.0)
        assert levels["stop_loss"] == pytest.approx(50000.0 - 100.0 * 1.5)  # 49850
        assert levels["take_profit"] == pytest.approx(50000.0 + 100.0 * 2.0)  # 50200
        assert levels["trailing_stop"] == pytest.approx(50000.0 - 100.0 * 1.0)  # 49900

    def test_short_with_atr(self, rm):
        """SHORT: SL sopra entry, TP sotto entry, trailing sopra entry."""
        levels = rm.calculate_levels(entry_price=50000.0, side="SHORT", atr=100.0)
        assert levels["stop_loss"] == pytest.approx(50000.0 + 100.0 * 1.5)  # 50150
        assert levels["take_profit"] == pytest.approx(50000.0 - 100.0 * 2.0)  # 49800
        assert levels["trailing_stop"] == pytest.approx(50000.0 + 100.0 * 1.0)  # 50100

    def test_fallback_without_atr(self, rm):
        """Senza ATR, usa percentuali fisse da settings."""
        levels = rm.calculate_levels(entry_price=50000.0, side="LONG", atr=None)
        # STOP_LOSS_PCT=0.5%, TAKE_PROFIT_PCT=1.0%
        assert levels["stop_loss"] == pytest.approx(50000.0 * (1 - 0.5 / 100))  # 49750
        assert levels["take_profit"] == pytest.approx(50000.0 * (1 + 1.0 / 100))  # 50500
        assert levels["trailing_stop"] == pytest.approx(50000.0 * (1 - 0.5 / 100))  # 49750 (same as SL)

    def test_fallback_with_zero_atr(self, rm):
        """ATR=0 deve usare fallback percentuale."""
        levels = rm.calculate_levels(entry_price=50000.0, side="LONG", atr=0.0)
        assert levels["stop_loss"] == pytest.approx(50000.0 * (1 - 0.5 / 100))

    def test_short_fallback_without_atr(self, rm):
        """SHORT senza ATR usa percentuali fisse invertite."""
        levels = rm.calculate_levels(entry_price=50000.0, side="SHORT", atr=None)
        assert levels["stop_loss"] == pytest.approx(50000.0 * (1 + 0.5 / 100))  # 50250
        assert levels["take_profit"] == pytest.approx(50000.0 * (1 - 1.0 / 100))  # 49500
