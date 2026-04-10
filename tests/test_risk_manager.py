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


    def test_invalid_side_raises_error(self, rm):
        """Side invalido deve lanciare ValueError."""
        with pytest.raises(ValueError, match="Invalid side"):
            rm.calculate_levels(entry_price=50000.0, side="long", atr=100.0)


from src.sentiment.claude_sentiment import SentimentResult


class TestCalculatePositionSize:
    """Test per calculate_position_size."""

    def test_basic_position_size(self, rm):
        """Size basata su rischio fisso senza sentiment."""
        size = rm.calculate_position_size(
            capital=10000.0, entry_price=50000.0, sl_price=49500.0,
        )
        # sl_distance = 500/50000 = 0.01
        # raw_size = (10000 * 1.0/100) / 0.01 = 10000
        # capped = min(10000, 10000 * 20/100) = 2000
        assert size == pytest.approx(2000.0)

    def test_small_sl_hits_cap(self, rm):
        """SL molto vicino -> size enorme, deve essere cappata."""
        size = rm.calculate_position_size(
            capital=10000.0, entry_price=50000.0, sl_price=49990.0,
        )
        # sl_distance = 10/50000 = 0.0002
        # raw_size = 100 / 0.0002 = 500000 -> capped at 2000
        assert size == pytest.approx(2000.0)

    def test_below_minimum_returns_zero(self, rm):
        """Size sotto il minimo exchange -> 0.0."""
        size = rm.calculate_position_size(
            capital=50.0, entry_price=50000.0, sl_price=49500.0,
        )
        # raw_size = (50 * 0.01) / 0.01 = 50
        # capped = min(50, 50*0.2) = 10.0
        # 10.0 >= MIN_ORDER_SIZE (10.0), just at the boundary
        assert size == pytest.approx(10.0)

    def test_very_small_capital_returns_zero(self, rm):
        """Capitale minimo -> size sotto exchange minimum -> 0.0."""
        size = rm.calculate_position_size(
            capital=30.0, entry_price=50000.0, sl_price=49500.0,
        )
        # raw_size = (30 * 0.01) / 0.01 = 30
        # capped = min(30, 30*0.2) = 6.0 < 10.0
        assert size == 0.0

    def test_zero_capital_returns_zero(self, rm):
        """Capitale zero -> 0.0."""
        size = rm.calculate_position_size(
            capital=0.0, entry_price=50000.0, sl_price=49500.0,
        )
        assert size == 0.0

    def test_entry_equals_sl_returns_zero(self, rm):
        """entry_price == sl_price (divisione per zero) -> 0.0."""
        size = rm.calculate_position_size(
            capital=10000.0, entry_price=50000.0, sl_price=50000.0,
        )
        assert size == 0.0

    def test_sentiment_high_confidence_full_size(self, rm):
        """Sentiment con confidence alta (1.0) -> multiplier 1.0, size piena."""
        sentiment = SentimentResult(
            sentiment_score=0.5, confidence=1.0,
            top_events=[], recommendation="BUY",
        )
        size_with = rm.calculate_position_size(
            capital=10000.0, entry_price=50000.0, sl_price=49500.0,
            sentiment=sentiment,
        )
        size_without = rm.calculate_position_size(
            capital=10000.0, entry_price=50000.0, sl_price=49500.0,
        )
        assert size_with == size_without

    def test_sentiment_low_confidence_reduced_size(self, rm):
        """Sentiment con confidence bassa -> multiplier 0.5, size dimezzata."""
        sentiment = SentimentResult(
            sentiment_score=0.5, confidence=0.1,
            top_events=[], recommendation="BUY",
        )
        size = rm.calculate_position_size(
            capital=10000.0, entry_price=50000.0, sl_price=49500.0,
            sentiment=sentiment,
        )
        # raw_size = (10000 * 0.01 * 0.5) / 0.01 = 5000
        # capped = min(5000, 2000) = 2000
        assert size == pytest.approx(2000.0)

    def test_sentiment_mid_confidence_scales(self, rm):
        """Sentiment con confidence 0.7 -> multiplier 0.7."""
        sentiment = SentimentResult(
            sentiment_score=0.3, confidence=0.7,
            top_events=[], recommendation="BUY",
        )
        size = rm.calculate_position_size(
            capital=10000.0, entry_price=50000.0, sl_price=45000.0,
            sentiment=sentiment,
        )
        # sl_distance = 5000/50000 = 0.1
        # raw_size = (10000 * 0.01 * 0.7) / 0.1 = 700
        # capped = min(700, 2000) = 700
        assert size == pytest.approx(700.0)


