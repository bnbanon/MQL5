# Trading agent

This is a learning loop for the MetaTrader 5 account. The monthly figure is a target of 10 percent. It is not a promise, and a short month does not raise the risk used on the next trade. There is no profit cap. Every order has a hard stop, and the lot cannot exceed the broker maximum.

## What it will not do

No program can guarantee 10 percent a month. News wires, order books, and retail sentiment are not all available from this machine, so the agent does not invent those numbers. If you add an `OPENAI_API_KEY` later, it can be wired in. The decisions that run today are the rules in this repository plus the losses it has stored.

## Layout

- `mql5/AgentBridge.mq5` is the terminal side. It publishes prices, ATR, the 200 EMA, MACD, and RSI for M15, H1, and H4, and it refuses an order that has no stop or a lot outside the broker limits. Crypto symbols retry the filling mode when the server rejects it.
- `seed_engine.py` creates `evolutionary_memory` and loads the starting rule book.
- `quantum_agent.py` reads the bridge file, skips a setup that matches a stored loss, and writes at most one order per pass.

## Run

1. Compile `AgentBridge.mq5` and attach it to any chart. Leave it running. The chart period is the timeframe it will trade. H1 and H4 can veto that direction.
2. Initialize memory:

```bash
python3 seed_engine.py
```

3. Start the agent:

```bash
python3 quantum_agent.py
```

The bridge writes `MQL5/Files/agent_state.csv`. The agent writes `agent_cmd.txt` in that same folder. A stop-out is stored under its deal id, so the same loss is not recorded twice.

Set `MT5_FILES` if the terminal data folder is somewhere else.

## Daily data

Once a day, `python3 daily_feed.py` downloads this week's economic calendar plus the Federal Reserve and ECB press feeds into `daily_feed/`. The trading loop refreshes that file itself when it is older than 20 hours. A high-impact release blocks new trades in that currency from 45 minutes before the event until 20 minutes after.

The pattern notes in the brief are written here, not copied from a course. The BabyPips school is listed as the place to study the same ideas: trend, engulfing candles, pin bars, and staying out of news spreads.
