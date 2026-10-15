import hashlib
import math
import re

from chromadb.api.types import Documents, Embeddings, EmbeddingFunction
from chromadb.utils.embedding_functions import register_embedding_function

_TOKEN = re.compile(r"[a-z0-9]+")


@register_embedding_function
class HashEmbedding(EmbeddingFunction[Documents]):
    """Local token embedding. No model download, stable across restarts."""

    def __init__(self, dim: int = 256):
        self.dim = int(dim)

    def __call__(self, input: Documents) -> Embeddings:
        return [self._embed(text) for text in input]

    @staticmethod
    def name() -> str:
        return "hash-tokens"

    @staticmethod
    def build_from_config(config):
        return HashEmbedding(dim=int(config.get("dim", 256)))

    def get_config(self):
        return {"dim": self.dim}

    def _embed(self, text: str):
        vector = [0.0] * self.dim
        tokens = _TOKEN.findall((text or "").lower())
        if not tokens:
            vector[0] = 1.0
            return vector
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "little") % self.dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            return vector
        return [value / norm for value in vector]
