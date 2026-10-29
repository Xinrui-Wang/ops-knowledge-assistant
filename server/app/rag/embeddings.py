"""OpenAI 兼容协议的 Embedding 客户端。

注意：Qwen3-Embedding 是指令感知模型，**查询侧**要加 instruction，文档侧不加。
这与训练时「query 带指令、document 不带」的构造保持一致。
"""

from __future__ import annotations

import httpx
import numpy as np

from app.config import settings

QUERY_INSTRUCTION = (
    "Given a question about Chinese enterprise operations policy, "
    "retrieve the policy clause that answers the question."
)


class EmbeddingClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        dimensions: int | None = None,
    ):
        self.base_url = (base_url or settings.embed_base_url).rstrip("/")
        self.api_key = api_key or settings.embed_api_key
        self.model = model or settings.embed_model
        self.dimensions = dimensions if dimensions is not None else settings.embed_dimensions

        if not self.base_url or not self.api_key:
            raise RuntimeError(
                "未配置 Embedding 服务：请设置 OKA_EMBED_BASE_URL / OKA_EMBED_API_KEY（可参考 .env.example）"
            )

    def _request(self, texts: list[str]) -> list[list[float]]:
        payload: dict = {"model": self.model, "input": texts}
        if self.dimensions:
            payload["dimensions"] = self.dimensions

        resp = httpx.post(
            f"{self.base_url}/embeddings",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
            timeout=settings.embed_timeout,
        )
        resp.raise_for_status()
        return [item["embedding"] for item in resp.json()["data"]]

    def embed_documents(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            vectors.extend(self._request(texts[start : start + batch_size]))
        return np.asarray(vectors, dtype=np.float32)

    def embed_query(self, query: str) -> np.ndarray:
        return np.asarray(self._request([f"{QUERY_INSTRUCTION}\n{query}"])[0], dtype=np.float32)
