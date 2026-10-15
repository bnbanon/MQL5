"""Setups read from closed candles.

The names match ideas traders use: engulfing and star candles, pin bars,
support and resistance, a retest, a fair value gap, and an order block.
The wording is ours.
"""


def _body(bar):
    return abs(bar["close"] - bar["open"])


def _range(bar):
    return bar["high"] - bar["low"]


def swings(bars, wing=2):
    highs = []
    lows = []
    if len(bars) < wing * 2 + 1:
        return highs, lows
    for index in range(wing, len(bars) - wing):
        window = bars[index - wing : index + wing + 1]
        if bars[index]["high"] >= max(bar["high"] for bar in window):
            highs.append({"index": index, "price": bars[index]["high"]})
        if bars[index]["low"] <= min(bar["low"] for bar in window):
            lows.append({"index": index, "price": bars[index]["low"]})
    return highs, lows


def nearest_levels(bars):
    """Nearest swing low at or under the close, and swing high at or above it."""
    price = bars[-1]["close"]
    history = bars[:-1] if len(bars) > 5 else bars
    highs, lows = swings(history)
    supports = [row["price"] for row in lows if row["price"] <= price]
    resistances = [row["price"] for row in highs if row["price"] >= price]
    support = max(supports) if supports else None
    resistance = min(resistances) if resistances else None
    return support, resistance


def near(price, level, atr, factor=0.35):
    if level is None or atr <= 0:
        return False
    return abs(price - level) <= factor * atr


def engulfing(prev, curr):
    """An up candle whose body covers a down candle, or the mirror."""
    prev_high = max(prev["open"], prev["close"])
    prev_low = min(prev["open"], prev["close"])
    curr_high = max(curr["open"], curr["close"])
    curr_low = min(curr["open"], curr["close"])
    covers = curr_high >= prev_high and curr_low <= prev_low
    if not covers:
        return None
    if curr["close"] > curr["open"] and prev["close"] < prev["open"]:
        return "BUY"
    if curr["close"] < curr["open"] and prev["close"] > prev["open"]:
        return "SELL"
    return None


def pin_bar(bar, atr):
    """A long wick and a small body, large enough to matter versus ATR."""
    rng = _range(bar)
    if atr <= 0 or rng < 0.5 * atr:
        return None
    body = _body(bar)
    upper = bar["high"] - max(bar["open"], bar["close"])
    lower = min(bar["open"], bar["close"]) - bar["low"]
    if lower >= max(2.0 * body, 0.55 * rng) and upper <= 0.25 * rng and bar["close"] >= bar["low"] + 0.6 * rng:
        return "BUY"
    if upper >= max(2.0 * body, 0.55 * rng) and lower <= 0.25 * rng and bar["close"] <= bar["low"] + 0.4 * rng:
        return "SELL"
    return None


def star(bars):
    """Three candles: a push, a small pause, then a push back through the midpoint."""
    if len(bars) < 3:
        return None
    first, mid, last = bars[-3], bars[-2], bars[-1]
    first_body = _body(first)
    mid_body = _body(mid)
    last_body = _body(last)
    if first_body <= 0 or mid_body * 2 >= first_body or last_body <= mid_body:
        return None
    midpoint = (first["open"] + first["close"]) / 2.0
    if first["close"] < first["open"] and last["close"] > last["open"] and last["close"] > midpoint:
        return "BUY"
    if first["close"] > first["open"] and last["close"] < last["open"] and last["close"] < midpoint:
        return "SELL"
    return None


def inside_break(bars):
    """The middle candle sits inside the one before it, then the next close breaks out."""
    if len(bars) < 3:
        return None
    mother, inside, last = bars[-3], bars[-2], bars[-1]
    if inside["high"] > mother["high"] or inside["low"] < mother["low"]:
        return None
    if last["close"] > mother["high"] and last["close"] > last["open"]:
        return "BUY"
    if last["close"] < mother["low"] and last["close"] < last["open"]:
        return "SELL"
    return None


def fair_value_gaps(bars):
    """A three-candle hole. Later candles that trade through it remove it."""
    gaps = []
    for index in range(2, len(bars)):
        older = bars[index - 2]
        newer = bars[index]
        if newer["low"] > older["high"]:
            gaps.append(
                {"direction": "BUY", "low": older["high"], "high": newer["low"], "index": index}
            )
        elif newer["high"] < older["low"]:
            gaps.append(
                {"direction": "SELL", "low": newer["high"], "high": older["low"], "index": index}
            )
    alive = []
    for gap in gaps:
        filled = False
        for bar in bars[gap["index"] + 1 :]:
            if gap["direction"] == "BUY" and bar["low"] <= gap["low"]:
                filled = True
            if gap["direction"] == "SELL" and bar["high"] >= gap["high"]:
                filled = True
        if not filled:
            alive.append(gap)
    return alive


