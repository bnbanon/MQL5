#!/usr/bin/env python3
"""Download one day's official calendar and central-bank headlines.

The files land in daily_feed/ and are what the agent reads while it trades.
Pattern notes are written in our own words. BabyPips is listed as the study
source, not copied into the brief.
"""

import json
import os
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
FED_URL = "https://www.federalreserve.gov/feeds/press_all.xml"
ECB_URL = "https://www.ecb.europa.eu/rss/press.html"
STUDY_SOURCES = [
    "https://www.babypips.com/learn/forex",
    "https://www.federalreserve.gov/feeds/press_all.xml",
    "https://www.ecb.europa.eu/rss/press.html",
]

PLAYBOOK = [
    "Trade in the direction of the 200 EMA. A cross against that average is not an entry.",
    "An engulfing candle only counts when its body covers the previous body and the higher timeframe agrees.",
    "A pin bar is a rejection of a level: the wick is the story, and the close has to come back inside the range.",
    "Do not open a new trade in the window around a high-impact release for that currency.",
    "A wide spread relative to ATR is a reason to wait, especially on exotics and crypto.",
]


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 daily-feed"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def _rss_items(payload: bytes, limit: int = 8):
    root = ET.fromstring(payload)
    rows = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        published = (item.findtext("pubDate") or "").strip()
        if title:
            rows.append({"title": title, "link": link, "published": published})
        if len(rows) >= limit:
            break
    return rows


def calendar_events(payload: bytes):
    raw = json.loads(payload.decode("utf-8"))
    events = []
    for row in raw:
        impact = row.get("impact") or ""
        if impact not in ("High", "Medium"):
            continue
        events.append(
            {
                "time": row.get("date") or "",
                "currency": row.get("country") or "",
                "title": row.get("title") or "",
                "impact": impact,
                "forecast": row.get("forecast") or "",
                "previous": row.get("previous") or "",
            }
        )
    return events


def build_brief(calendar_payload: bytes, fed_payload: bytes, ecb_payload: bytes) -> dict:
    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "events": calendar_events(calendar_payload),
        "fed": _rss_items(fed_payload),
        "ecb": _rss_items(ecb_payload),
        "playbook": PLAYBOOK,
        "study_sources": STUDY_SOURCES,
    }


def refresh(directory: str) -> dict:
    folder = Path(directory)
    folder.mkdir(parents=True, exist_ok=True)
    calendar_payload = _get(CALENDAR_URL)
    fed_payload = _get(FED_URL)
    ecb_payload = _get(ECB_URL)
    (folder / "calendar.json").write_bytes(calendar_payload)
    (folder / "fed.xml").write_bytes(fed_payload)
    (folder / "ecb.xml").write_bytes(ecb_payload)
    brief = build_brief(calendar_payload, fed_payload, ecb_payload)
    (folder / "brief.json").write_text(json.dumps(brief, indent=2), encoding="utf-8")
    return brief


def load_brief(directory: str):
    path = Path(directory) / "brief.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def refresh_if_stale(directory: str, max_age_hours: float = 20) -> dict:
    brief = load_brief(directory)
    if brief:
        fetched = datetime.fromisoformat(brief["fetched_at"])
        age = datetime.now(timezone.utc) - fetched
        if age.total_seconds() < max_age_hours * 3600:
            return brief
    return refresh(directory)


if __name__ == "__main__":
    target = os.environ.get("DAILY_FEED", "./daily_feed")
    brief = refresh(target)
    highs = [row for row in brief["events"] if row["impact"] == "High"]
    print(f"Saved {target}/brief.json")
    print(f"High-impact events: {len(highs)}")
    for row in highs[:12]:
        print(f"  {row['time']}  {row['currency']}  {row['title']}")
    print(f"Fed headlines: {len(brief['fed'])}  ECB headlines: {len(brief['ecb'])}")