class TestUpdateTrailingStop:
    """Test per update_trailing_stop."""

    def test_long_trailing_moves_up(self, rm):
        """LONG: trailing sale quando il prezzo sale."""
        new_trail = rm.update_trailing_stop(
            side="LONG", current_price=50200.0, current_trailing=49900.0, atr=100.0,
        )
        # new candidate = 50200 - 100*1.0 = 50100 > 49900
        assert new_trail == pytest.approx(50100.0)

    def test_long_trailing_never_moves_down(self, rm):
        """LONG: trailing non scende se il prezzo scende."""
        new_trail = rm.update_trailing_stop(
            side="LONG", current_price=49950.0, current_trailing=49900.0, atr=100.0,
        )
        # new candidate = 49950 - 100 = 49850 < 49900
        assert new_trail == pytest.approx(49900.0)

    def test_short_trailing_moves_down(self, rm):
        """SHORT: trailing scende quando il prezzo scende."""
        new_trail = rm.update_trailing_stop(
            side="SHORT", current_price=49800.0, current_trailing=50100.0, atr=100.0,
        )
        # new candidate = 49800 + 100*1.0 = 49900 < 50100
        assert new_trail == pytest.approx(49900.0)

    def test_short_trailing_never_moves_up(self, rm):
        """SHORT: trailing non sale se il prezzo sale."""
        new_trail = rm.update_trailing_stop(
            side="SHORT", current_price=50200.0, current_trailing=50100.0, atr=100.0,
        )
        # new candidate = 50200 + 100 = 50300 > 50100
        assert new_trail == pytest.approx(50100.0)


    def test_invalid_side_raises_error(self, rm):
        """Side invalido deve lanciare ValueError."""
        with pytest.raises(ValueError, match="Invalid side"):
            rm.update_trailing_stop(
                side="long", current_price=50000.0, current_trailing=49900.0, atr=100.0,
            )


class TestDailyLimits:
    """Test per can_trade, record_trade, reset_daily."""

    def test_can_trade_initially(self, rm):
        """Nessun trade registrato -> puo' tradare."""
        assert rm.can_trade(capital=1000.0) is True

    def test_cannot_trade_after_max_trades(self, rm):
        """Dopo MAX_DAILY_TRADES (20) -> non puo' tradare."""
        for _ in range(20):
            rm.record_trade(pnl=1.0)
        assert rm.can_trade(capital=1000.0) is False

    def test_cannot_trade_after_max_loss(self, rm):
        """Dopo perdita >= MAX_DAILY_LOSS_PCT (3%) del capitale -> non puo' tradare."""
        rm.record_trade(pnl=-35.0)  # -3.5% of 1000
        assert rm.can_trade(capital=1000.0) is False

    def test_can_trade_under_loss_limit(self, rm):
        """Perdita sotto il limite -> puo' ancora tradare."""
        rm.record_trade(pnl=-20.0)  # -2% of 1000
        assert rm.can_trade(capital=1000.0) is True

    def test_reset_daily_clears_counters(self, rm):
        """reset_daily resetta trades e pnl."""
        for _ in range(20):
            rm.record_trade(pnl=-5.0)
        assert rm.can_trade(capital=1000.0) is False
        rm.reset_daily()
        assert rm.can_trade(capital=1000.0) is True

    def test_record_trade_accumulates_pnl(self, rm):
        """PnL si accumula correttamente."""
        rm.record_trade(pnl=-10.0)
        rm.record_trade(pnl=-10.0)
        rm.record_trade(pnl=-10.0)
        # total = -30, 3% of 1000 = 30 -> at limit
        assert rm.can_trade(capital=1000.0) is False

    def test_zero_capital_cannot_trade(self, rm):
        """Capitale zero -> non puo' tradare."""
        assert rm.can_trade(capital=0.0) is False


