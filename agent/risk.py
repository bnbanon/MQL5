"""Position size from confidence. A losing month does not raise the risk."""

MIN_RISK = 0.002
MAX_RISK = 0.01
MIN_LOT_RISK_CAP = 0.02


def risk_fraction(confidence: float) -> float:
    score = min(1.0, max(0.0, float(confidence)))
    return MIN_RISK + (MAX_RISK - MIN_RISK) * score


def normalize_lots(raw: float, step: float, minimum: float, maximum: float):
    if step <= 0.0 or maximum <= 0.0 or minimum <= 0.0:
        return None
    if raw < minimum:
        return None
    clipped = min(raw, maximum)
    steps = int(clipped / step)
    sized = steps * step
    if sized < minimum:
        return None
    if sized > maximum:
        sized = int(maximum / step) * step
    decimals = 0
    probe = step
    while decimals < 8 and abs(probe - round(probe)) > 1e-8:
        probe *= 10.0
        decimals += 1
    return round(sized, decimals)


def lots_for_stop(
    balance: float,
    confidence: float,
    sl_distance: float,
    tick_size: float,
    tick_value: float,
    vol_min: float,
    vol_max: float,
    vol_step: float,
):
    """Lot size so a stop-out loses a confidence-scaled slice of balance.

    The broker maximum is a hard ceiling. A stop smaller than the minimum
    lot's loss is refused when that loss would exceed 2% of balance.
    """
    if balance <= 0.0 or sl_distance <= 0.0 or tick_size <= 0.0 or tick_value <= 0.0:
        return None
    loss_per_lot = (sl_distance / tick_size) * tick_value
    if loss_per_lot <= 0.0:
        return None
    money_risk = balance * risk_fraction(confidence)
    raw = money_risk / loss_per_lot
    if raw < vol_min:
        if vol_min * loss_per_lot > balance * MIN_LOT_RISK_CAP:
            return None
        raw = vol_min
    return normalize_lots(raw, vol_step, vol_min, vol_max)
