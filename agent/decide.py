from agent.risk import lots_for_stop

MONTHLY_TARGET = 0.10


def setup_text(snap: dict, direction: str) -> str:
    ema_side = "above" if snap["bid"] >= snap["ema200"] else "below"
    macd_side = "above" if snap["macd"] >= snap["macd_signal"] else "below"
    return (
        f"{direction} {snap['symbol']} while price is {ema_side} the 200 EMA "
        f"and MACD is {macd_side} its signal. Spread {int(snap['spread_points'])} points."
    )


def _direction(snap: dict):
    if snap["bid"] > snap["ema200"] and snap["macd"] > snap["macd_signal"]:
        return "BUY"
    if snap["bid"] < snap["ema200"] and snap["macd"] < snap["macd_signal"]:
        return "SELL"
    return None


def _sl_tp(direction: str, snap: dict):
    distance = 1.5 * snap["atr"]
    target = 3.0 * snap["atr"]
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


def decide(snap: dict, memory, account: dict, month_return: float, news_block: str = "", higher=None):
    """Return an order dict or a wait dict. Never omits a stop on an order."""
    direction = _direction(snap)
    if direction is None:
        return {"action": "WAIT", "symbol": snap["symbol"], "reason": "price and MACD do not agree"}

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

    text = setup_text(snap, direction)
    lesson = memory.blocking_lesson(text)
    if lesson:
        return {
            "action": "WAIT",
            "symbol": snap["symbol"],
            "reason": "blocked by a stored loss: " + lesson,
        }

    sl, tp, distance = _sl_tp(direction, snap)
    if direction == "BUY" and not (sl < snap["bid"]):
        return {"action": "WAIT", "symbol": snap["symbol"], "reason": "stop would be on the wrong side"}
    if direction == "SELL" and not (sl > snap["ask"]):
        return {"action": "WAIT", "symbol": snap["symbol"], "reason": "stop would be on the wrong side"}

    gap = abs(snap["macd"] - snap["macd_signal"])
    scale = snap["atr"] if snap["atr"] else 1.0
    confidence = 0.45 + min(0.45, gap / scale)
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
        "reason": text,
    }
