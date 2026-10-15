from agent.price_action import find_setups
from agent.record import setup_key
from agent.risk import lots_for_stop

MONTHLY_TARGET = 0.10
REVERSAL_NAMES = {"pin bar", "engulfing", "morning star", "evening star", "retest"}


def setup_text(snap: dict, direction: str, names) -> str:
    ema_side = "above" if snap["bid"] >= snap["ema200"] else "below"
    macd_side = "above" if snap["macd"] >= snap["macd_signal"] else "below"
    listed = ", ".join(names)
    return (
        f"{direction} {snap['symbol']} via {listed}. "
        f"Price is {ema_side} the 200 EMA and MACD is {macd_side} its signal. "
        f"Spread {int(snap['spread_points'])} points."
    )


def _direction(snap: dict):
    if snap["bid"] > snap["ema200"] and snap["macd"] > snap["macd_signal"]:
        return "BUY"
    if snap["bid"] < snap["ema200"] and snap["macd"] < snap["macd_signal"]:
        return "SELL"
    return None


def _sl_tp(direction: str, snap: dict, stop_price=None):
    distance = 1.5 * snap["atr"]
    if stop_price is not None and snap["atr"] > 0:
        if direction == "BUY":
            raw = snap["bid"] - stop_price
        else:
            raw = stop_price - snap["ask"]
        if raw > snap["point"] * 5:
            padded = raw + 0.15 * snap["atr"]
            distance = min(max(padded, 0.8 * snap["atr"]), 2.5 * snap["atr"])
    target = max(3.0 * snap["atr"], distance * 2.0)
    if direction == "BUY":
        sl = snap["bid"] - distance
        tp = snap["ask"] + target
    else:
        sl = snap["ask"] + distance
        tp = snap["bid"] - target
    return sl, tp, distance


def _higher_blocks(direction: str, higher: list) -> str:
    for other in higher or []:
        other_direction = _direction(other)
        if other_direction and other_direction != direction:
            return other.get("timeframe", "higher")
    return ""


def _candidate_names(snap: dict, bars):
    trend = _direction(snap)
    patterns = find_setups(bars or [], snap["atr"], snap["bid"], snap["ema200"])
    buys = ["200 EMA and MACD"] if trend == "BUY" else []
    sells = ["200 EMA and MACD"] if trend == "SELL" else []
    buy_stops = []
    sell_stops = []
    for row in patterns:
        if row["direction"] == "BUY":
            buys.append(row["name"])
            buy_stops.append(row["stop_price"])
        else:
            sells.append(row["name"])
            sell_stops.append(row["stop_price"])
    return buys, sells, buy_stops, sell_stops


def _with_average(direction: str, snap: dict) -> bool:
    if direction == "BUY":
        return snap["bid"] > snap["ema200"]
    return snap["bid"] < snap["ema200"]


def _higher_agrees(direction: str, higher) -> bool:
    agreed = []
    for other in higher or []:
        other_direction = _direction(other)
        if other_direction:
            agreed.append(other_direction)
    return bool(agreed) and all(item == direction for item in agreed)


def _rsi_blocks(direction: str, rsi: float, names) -> bool:
    if direction == "BUY" and rsi >= 80:
        return True
    if direction == "SELL" and rsi <= 20:
        return True
    if set(names) <= REVERSAL_NAMES:
        if direction == "BUY" and rsi >= 70:
            return True
        if direction == "SELL" and rsi <= 30:
            return True
    return False


def decide(snap: dict, memory, account: dict, month_return: float, news_block: str = "", higher=None, bars=None, record=None):
    """Return an order dict or a wait dict. Never omits a stop on an order."""
    buys, sells, buy_stops, sell_stops = _candidate_names(snap, bars)
    if buys and sells:
        return {
            "action": "WAIT",
            "symbol": snap["symbol"],
            "reason": "a buy setup and a sell setup are both on this candle",
        }
    if not buys and not sells:
        return {
            "action": "WAIT",
            "symbol": snap["symbol"],
            "reason": "no trend, candle, level, gap, or order block setup",
        }

    direction = "BUY" if buys else "SELL"
    names = buys if direction == "BUY" else sells
    stops = buy_stops if direction == "BUY" else sell_stops
    if not _with_average(direction, snap) and not _higher_agrees(direction, higher):
        return {
            "action": "WAIT",
            "symbol": snap["symbol"],
            "reason": "that setup is against the 200 EMA",
        }

    blocked_tf = _higher_blocks(direction, higher)
    if blocked_tf:
        return {
            "action": "WAIT",
            "symbol": snap["symbol"],
            "reason": "the " + blocked_tf + " timeframe points the other way",
        }

    if news_block:
        return {
            "action": "WAIT",
            "symbol": snap["symbol"],
            "reason": "high-impact news: " + news_block,
        }

    if snap["atr"] <= 0.0:
        return {"action": "WAIT", "symbol": snap["symbol"], "reason": "ATR is not ready"}

    spread_price = snap["spread_points"] * snap["point"]
    if spread_price > snap["atr"] * 0.25:
        return {
            "action": "WAIT",
            "symbol": snap["symbol"],
            "reason": "spread is wide relative to ATR",
        }

    if _rsi_blocks(direction, snap["rsi"], names):
        return {"action": "WAIT", "symbol": snap["symbol"], "reason": "RSI is too stretched for this setup"}

    text = setup_text(snap, direction, names)
    lesson = memory.blocking_lesson(text)
    if lesson:
        return {
            "action": "WAIT",
            "symbol": snap["symbol"],
            "reason": "blocked by a stored loss: " + lesson,
        }

    stop_price = None
    if stops:
        stop_price = min(stops) if direction == "BUY" else max(stops)
    sl, tp, distance = _sl_tp(direction, snap, stop_price)
    if direction == "BUY" and not (sl < snap["bid"]):
        return {"action": "WAIT", "symbol": snap["symbol"], "reason": "stop would be on the wrong side"}
    if direction == "SELL" and not (sl > snap["ask"]):
        return {"action": "WAIT", "symbol": snap["symbol"], "reason": "stop would be on the wrong side"}

    key = setup_key(snap["symbol"], direction, names)
    gap = abs(snap["macd"] - snap["macd_signal"])
    scale = snap["atr"] if snap["atr"] else 1.0
    confidence = 0.45 + min(0.45, gap / scale)
    wins, losses = (0, 0)
    if record is not None:
        confidence = record.adjust(confidence, key)
        wins, losses = record.stats(key)
    # A month already at the target does not raise risk. A month behind does not either.
    lots = lots_for_stop(
        balance=account["balance"],
        confidence=confidence,
        sl_distance=distance,
        tick_size=snap["tick_size"],
        tick_value=snap["tick_value"],
        vol_min=snap["vol_min"],
        vol_max=snap["vol_max"],
        vol_step=snap["vol_step"],
    )
    if lots is None:
        return {
            "action": "WAIT",
            "symbol": snap["symbol"],
            "reason": "the stop's minimum lot would risk more than the account allows",
        }

    return {
        "action": direction,
        "symbol": snap["symbol"],
        "lot_size": lots,
        "stop_loss": round(sl, int(snap["digits"])),
        "take_profit": round(tp, int(snap["digits"])),
        "confidence": round(confidence, 4),
        "month_return": month_return,
        "month_target": MONTHLY_TARGET,
        "setup": text,
        "setup_key": key,
        "reason": _reason(direction, names, wins, losses),
    }


def _reason(direction: str, names, wins: int, losses: int) -> str:
    text = direction + " via " + ", ".join(names)
    total = wins + losses
    if total:
        return text + f", record {wins}/{total}"
    return text
