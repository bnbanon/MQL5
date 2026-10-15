# Trading agent

This is a learning loop for the MetaTrader 5 account. The monthly figure is a target of 10 percent. It is not a promise, and a short month does not raise the risk used on the next trade. There is no profit cap. Every order has a hard stop, and the lot cannot exceed the broker maximum.

## What it will not do

No program can guarantee 10 percent a month. News wires, order books, and retail sentiment are not all available from this machine, so the agent does not invent those numbers. If you add an `OPENAI_API_KEY` later, it can be wired in. The decisions that run today are the rules in this repository, the losses it has stored, and a win/loss count for each setup.

## Layout

- `mql5/AgentBridge.mq5` is the terminal side. It publishes prices, ATR, the 200 EMA, MACD, and RSI for M15, H1, and H4, and it refuses an order that has no stop or a lot outside the broker limits. Crypto symbols retry the filling mode when the server rejects it.
- `seed_engine.py` creates `evolutionary_memory` and loads the starting rule book.
- `quantum_agent.py` reads the bridge file, skips a setup that matches a stored loss, and writes at most one order per pass. Wins and losses for the same setup are counted together. The lot stays on the normal scale until that setup has 30 closed trades. After that, the win rate can nudge the size, and the nudge stays inside the 0.2 to 1 percent band.

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

The bridge writes `MQL5/Files/agent_state.csv`. The agent writes `agent_cmd.txt` in that same folder. A stop-out is stored under its deal id, so the same loss is not recorded twice. A winning exit is counted on that setup and does not become a ban. The counts are in `evolutionary_memory/setup_record.json`.

Set `MT5_FILES` if the terminal data folder is somewhere else.

## Daily data

Once a day, `python3 daily_feed.py` downloads this week's economic calendar plus the Federal Reserve and ECB press feeds into `daily_feed/`. The trading loop refreshes that file itself when it is older than 20 hours. A high-impact release blocks new trades in that currency from 45 minutes before the event until 20 minutes after.

The pattern notes in the brief are written here, not copied from a course. The BabyPips school and the Forexpedia glossary are the study links. The live entries are the 200 EMA with MACD, RSI when it is too stretched to chase, engulfing candles, pin bars, morning and evening stars, inside-bar breaks, support and resistance retests, fair value gaps, and order blocks. A buy idea and a sell idea on the same candle cancel each other. A setup against the 200 EMA needs the higher timeframes to agree.
