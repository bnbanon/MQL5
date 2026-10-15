"""Starting rules. These are loaded once and then extended by real losses."""

SEED = [
    {
        "id": "init_001",
        "document": (
            "Do not buy a market that is already falling through the 200 EMA "
            "when retail positioning is extremely long. That is a falling knife, "
            "and the stop is the exit."
        ),
        "metadata": {"type": "technical_failure", "pair": "ALL"},
    },
    {
        "id": "init_002",
        "document": (
            "Do not enter just before a high-impact release when the spread is "
            "many times its normal width. The stop is filled by the spread, not "
            "by the idea."
        ),
        "metadata": {"type": "execution_failure", "pair": "ALL"},
    },
    {
        "id": "init_003",
        "document": (
            "Do not buy the first pause in a downswing. A single green candle "
            "under a falling 200 EMA is not a reversal. Wait for price to close "
            "back above the level that broke."
        ),
        "metadata": {"type": "technical_failure", "pair": "ALL"},
    },
    {
        "id": "init_004",
        "document": (
            "A percent target is a percent of account balance in money. It is "
            "never a percent of the instrument price. One percent of a 10000 "
            "balance is 100 of account currency."
        ),
        "metadata": {"type": "risk_rule", "pair": "ALL"},
    },
    {
        "id": "init_005",
        "document": (
            "Every order needs a hard stop on the correct side of the price. "
            "If the stop cannot be set, do not send the order. A losing month "
            "does not increase next month's risk. Each month starts at the 10 "
            "percent target with the same risk rules."
        ),
        "metadata": {"type": "risk_rule", "pair": "ALL"},
    },
    {
        "id": "init_006",
        "document": (
            "On exchange symbols such as BTCUSD and ETHUSD, use return filling. "
            "A point-based spread limit copied from gold will block every crypto "
            "entry because one point is a fraction of the price."
        ),
        "metadata": {"type": "execution_failure", "pair": "CRYPTO"},
    },
    {
        "id": "init_007",
        "document": (
            "Do not remove a stop to recover a loss. A recovery trade is a new "
            "order with its own stop, its own size, and a reason that is not "
            "already stored as a failed pattern."
        ),
        "metadata": {"type": "risk_rule", "pair": "ALL"},
    },
    {
        "id": "init_008",
        "document": (
            "An engulfing candle counts when its body covers the previous body. "
            "Buy the bullish one at support or with the 200 EMA. Sell the bearish one "
            "at resistance or with the 200 EMA."
        ),
        "metadata": {"type": "price_action", "pair": "ALL"},
    },
    {
        "id": "init_009",
        "document": (
            "A pin bar is a long wick and a small body. Buy it when the lower wick "
            "rejects a swing low and the close comes back up. Sell it when the upper "
            "wick rejects a swing high."
        ),
        "metadata": {"type": "price_action", "pair": "ALL"},
    },
    {
        "id": "init_010",
        "document": (
            "Support is a prior swing low and resistance is a prior swing high. "
            "A retest is a close through that level, then a return that closes back "
            "the way of the break. A fair value gap is a three-candle hole that has "
            "not been traded through. An order block is the last opposite candle "
            "before the push that left that hole. Enter when price comes back into "
            "the gap or the block, and put the stop beyond it."
        ),
        "metadata": {"type": "price_action", "pair": "ALL"},
    },
    {
        "id": "init_011",
        "document": (
            "RSI at 80 or higher is too late to buy. RSI at 20 or lower is too late "
            "to sell. A reversal candle into that extreme is skipped. A setup against "
            "the 200 EMA needs the higher timeframes to agree, or it is skipped."
        ),
        "metadata": {"type": "price_action", "pair": "ALL"},
    },
]
