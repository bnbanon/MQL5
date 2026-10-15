"""High-impact events from the daily brief can block a new order."""

from datetime import datetime, timedelta, timezone

CODES = (
    "EUR", "USD", "GBP", "JPY", "AUD", "NZD", "CAD", "CHF",
    "XAU", "BTC", "ETH",
)


def currencies_in(symbol: str):
    found = [code for code in CODES if code in symbol.upper()]
    if "XAU" in found or "BTC" in found or "ETH" in found:
        found.append("USD")
    return found


def parse_event_time(value: str):
    text = (value or "").replace("Z", "+00:00")
    try:
        when = datetime.fromisoformat(text)
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone(timezone.utc)


def blocking_event(symbol: str, events, now=None, before_minutes=45, after_minutes=20):
    """Return the high-impact release that is too close to trade through."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    wanted = set(currencies_in(symbol))
    soonest = None
    for event in events or []:
        if str(event.get("impact", "")).lower() != "high":
            continue
        if event.get("currency") not in wanted:
            continue
        when = event.get("when")
        if isinstance(when, str):
            when = parse_event_time(when)
        if when is None:
            continue
        delta = when - now
        if timedelta(minutes=-after_minutes) <= delta <= timedelta(minutes=before_minutes):
            if soonest is None or when < soonest[0]:
                soonest = (when, event)
    if soonest is None:
        return ""
    event = soonest[1]
    return f"{event['currency']} {event['title']} at {event.get('time', '')}"
