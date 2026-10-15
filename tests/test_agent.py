import os
import tempfile
import unittest

from datetime import datetime, timedelta, timezone

from agent.decide import decide
from agent.memory import TradeMemory
from agent.price_action import find_setups
from agent.news import blocking_event
from agent.record import LONG_RECORD, SetupRecord, adjusted_confidence, key_from_setup, setup_key
from agent.reflect import reflect_closed_deals
from agent.risk import lots_for_stop, risk_fraction
from agent.state import month_return, parse_state
from seed_engine import seed


def snap(**overrides):
    base = {
        "symbol": "EURUSD",
        "timeframe": "PERIOD_M15",
        "bid": 1.1000,
        "ask": 1.1002,
        "point": 0.00001,
        "digits": 5,
        "vol_min": 0.01,
        "vol_max": 50.0,
        "vol_step": 0.01,
        "spread_points": 20,
        "atr": 0.0010,
        "ema200": 1.0900,
        "macd": 0.0004,
        "macd_signal": 0.0001,
        "rsi": 55,
        "tick_value": 1.0,
        "tick_size": 0.00001,
    }
    base.update(overrides)
    return base


class RiskTests(unittest.TestCase):
    def test_losing_month_does_not_raise_risk(self):
        self.assertEqual(risk_fraction(0.8), risk_fraction(0.8))

    def test_lot_never_exceeds_broker_max(self):
        lots = lots_for_stop(
            balance=1_000_000,
            confidence=1.0,
            sl_distance=0.0001,
            tick_size=0.00001,
            tick_value=1.0,
            vol_min=0.01,
            vol_max=2.0,
            vol_step=0.01,
        )
        self.assertLessEqual(lots, 2.0)

    def test_refuses_when_minimum_lot_risks_too_much(self):
        lots = lots_for_stop(
            balance=100,
            confidence=0.2,
            sl_distance=5000,
            tick_size=0.01,
            tick_value=1.0,
            vol_min=0.01,
            vol_max=100,
            vol_step=0.01,
        )
        self.assertIsNone(lots)

    def test_missing_stop_distance_refuses(self):
        self.assertIsNone(
            lots_for_stop(10000, 0.7, 0.0, 0.01, 1.0, 0.01, 50, 0.01)
        )


