#!/usr/bin/env python3
"""Create the local memory and load the starting rule book."""

import argparse
import os

from agent.knowledge import SEED
from agent.memory import TradeMemory


def seed(path: str) -> int:
    memory = TradeMemory(path)
    for item in SEED:
        memory.add(item["id"], item["document"], item["metadata"])
    print(f"Memory ready at {path}. Rules stored: {memory.collection.count()}")
    return memory.collection.count()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--path",
        default=os.environ.get("AGENT_MEMORY", "./evolutionary_memory"),
    )
    args = parser.parse_args()
    seed(args.path)
