def lesson_from_loss(setup: str, symbol: str, profit: float) -> str:
    return (
        f"Do not repeat this {symbol} setup. It hit the hard stop and lost "
        f"{profit:.2f}. Setup: {setup}"
    )


def reflect_closed_deals(deals, open_setups: dict, memory) -> list:
    """Store one lesson per losing exit. Winning exits are kept as context only."""
    written = []
    for deal in deals:
        if deal.get("entry") != "OUT":
            continue
        deal_id = str(deal["deal"])
        position = str(deal.get("position", ""))
        setup = open_setups.get(position) or open_setups.get(deal_id)
        if deal["profit"] >= 0.0:
            open_setups.pop(position, None)
            continue
        if not setup:
            setup = f"{deal['type']} {deal['symbol']} closed at {deal['price']}"
        document = lesson_from_loss(setup, deal["symbol"], deal["profit"])
        stored = memory.add(
            "loss_" + deal_id,
            document,
            {"type": "stop_loss", "pair": deal["symbol"], "profit": deal["profit"]},
        )
        open_setups.pop(position, None)
        if stored:
            written.append(document)
    return written