class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        seed(self.tmp.name)
        self.memory = TradeMemory(self.tmp.name)
        self.account = {"balance": 10000, "equity": 10000, "free_margin": 9000, "currency": "GBP"}

    def tearDown(self):
        self.tmp.cleanup()

    def test_order_always_has_a_stop(self):
        order = decide(snap(), self.memory, self.account, 0.0)
        self.assertEqual(order["action"], "BUY")
        self.assertLess(order["stop_loss"], snap()["bid"])
        self.assertGreater(order["lot_size"], 0)

    def test_no_trade_without_agreement(self):
        order = decide(snap(bid=1.0800, ask=1.0802, ema200=1.0900), self.memory, self.account, 0.0)
        self.assertEqual(order["action"], "WAIT")

    def test_stored_loss_blocks_the_same_setup(self):
        first = decide(snap(), self.memory, self.account, 0.0)
        self.memory.add(
            "loss_test",
            "Do not repeat this EURUSD setup. It hit the hard stop and lost -25.00. Setup: " + first["setup"],
            {"type": "stop_loss", "pair": "EURUSD"},
        )
        second = decide(snap(), self.memory, self.account, -0.04)
        self.assertEqual(second["action"], "WAIT")
        self.assertIn("blocked by a stored loss", second["reason"])

    def test_a_down_month_does_not_change_the_lot(self):
        ahead = decide(snap(), self.memory, self.account, 0.12)
        behind = decide(snap(), self.memory, self.account, -0.08)
        self.assertEqual(ahead["lot_size"], behind["lot_size"])

    def test_higher_timeframe_can_veto(self):
        higher = snap(timeframe="PERIOD_H4", bid=1.0800, ask=1.0802, ema200=1.0900, macd=-0.0004, macd_signal=-0.0001)
        order = decide(snap(), self.memory, self.account, 0.0, higher=[higher])
        self.assertEqual(order["action"], "WAIT")

    def test_high_impact_news_blocks_that_currency(self):
        when = datetime.now(timezone.utc) + timedelta(minutes=20)
        events = [
            {
                "currency": "USD",
                "title": "CPI m/m",
                "impact": "High",
                "time": when.isoformat(),
                "when": when,
            }
        ]
        reason = blocking_event("EURUSD", events, now=datetime.now(timezone.utc))
        self.assertIn("CPI", reason)
        order = decide(snap(), self.memory, self.account, 0.0, news_block=reason)
        self.assertEqual(order["action"], "WAIT")
        self.assertIn("CPI", order["reason"])
        self.assertEqual(blocking_event("EURGBP", events, now=datetime.now(timezone.utc)), "")

    def test_wide_spread_waits(self):
        order = decide(snap(spread_points=5000, point=0.01, atr=1.0), self.memory, self.account, 0.0)
        self.assertEqual(order["action"], "WAIT")
        self.assertIn("spread", order["reason"])

    def test_pin_at_support_buys_without_a_macd_cross(self):
        bars = _pin_at_support()
        market = snap(bid=1.1028, ask=1.1030, ema200=1.0900, macd=-0.0002, macd_signal=0.0001, rsi=42)
        order = decide(market, self.memory, self.account, 0.0, bars=bars)
        self.assertEqual(order["action"], "BUY")
        self.assertIn("pin bar", order["reason"])
        self.assertLess(order["stop_loss"], market["bid"])

    def test_pin_below_the_average_is_skipped(self):
        bars = _pin_at_support()
        market = snap(bid=1.1028, ask=1.1030, ema200=1.2000, macd=0.0004, macd_signal=0.0001, rsi=42)
        order = decide(market, self.memory, self.account, 0.0, bars=bars)
        self.assertEqual(order["action"], "WAIT")
        self.assertIn("200 EMA", order["reason"])

    def test_buy_and_sell_setups_cancel(self):
        bars = _bullish_gap_and_bearish_engulfing()
        names = {row["name"] for row in find_setups(bars, 0.0010, 1.1030, 1.2000)}
        self.assertIn("fair value gap", names)
        self.assertIn("engulfing", names)
        order = decide(
            snap(bid=1.1030, ask=1.1032, ema200=1.2000, macd=0.0004, macd_signal=0.0001, rsi=48),
            self.memory,
            self.account,
            0.0,
            bars=bars,
        )
        self.assertEqual(order["action"], "WAIT")
        self.assertIn("both", order["reason"])

    def test_return_into_a_bullish_order_block(self):
        bars = _return_to_order_block()
        order = decide(
            snap(bid=1.1012, ask=1.1014, macd=-0.0002, macd_signal=0.0001, rsi=48),
            self.memory,
            self.account,
            0.0,
            bars=bars,
        )
        self.assertEqual(order["action"], "BUY")
        self.assertIn("order block", order["reason"])

    def test_stretched_rsi_blocks_a_trend_buy(self):
        order = decide(snap(rsi=85), self.memory, self.account, 0.0)
        self.assertEqual(order["action"], "WAIT")
        self.assertIn("RSI", order["reason"])


class SetupRecordTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        seed(self.tmp.name)
        self.memory = TradeMemory(self.tmp.name)
        self.record = SetupRecord(self.tmp.name)
        self.account = {"balance": 10000, "equity": 10000, "free_margin": 9000, "currency": "GBP"}

    def tearDown(self):
        self.tmp.cleanup()

    def test_spread_does_not_split_one_setup(self):
        first = decide(snap(spread_points=12), self.memory, self.account, 0.0)
        second = decide(snap(spread_points=18), self.memory, self.account, 0.0)
        self.assertEqual(first["setup_key"], second["setup_key"])
        self.assertEqual(key_from_setup(first["setup"]), first["setup_key"])
        self.assertNotEqual(first["setup"], second["setup"])

    def test_short_record_does_not_change_the_lot(self):
        plain = decide(snap(), self.memory, self.account, 0.0)
        key = plain["setup_key"]
        for index in range(9):
            self.record.note(f"win-{index}", key, True)
        self.record.note("loss-0", key, False)
        counted = decide(snap(), self.memory, self.account, 0.0, record=self.record)
        self.assertEqual(counted["lot_size"], plain["lot_size"])
        self.assertEqual(counted["confidence"], plain["confidence"])
        self.assertIn("record 9/10", counted["reason"])

    def test_long_winning_record_nudges_inside_the_band(self):
        plain = decide(snap(), self.memory, self.account, 0.0)
        key = plain["setup_key"]
        for index in range(LONG_RECORD - 3):
            self.record.note(f"win-{index}", key, True)
        for index in range(3):
            self.record.note(f"loss-{index}", key, False)
        counted = decide(snap(), self.memory, self.account, 0.0, record=self.record)
        self.assertGreater(counted["lot_size"], plain["lot_size"])
        self.assertGreater(counted["confidence"], plain["confidence"])
        fraction = risk_fraction(counted["confidence"])
        self.assertGreaterEqual(fraction, 0.002)
        self.assertLessEqual(fraction, 0.01)

    def test_long_losing_record_shrinks_inside_the_band(self):
        plain = decide(snap(), self.memory, self.account, 0.0)
        key = plain["setup_key"]
        for index in range(LONG_RECORD):
            self.record.note(f"loss-{index}", key, False)
        counted = decide(snap(), self.memory, self.account, 0.0, record=self.record)
        self.assertLess(counted["lot_size"], plain["lot_size"])
        fraction = risk_fraction(counted["confidence"])
        self.assertGreaterEqual(fraction, 0.002)
        self.assertLessEqual(fraction, 0.01)

    def test_even_long_record_leaves_size_alone(self):
        base = 0.62
        self.assertEqual(adjusted_confidence(base, 15, 15), base)
        self.assertEqual(adjusted_confidence(base, 14, 15), base)

    def test_same_deal_is_counted_once_and_a_win_is_not_a_ban(self):
        key = setup_key("EURUSD", "BUY", ["200 EMA and MACD"])
        text = "BUY EURUSD via 200 EMA and MACD. Price is above the 200 EMA and MACD is above its signal. Spread 20 points."
        deals = [
            {"deal": "9", "position": "55", "symbol": "EURUSD", "type": "SELL", "profit": -12.5, "price": 1.1, "entry": "OUT"},
            {"deal": "9", "position": "55", "symbol": "EURUSD", "type": "SELL", "profit": -12.5, "price": 1.1, "entry": "OUT"},
            {"deal": "10", "position": "56", "symbol": "EURUSD", "type": "BUY", "profit": 8.0, "price": 1.2, "entry": "OUT"},
            {"deal": "11", "position": "57", "symbol": "EURUSD", "type": "BUY", "profit": 0.0, "price": 1.2, "entry": "OUT"},
        ]
        setups = {
            "55": {"setup": text.replace("BUY", "SELL"), "key": setup_key("EURUSD", "SELL", ["200 EMA and MACD"])},
            "56": text,
            "57": text,
        }
        log = []
        before = self.memory.collection.count()
        written = reflect_closed_deals(deals, setups, self.memory, self.record, log)
        self.assertEqual(len(written), 1)
        self.assertEqual(self.memory.collection.count(), before + 1)
        self.assertEqual(self.record.stats(setup_key("EURUSD", "SELL", ["200 EMA and MACD"])), (0, 1))
        self.assertEqual(self.record.stats(key), (1, 0))
        again = []
        reflect_closed_deals(deals, {}, self.memory, self.record, again)
        self.assertEqual(again, [])
        self.assertEqual(self.memory.collection.count(), before + 1)
        self.assertEqual(self.record.stats(key), (1, 0))
        reloaded = SetupRecord(self.tmp.name)
        self.assertEqual(reloaded.stats(key), (1, 0))


