import pytest

from app.rag.bm25 import BM25Index
from app.rag.chunker import load_chunks


@pytest.fixture(scope="module")
def index():
    return BM25Index(load_chunks())


@pytest.mark.parametrize(
    ("query", "expected_chunk_id"),
    [
        ("一线城市出差住宿标准是多少", "01-销售费用报销管理制度#第五条"),
        ("P2 工单首次响应时限是多久", "03-售后服务响应管理办法#第四条"),
        ("渠道返利比例怎么算", "04-渠道返利政策#第四条"),
        ("客户数据导出需要谁审批", "05-客户信息与数据安全规范#第四条"),
        ("出差要提前几天申请", "02-差旅与出差管理办法#第三条"),
    ],
)
def test_top1_lands_on_expected_clause(index, query, expected_chunk_id):
    hits = index.search(query, top_k=3)
    assert hits, f"「{query}」没有命中任何条款"
    assert hits[0][0].chunk_id == expected_chunk_id, (
        f"「{query}」Top1 是 {hits[0][0].chunk_id}，期望 {expected_chunk_id}"
    )
