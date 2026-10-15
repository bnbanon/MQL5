from agent.record import key_from_setup


def lesson_from_loss(setup: str, symbol: str, profit: float) -> str:
    return (
        f"Do not repeat this {symbol} setup. It hit the hard stop and lost "
        f"{profit:.2f}. Setup: {setup}"
    )


def _tracked(open_setups: dict, position: str, deal_id: str):
    raw = None
    if position and position in open_setups:
        raw = open_setups.get(position)
    elif deal_id and deal_id in open_setups:
        raw = open_setups.get(deal_id)
    if isinstance(raw, dict):
        setup = str(raw.get("setup") or "")
        key = str(raw.get("key") or "") or key_from_setup(setup)
        return setup, key
    if isinstance(raw, str):
        return raw, key_from_setup(raw)
    return "", ""


def _remember(record, record_log, deal_id: str, key: str, won: bool) -> None:
    if record is None or not key:
        return
    message = record.note(deal_id, key, won)
    if message and record_log is not None:
        record_log.append(message)


def reflect_closed_deals(deals, open_setups: dict, memory, record=None, record_log=None) -> list:
    """Store one lesson per losing exit, and count both wins and losses once."""
    written = []
    for deal in deals:
        if deal.get("entry") != "OUT":
            continue
        deal_id = str(deal["deal"])
        position = str(deal.get("position", ""))
        setup, key = _tracked(open_setups, position, deal_id)
        profit = deal["profit"]
        if profit > 0.0:
            _remember(record, record_log, deal_id, key, True)
            open_setups.pop(position, None)
            continue
        if profit == 0.0:
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
        _remember(record, record_log, deal_id, key, False)
        open_setups.pop(position, None)
        if stored:
            written.append(document)
    return written
