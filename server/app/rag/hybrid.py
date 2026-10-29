"""RRF 融合与统一检索入口。

RRF（Reciprocal Rank Fusion）只看排名、不看分数：
    score(d) = Σ 1 / (k + rank_i(d))
这样 BM25 的分值量纲和余弦相似度量纲不一致也不需要调权重。
"""

from __future__ import annotations

from collections import defaultdict

from app.rag.bm25 import BM25Index
from app.rag.chunker import Chunk
from app.rag.embeddings import EmbeddingClient
from app.rag.vector_store import VectorIndex


def rrf_fuse(rankings: list[list[str]], k: int = 60) -> list[tuple[str, float]]:
    scores: dict[str, float] = defaultdict(float)
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] += 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


class HybridRetriever:
    def __init__(
        self,
        chunks: list[Chunk],
        vector_index: VectorIndex | None = None,
        client: EmbeddingClient | None = None,
        rrf_k: int = 60,
    ):
        self.chunks = chunks
        self.by_id = {chunk.chunk_id: chunk for chunk in chunks}
        self.bm25 = BM25Index(chunks)
        self.vector_index = vector_index
        self.client = client
        self.rrf_k = rrf_k

    def _embedding_client(self) -> EmbeddingClient:
        if self.client is None:
            self.client = EmbeddingClient()
        return self.client

    def search(
        self, query: str, mode: str = "hybrid", top_k: int = 5
    ) -> list[tuple[Chunk, float]]:
        if mode not in ("bm25", "vector", "hybrid"):
            raise ValueError(f"未知检索模式：{mode}")

        sparse_hits = self.bm25.search(query, top_k=top_k * 3)
        sparse_ids = [chunk.chunk_id for chunk, _ in sparse_hits]

        if mode == "bm25":
            return sparse_hits[:top_k]

        if self.vector_index is None:
            raise RuntimeError("向量索引未加载，请先运行：python -m app.rag.index")

        dense_hits = self.vector_index.search(
            self._embedding_client().embed_query(query), top_k=top_k * 3
        )

        if mode == "vector":
            return [(self.by_id[chunk_id], score) for chunk_id, score in dense_hits[:top_k]]

        dense_ids = [chunk_id for chunk_id, _ in dense_hits]
        fused = rrf_fuse([sparse_ids, dense_ids], k=self.rrf_k)
        return [(self.by_id[chunk_id], score) for chunk_id, score in fused[:top_k]]