class MemoryLoopTests(unittest.TestCase):
    def test_loss_is_written_once_and_win_is_not_a_ban(self):
        tmp = tempfile.TemporaryDirectory()
        memory = TradeMemory(tmp.name)
        setups = {"55": "BUY EURUSD while price is above the 200 EMA and MACD is above its signal. Spread 20 points."}
        deals = [
            {"deal": "9", "position": "55", "symbol": "EURUSD", "type": "SELL", "profit": -12.5, "price": 1.1, "entry": "OUT"},
            {"deal": "9", "position": "55", "symbol": "EURUSD", "type": "SELL", "profit": -12.5, "price": 1.1, "entry": "OUT"},
            {"deal": "10", "position": "56", "symbol": "EURUSD", "type": "BUY", "profit": 8.0, "price": 1.2, "entry": "OUT"},
        ]
        setups["56"] = "winning setup"
        written = reflect_closed_deals(deals, setups, memory)
        self.assertEqual(len(written), 1)
        self.assertEqual(memory.collection.count(), 1)
        again = reflect_closed_deals(deals, {}, memory)
        self.assertEqual(len(again), 0)
        self.assertEqual(memory.collection.count(), 1)
        tmp.cleanup()

    def test_month_return_uses_closed_deals_only(self):
        account = {"balance": 11000}
        deals = [
            {"entry": "IN", "profit": 0},
            {"entry": "OUT", "profit": 1000},
        ]
        self.assertAlmostEqual(month_return(account, deals), 0.1)

    def test_state_parser(self):
        text = "\n".join(
            [
                "CHART|PERIOD_M15",
                "ACCOUNT|10000|10020|9000|GBP|100",
                "SYMBOL|BTCUSD|PERIOD_M15|100000|100020|0.01|2|0.01|10|0.01|200|150|99000|1|0.5|55|0.01|0.01",
                "BAR|EURUSD|PERIOD_M15|1.1000|1.1020|1.0990|1.1010",
                "DEAL|7|3|BTCUSD|SELL|0.01|100000|-5|1700000000|OUT",
            ]
        )
        state = parse_state(text)
        self.assertEqual(state["account"]["chart"], "PERIOD_M15")
        self.assertEqual(state["symbols"][0]["symbol"], "BTCUSD")
        self.assertEqual(state["deals"][0]["entry"], "OUT")
        self.assertEqual(state["bars"][0]["close"], 1.1010)


def _bar(open_, high, low, close):
    return {"open": open_, "high": high, "low": low, "close": close}


def _pin_at_support():
    return [
        _bar(1.1030, 1.1040, 1.1020, 1.1025),
        _bar(1.1025, 1.1030, 1.1015, 1.1018),
        _bar(1.1018, 1.1020, 1.1010, 1.1012),
        _bar(1.1012, 1.1015, 1.1000, 1.1008),
        _bar(1.1008, 1.1025, 1.1006, 1.1020),
        _bar(1.1020, 1.1035, 1.1016, 1.1030),
        _bar(1.1030, 1.1040, 1.1024, 1.1036),
        _bar(1.1036, 1.1042, 1.1028, 1.1032),
        _bar(1.1032, 1.1034, 1.1000, 1.1028),
    ]


def _bullish_gap_and_bearish_engulfing():
    return [
        _bar(1.0980, 1.1000, 1.0975, 1.0994),
        _bar(1.0994, 1.1040, 1.0992, 1.1036),
        _bar(1.1036, 1.1070, 1.1050, 1.1064),
        _bar(1.1064, 1.1072, 1.1055, 1.1068),
        _bar(1.1070, 1.1072, 1.1020, 1.1030),
    ]


def _return_to_order_block():
    return [
        _bar(1.1020, 1.1022, 1.0998, 1.1002),
        _bar(1.1002, 1.1010, 1.1000, 1.1008),
        _bar(1.1008, 1.1045, 1.1006, 1.1040),
        _bar(1.1040, 1.1060, 1.1032, 1.1050),
        _bar(1.1050, 1.1052, 1.1004, 1.1012),
    ]


if __name__ == "__main__":
    unittest.main()