def order_blocks(bars):
    """The last opposite candle before a push that leaves a fair value gap."""
    blocks = []
    for index in range(2, len(bars)):
        older, mid, newer = bars[index - 2], bars[index - 1], bars[index]
        bullish_gap = newer["low"] > older["high"] and mid["close"] > mid["open"]
        bearish_gap = newer["high"] < older["low"] and mid["close"] < mid["open"]
        if not bullish_gap and not bearish_gap:
            continue
        for back in range(index - 2, -1, -1):
            candle = bars[back]
            bearish = candle["close"] < candle["open"]
            if bullish_gap and not bearish:
                continue
            if bearish_gap and bearish:
                continue
            blocks.append(
                {
                    "direction": "BUY" if bullish_gap else "SELL",
                    "low": min(candle["open"], candle["close"]),
                    "high": max(candle["open"], candle["close"]),
                    "index": back,
                }
            )
            break
    alive = []
    for block in blocks:
        mitigated = False
        for bar in bars[block["index"] + 1 :]:
            if block["direction"] == "BUY" and bar["close"] < block["low"]:
                mitigated = True
            if block["direction"] == "SELL" and bar["close"] > block["high"]:
                mitigated = True
        if not mitigated:
            alive.append(block)
    return alive


def _in_zone(price, zone):
    return zone["low"] <= price <= zone["high"]


def _returned(prev_close, price, zone, direction):
    """Price was outside the zone on the previous close and is inside it now."""
    if not _in_zone(price, zone):
        return False
    if direction == "BUY":
        return prev_close > zone["high"]
    return prev_close < zone["low"]


def retest(bars, atr):
    """A swing level breaks, then the latest candle tags it and closes back through."""
    if len(bars) < 8 or atr <= 0:
        return None
    last = bars[-1]
    highs, lows = swings(bars[:-2])
    for row in reversed(highs):
        level = row["price"]
        broke = any(bar["close"] > level for bar in bars[-6:-1])
        tagged = last["low"] <= level + 0.25 * atr and last["close"] > level and last["close"] > last["open"]
        if broke and tagged:
            return "BUY", level
    for row in reversed(lows):
        level = row["price"]
        broke = any(bar["close"] < level for bar in bars[-6:-1])
        tagged = last["high"] >= level - 0.25 * atr and last["close"] < level and last["close"] < last["open"]
        if broke and tagged:
            return "SELL", level
    return None


def _with_trend(direction, bid, ema):
    if ema <= 0:
        return True
    if direction == "BUY":
        return bid > ema
    return bid < ema


def find_setups(bars, atr, bid, ema):
    """Each item is a direction, a short name, and the price the stop must sit beyond."""
    found = []
    if not bars or len(bars) < 3 or atr <= 0:
        return found
    last = bars[-1]
    prev = bars[-2]
    support, resistance = (None, None)
    if len(bars) >= 8:
        support, resistance = nearest_levels(bars)

    eng = engulfing(prev, last)
    if eng and _body(last) >= 0.3 * atr:
        at_level = (eng == "BUY" and near(last["low"], support, atr)) or (
            eng == "SELL" and near(last["high"], resistance, atr)
        )
        if at_level or _with_trend(eng, bid, ema):
            stop = min(last["low"], prev["low"]) if eng == "BUY" else max(last["high"], prev["high"])
            found.append({"direction": eng, "name": "engulfing", "stop_price": stop})

    pin = pin_bar(last, atr)
    if pin == "BUY" and near(last["low"], support, atr, 0.45):
        found.append({"direction": "BUY", "name": "pin bar", "stop_price": last["low"]})
    if pin == "SELL" and near(last["high"], resistance, atr, 0.45):
        found.append({"direction": "SELL", "name": "pin bar", "stop_price": last["high"]})

    starred = star(bars)
    star_at_level = False
    if starred == "BUY":
        star_at_level = near(min(bar["low"] for bar in bars[-3:]), support, atr)
    elif starred == "SELL":
        star_at_level = near(max(bar["high"] for bar in bars[-3:]), resistance, atr)
    if starred and (_with_trend(starred, bid, ema) or star_at_level):
        stop = min(bar["low"] for bar in bars[-3:]) if starred == "BUY" else max(bar["high"] for bar in bars[-3:])
        label = "morning star" if starred == "BUY" else "evening star"
        found.append({"direction": starred, "name": label, "stop_price": stop})

    broken = inside_break(bars)
    if broken and _with_trend(broken, bid, ema):
        mother = bars[-3]
        stop = mother["low"] if broken == "BUY" else mother["high"]
        found.append({"direction": broken, "name": "inside bar", "stop_price": stop})

    prev_close = prev["close"]
    for gap in reversed(fair_value_gaps(bars)):
        if _returned(prev_close, bid, gap, gap["direction"]):
            stop = gap["low"] if gap["direction"] == "BUY" else gap["high"]
            found.append({"direction": gap["direction"], "name": "fair value gap", "stop_price": stop})
            break
    for block in reversed(order_blocks(bars)):
        if _returned(prev_close, bid, block, block["direction"]):
            stop = block["low"] if block["direction"] == "BUY" else block["high"]
            found.append({"direction": block["direction"], "name": "order block", "stop_price": stop})
            break

    tested = retest(bars, atr)
    if tested and _with_trend(tested[0], bid, ema):
        found.append({"direction": tested[0], "name": "retest", "stop_price": tested[1]})
    return found
