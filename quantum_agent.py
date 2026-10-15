#!/usr/bin/env python3
"""Read the MT5 bridge, skip known losing setups, and send orders that have a stop.

The monthly figure is a target. It is not a promise, and a short month does not
raise the risk used for the next one. Profit above the target is allowed.
"""

import json
import os
import time
import uuid
from pathlib import Path

from agent.decide import MONTHLY_TARGET, decide
from agent.memory import TradeMemory
from agent.news import blocking_event
from agent.record import SetupRecord
from agent.reflect import reflect_closed_deals
from agent.state import month_return, parse_state
from daily_feed import refresh_if_stale
from seed_engine import seed

MEMORY_PATH = os.environ.get("AGENT_MEMORY", "./evolutionary_memory")
FEED_DIR = os.environ.get("DAILY_FEED", "./daily_feed")
FILES_DIR = Path(
    os.environ.get(
        "MT5_FILES",
        os.path.expanduser("~/.mt5/drive_c/MetaTrader5/MQL5/Files"),
    )
)
STATE_NAME = "agent_state.csv"
COMMAND_NAME = "agent_cmd.txt"
TRACK_NAME = "agent_open.json"
POLL_SECONDS = float(os.environ.get("AGENT_POLL", "5"))
PENDING = {"symbol": "", "sent": 0.0}


def load_open(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_open(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def write_command(files: Path, order: dict) -> str:
    command_id = uuid.uuid4().hex[:12]
    line = "|".join(
        [
            command_id,
            order["action"],
            order["symbol"],
            f"{order['lot_size']:.8f}",
            f"{order['stop_loss']:.8f}",
            f"{order['take_profit']:.8f}",
            order["setup"].replace("|", "/")[:180],
        ]
    )
    target = files / COMMAND_NAME
    temporary = files / (COMMAND_NAME + ".tmp")
    temporary.write_text(line + "\n", encoding="utf-8")
    temporary.replace(target)
    return command_id


def consume_acks(files: Path, open_setups: dict) -> None:
    path = files / "agent_ack.txt"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8", errors="replace")
    path.write_text("", encoding="utf-8")
    for raw in text.splitlines():
        parts = raw.strip().split("|")
        if len(parts) < 3:
            continue
        command_id, status, detail = parts[0], parts[1], parts[2]
        if status == "OK" and command_id in open_setups:
            open_setups[detail] = open_setups.pop(command_id)
        elif status != "OK":
            print("Bridge rejected", command_id, detail)
            open_setups.pop(command_id, None)


def command_waiting(files: Path) -> bool:
    path = files / COMMAND_NAME
    return path.exists() and path.stat().st_size > 0


def one_pass(memory: TradeMemory, files: Path, track_path: Path, record: SetupRecord = None) -> None:
    state_path = files / STATE_NAME
    if not state_path.exists():
        print("Waiting for AgentBridge to write", state_path)
        return
    state = parse_state(state_path.read_text(encoding="utf-8", errors="replace"))
    account = state["account"]
    if not account:
        print("State file has no account row yet")
        return
    open_setups = load_open(track_path)
    consume_acks(files, open_setups)
    record_log = []
    lessons = reflect_closed_deals(state["deals"], open_setups, memory, record, record_log)
    for lesson in lessons:
        print("Stored loss:", lesson)
    for line in record_log:
        print("Recorded", line)
    held = {row["symbol"] for row in state["positions"]}
    progress = month_return(account, state["deals"])
    print(
        f"Balance {account['balance']:.2f} {account['currency']}  "
        f"month {progress * 100:.2f}%  target {MONTHLY_TARGET * 100:.0f}%"
    )
    chart = account.get("chart", "")
    brief = refresh_if_stale(FEED_DIR)
    events = brief.get("events", [])
    print(f"Daily brief {brief.get('fetched_at', '')}  events {len(events)}")
    if PENDING["symbol"] and PENDING["symbol"] in held:
        PENDING["symbol"] = ""
    if command_waiting(files) or (PENDING["symbol"] and time.time() - PENDING["sent"] < 20):
        print("Waiting for the bridge to finish the last order", PENDING["symbol"])
        save_open(track_path, open_setups)
        return
    grouped = {}
    for snap in state["symbols"]:
        grouped.setdefault(snap["symbol"], []).append(snap)
    bar_groups = {}
    for bar in state.get("bars", []):
        bar_groups.setdefault((bar["symbol"], bar["timeframe"]), []).append(bar)
    for symbol, rows in grouped.items():
        if symbol in held:
            continue
        primary = next((row for row in rows if row["timeframe"] == chart), rows[0])
        higher = [row for row in rows if row is not primary]
        news = blocking_event(symbol, [{**row, "when": row.get("time")} for row in events])
        chart_bars = bar_groups.get((symbol, primary["timeframe"]), [])
        order = decide(
            primary,
            memory,
            account,
            progress,
            news_block=news,
            higher=higher,
            bars=chart_bars,
            record=record,
        )
        print(symbol, order["action"], order.get("reason", ""))
        if order["action"] not in ("BUY", "SELL"):
            continue
        if order.get("stop_loss", 0.0) <= 0.0:
            print("Refused an order with no stop")
            continue
        command_id = write_command(files, order)
        open_setups[command_id] = {"setup": order["setup"], "key": order["setup_key"]}
        PENDING["symbol"] = order["symbol"]
        PENDING["sent"] = time.time()
        print(
            f"Sent {order['action']} {order['symbol']} {order['lot_size']} "
            f"sl {order['stop_loss']} tp {order['take_profit']} id {command_id}"
        )
        break
    save_open(track_path, open_setups)


def main() -> None:
    seed(MEMORY_PATH)
    memory = TradeMemory(MEMORY_PATH)
    record = SetupRecord(MEMORY_PATH)
    FILES_DIR.mkdir(parents=True, exist_ok=True)
    track_path = FILES_DIR / TRACK_NAME
    while True:
        try:
            one_pass(memory, FILES_DIR, track_path, record)
        except Exception as error:
            print("Loop error:", error)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
