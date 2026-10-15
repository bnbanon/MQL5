"""Win and loss counts for one setup. Size waits for a long record."""

import json
from pathlib import Path

LONG_RECORD = 30
MAX_NUDGE = 0.15


def setup_key(symbol: str, direction: str, names) -> str:
    listed = ", ".join(sorted(name.strip() for name in names if str(name).strip()))
    return f"{symbol}|{direction}|{listed}"


def key_from_setup(setup: str) -> str:
    """Recover a setup key from the order text. Spread and price stay out of it."""
    text = (setup or "").strip()
    head, separator, _rest = text.partition(".")
    if not separator:
        return ""
    direction, space, remainder = head.partition(" ")
    if space != " " or direction not in ("BUY", "SELL"):
        return ""
    symbol, marker, listed = remainder.partition(" via ")
    if marker != " via " or not symbol.strip() or not listed.strip():
        return ""
    names = [part.strip() for part in listed.split(",")]
    return setup_key(symbol.strip(), direction, names)


def adjusted_confidence(base: float, wins: int, losses: int) -> float:
    """Nudge confidence from the win rate only after a long record.

    The result stays inside 0 to 1, which is the existing 0.2% to 1% risk band.
    A 50% record leaves the size alone. Fewer than LONG_RECORD closes do too.
    """
    score = min(1.0, max(0.0, float(base)))
    total = wins + losses
    if total < LONG_RECORD:
        return score
    win_rate = wins / total
    nudge = (win_rate - 0.5) * (MAX_NUDGE * 2.0)
    return min(1.0, max(0.0, score + nudge))


class SetupRecord:
    def __init__(self, path: str):
        self.path = Path(path) / "setup_record.json"
        self.data = {"deals": {}, "setups": {}}
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                loaded = None
            if (
                isinstance(loaded, dict)
                and isinstance(loaded.get("deals"), dict)
                and isinstance(loaded.get("setups"), dict)
            ):
                self.data = loaded

    def stats(self, key: str):
        bucket = self.data["setups"].get(key) or {}
        return int(bucket.get("wins", 0)), int(bucket.get("losses", 0))

    def adjust(self, confidence: float, key: str) -> float:
        wins, losses = self.stats(key)
        return adjusted_confidence(confidence, wins, losses)

    def note(self, deal_id: str, key: str, won: bool):
        deal_id = str(deal_id)
        if not key or deal_id in self.data["deals"]:
            return None
        bucket = self.data["setups"].setdefault(key, {"wins": 0, "losses": 0})
        if won:
            bucket["wins"] = int(bucket.get("wins", 0)) + 1
            result = "win"
        else:
            bucket["losses"] = int(bucket.get("losses", 0)) + 1
            result = "loss"
        self.data["deals"][deal_id] = {"key": key, "result": result}
        self._save()
        wins, losses = self.stats(key)
        return f"{result} {key}: {wins} wins, {losses} losses"

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        temporary.replace(self.path)
