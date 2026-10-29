"""需要真实 Embedding 服务的用例；未配置 key 时自动跳过。"""

import pytest

from app.config import settings

pytestmark = pytest.mark.skipif(
    not settings.embed_api_key, reason="未配置 OKA_EMBED_API_KEY，跳过真实 embedding 调用"
)


def test_embed_query_returns_configured_dimensions():
    from app.rag.embeddings import EmbeddingClient

    vec = EmbeddingClient().embed_query("一线城市住宿标准")
    assert vec.shape == (settings.embed_dimensions,)
    assert float((vec**2).sum()) > 0
