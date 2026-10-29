"""向量索引：numpy 暴力检索。

47 条语料、1024 维，一次矩阵乘法就是全量检索（微秒级），
没必要引入 Chroma / Milvus 这类向量库。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from app.rag.chunker import Chunk
from app.rag.embeddings import EmbeddingClient


def _normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (matrix / norms).astype(np.float32)


class VectorIndex:
    def __init__(self, chunk_ids: list[str], matrix: np.ndarray):
        self.chunk_ids = list(chunk_ids)
        self.matrix = _normalize(np.asarray(matrix, dtype=np.float32))

    @classmethod
    def build(cls, chunks: list[Chunk], client: EmbeddingClient | None = None) -> "VectorIndex":
        client = client or EmbeddingClient()
        matrix = client.embed_documents([chunk.embed_text for chunk in chunks])
        return cls([chunk.chunk_id for chunk in chunks], matrix)

    def search(self, query_vector: np.ndarray, top_k: int = 5) -> list[tuple[str, float]]:
        query = np.asarray(query_vector, dtype=np.float32)
        norm = float(np.linalg.norm(query)) or 1.0
        scores = self.matrix @ (query / norm)
        order = np.argsort(-scores)[:top_k]
        return [(self.chunk_ids[i], float(scores[i])) for i in order]

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(path, ids=np.array(self.chunk_ids), matrix=self.matrix)
        return path

    @classmethod
    def load(cls, path: Path) -> "VectorIndex":
        data = np.load(path, allow_pickle=False)
        return cls(data["ids"].tolist(), data["matrix"])
