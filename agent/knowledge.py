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
]
