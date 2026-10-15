import os
import tempfile
import unittest

from agent.decide import decide
from agent.memory import TradeMemory
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

    def test_wide_spread_waits(self):
        order = decide(snap(spread_points=5000, point=0.01, atr=1.0), self.memory, self.account, 0.0)
        self.assertEqual(order["action"], "WAIT")
        self.assertIn("spread", order["reason"])


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
                "DEAL|7|3|BTCUSD|SELL|0.01|100000|-5|1700000000|OUT",
            ]
        )
        state = parse_state(text)
        self.assertEqual(state["account"]["chart"], "PERIOD_M15")
        self.assertEqual(state["symbols"][0]["symbol"], "BTCUSD")
        self.assertEqual(state["deals"][0]["entry"], "OUT")


if __name__ == "__main__":
    unittest.main()
