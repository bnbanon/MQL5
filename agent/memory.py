import os
from typing import Optional

import chromadb

from agent.embeddings import HashEmbedding

COLLECTION = "failed_patterns"


class TradeMemory:
    def __init__(self, path: str):
        os.makedirs(path, exist_ok=True)
        self.client = chromadb.PersistentClient(path=path)
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION,
            embedding_function=HashEmbedding(),
            metadata={"hnsw:space": "cosine"},
        )

    def add(self, item_id: str, document: str, metadata: dict) -> bool:
        existing = self.collection.get(ids=[item_id])
        if existing and existing.get("ids"):
            return False
        clean = {key: str(value) for key, value in metadata.items()}
        self.collection.add(documents=[document], metadatas=[clean], ids=[item_id])
        return True

    def similar(self, text: str, n_results: int = 3):
        count = self.collection.count()
        if count == 0 or not text.strip():
            return []
        found = self.collection.query(
            query_texts=[text],
            n_results=min(n_results, count),
            include=["documents", "metadatas", "distances"],
        )
        rows = []
        documents = (found.get("documents") or [[]])[0]
        metadatas = (found.get("metadatas") or [[]])[0]
        distances = (found.get("distances") or [[]])[0]
        for document, metadata, distance in zip(documents, metadatas, distances):
            rows.append(
                {
                    "document": document,
                    "metadata": metadata or {},
                    "distance": float(distance),
                }
            )
        return rows

    def blocking_lesson(self, text: str, max_distance: float = 0.45) -> Optional[str]:
        rows = self.similar(text, n_results=1)
        if not rows:
            return None
        if rows[0]["distance"] <= max_distance:
            return rows[0]["document"]
        return None
