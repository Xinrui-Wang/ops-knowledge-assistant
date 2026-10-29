from app.rag.hybrid import rrf_fuse


def test_rrf_prefers_agreement_across_rankings():
    sparse = ["a", "b", "c"]
    dense = ["c", "a", "d"]

    fused = dict(rrf_fuse([sparse, dense], k=60))

    # a 在两个榜单里都靠前，应排第一
    assert max(fused, key=fused.get) == "a"
    # 只出现在一个榜单末尾的 d，分数应低于两榜都在的 c
    assert fused["c"] > fused["d"]
    assert fused["a"] > fused["b"]


def test_rrf_is_order_independent_for_identical_rankings():
    ranking = ["x", "y", "z"]
    fused = [chunk_id for chunk_id, _ in rrf_fuse([ranking, ranking], k=60)]
    assert fused == ranking