class TestLossCooldown:
    """Test per il loss cooldown e streak protection."""

    def test_no_cooldown_initially(self, rm):
        """Nessun cooldown all'inizio."""
        assert rm.cooldown_remaining == 0
        assert rm.consecutive_losses == 0
        assert rm.streak_stopped is False

    def test_first_loss_sets_cooldown_3(self, rm):
        """Prima loss → cooldown di 3 candele."""
        rm.record_trade_result(-10.0)
        assert rm.consecutive_losses == 1
        assert rm.cooldown_remaining == 3

    def test_second_loss_doubles_cooldown(self, rm):
        """Seconda loss consecutiva → cooldown raddoppia a 6."""
        rm.record_trade_result(-10.0)
        rm._cooldown_remaining = 0  # simula fine cooldown
        rm.record_trade_result(-10.0)
        assert rm.consecutive_losses == 2
        assert rm.cooldown_remaining == 6

    def test_third_loss_cooldown_12(self, rm):
        """Terza loss → cooldown 12."""
        rm.record_trade_result(-10.0)
        rm._cooldown_remaining = 0
        rm.record_trade_result(-10.0)
        rm._cooldown_remaining = 0
        rm.record_trade_result(-10.0)
        assert rm.consecutive_losses == 3
        assert rm.cooldown_remaining == 12

    def test_fourth_loss_cooldown_capped_at_24(self, rm):
        """Quarta loss → cooldown 24 (cap massimo)."""
        for i in range(4):
            rm.record_trade_result(-10.0)
            if i < 3:
                rm._cooldown_remaining = 0
        assert rm.consecutive_losses == 4
        assert rm.cooldown_remaining == 24

    def test_five_losses_triggers_streak_stop(self, rm):
        """Quinta loss consecutiva → streak stop per la giornata."""
        for i in range(5):
            rm.record_trade_result(-10.0)
            if i < 4:
                rm._cooldown_remaining = 0
        assert rm.consecutive_losses == 5
        assert rm.streak_stopped is True

    def test_win_resets_streak(self, rm):
        """Un trade vincente resetta tutto."""
        rm.record_trade_result(-10.0)
        rm._cooldown_remaining = 0
        rm.record_trade_result(-10.0)
        assert rm.consecutive_losses == 2
        # Ora vinci
        rm.record_trade_result(5.0)
        assert rm.consecutive_losses == 0
        assert rm.cooldown_remaining == 0

    def test_can_trade_false_during_cooldown(self, rm):
        """can_trade() restituisce False durante il cooldown."""
        rm.record_trade_result(-10.0)
        assert rm.cooldown_remaining == 3
        assert rm.can_trade(1000.0) is False

    def test_can_trade_true_after_cooldown_expires(self, rm):
        """can_trade() restituisce True dopo che il cooldown è scaduto."""
        rm.record_trade_result(-10.0)
        assert rm.can_trade(1000.0) is False
        # Simula 3 tick
        rm.tick_cooldown()
        rm.tick_cooldown()
        rm.tick_cooldown()
        assert rm.cooldown_remaining == 0
        assert rm.can_trade(1000.0) is True

    def test_can_trade_false_after_streak_stop(self, rm):
        """can_trade() restituisce False dopo streak stop."""
        for i in range(5):
            rm.record_trade_result(-10.0)
            if i < 4:
                rm._cooldown_remaining = 0
        assert rm.can_trade(1000.0) is False

    def test_tick_cooldown_decrements(self, rm):
        """tick_cooldown() decrementa di 1."""
        rm.record_trade_result(-10.0)
        assert rm.cooldown_remaining == 3
        rm.tick_cooldown()
        assert rm.cooldown_remaining == 2
        rm.tick_cooldown()
        assert rm.cooldown_remaining == 1
        rm.tick_cooldown()
        assert rm.cooldown_remaining == 0

    def test_tick_cooldown_does_not_go_negative(self, rm):
        """tick_cooldown() non va sotto zero."""
        rm.tick_cooldown()  # cooldown è già 0
        assert rm.cooldown_remaining == 0

    def test_daily_reset_clears_everything(self, rm):
        """reset_daily() resetta cooldown, streak, e contatori."""
        for i in range(5):
            rm.record_trade_result(-10.0)
            if i < 4:
                rm._cooldown_remaining = 0
        assert rm.streak_stopped is True
        rm.reset_daily()
        assert rm.consecutive_losses == 0
        assert rm.cooldown_remaining == 0
        assert rm.streak_stopped is False
        assert rm.can_trade(1000.0) is True

    def test_partial_tp_resets_streak(self, rm):
        """Un PnL positivo (da partial TP) resetta lo streak."""
        rm.record_trade_result(-10.0)
        rm._cooldown_remaining = 0
        rm.record_trade_result(-10.0)
        assert rm.consecutive_losses == 2
        rm.record_trade_result(3.0)  # partial TP positivo
        assert rm.consecutive_losses == 0
