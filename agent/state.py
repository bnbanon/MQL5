"""Read the snapshot written by AgentBridge.mq5."""


def parse_state(text: str) -> dict:
    account = {}
    chart = ""
    symbols = []
    positions = []
    deals = []
    bars = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|")
        kind = parts[0]
        if kind == "ACCOUNT" and len(parts) >= 6:
            account = {
                "balance": float(parts[1]),
                "equity": float(parts[2]),
                "free_margin": float(parts[3]),
                "currency": parts[4],
                "leverage": float(parts[5]),
            }
        elif kind == "CHART" and len(parts) >= 2:
            chart = parts[1]
        elif kind == "SYMBOL" and len(parts) >= 18:
            symbols.append(
                {
                    "symbol": parts[1],
                    "timeframe": parts[2],
                    "bid": float(parts[3]),
                    "ask": float(parts[4]),
                    "point": float(parts[5]),
                    "digits": int(float(parts[6])),
                    "vol_min": float(parts[7]),
                    "vol_max": float(parts[8]),
                    "vol_step": float(parts[9]),
                    "spread_points": float(parts[10]),
                    "atr": float(parts[11]),
                    "ema200": float(parts[12]),
                    "macd": float(parts[13]),
                    "macd_signal": float(parts[14]),
                    "rsi": float(parts[15]),
                    "tick_value": float(parts[16]),
                    "tick_size": float(parts[17]),
                }
            )
        elif kind == "POSITION" and len(parts) >= 10:
            positions.append(
                {
                    "ticket": parts[1],
                    "symbol": parts[2],
                    "type": parts[3],
                    "volume": float(parts[4]),
                    "price": float(parts[5]),
                    "sl": float(parts[6]),
                    "tp": float(parts[7]),
                    "profit": float(parts[8]),
                    "magic": parts[9],
                }
            )
        elif kind == "BAR" and len(parts) >= 7:
            bars.append(
                {
                    "symbol": parts[1],
                    "timeframe": parts[2],
                    "open": float(parts[3]),
                    "high": float(parts[4]),
                    "low": float(parts[5]),
                    "close": float(parts[6]),
                }
            )
        elif kind == "DEAL" and len(parts) >= 10:
            deals.append(
                {
                    "deal": parts[1],
                    "position": parts[2],
                    "symbol": parts[3],
                    "type": parts[4],
                    "volume": float(parts[5]),
                    "price": float(parts[6]),
                    "profit": float(parts[7]),
                    "time": parts[8],
                    "entry": parts[9],
                }
            )
    if account:
        account["chart"] = chart
    return {
        "account": account,
        "symbols": symbols,
        "positions": positions,
        "deals": deals,
        "bars": bars,
    }


def month_return(account: dict, deals: list) -> float:
    balance = account.get("balance") or 0.0
    if balance <= 0.0:
        return 0.0
    closed = 0.0
    for deal in deals:
        if deal.get("entry") == "OUT":
            closed += deal["profit"]
    gross = balance - closed
    if gross <= 0.0:
        return 0.0
    return closed / gross
