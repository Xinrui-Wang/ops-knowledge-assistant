from app.rag.chunker import load_chunks
from app.rag.expand import expand, referenced_chunks, build_lookup


def test_finds_cross_reference_in_clause():
    chunks = load_chunks()
    by_id = {chunk.chunk_id: chunk for chunk in chunks}
    seed = by_id["02-差旅与出差管理办法#第六条"]

    targets = referenced_chunks(seed, build_lookup(chunks))

    assert [chunk.chunk_id for chunk in targets] == ["01-销售费用报销管理制度#第五条"]


def test_expand_appends_referenced_clause():
    chunks = load_chunks()
    by_id = {chunk.chunk_id: chunk for chunk in chunks}
    seed = by_id["02-差旅与出差管理办法#第六条"]

    expanded = expand([(seed, 1.0)], chunks)
    ids = [chunk.chunk_id for chunk, _ in expanded]

    assert ids[0] == seed.chunk_id
    assert "01-销售费用报销管理制度#第五条" in ids


def test_expand_does_not_duplicate_existing_hit():
    chunks = load_chunks()
    by_id = {chunk.chunk_id: chunk for chunk in chunks}
    seed = by_id["02-差旅与出差管理办法#第六条"]
    target = by_id["01-销售费用报销管理制度#第五条"]

    expanded = expand([(seed, 1.0), (target, 0.5)], chunks)
    ids = [chunk.chunk_id for chunk, _ in expanded]

    assert ids.count(target.chunk_id) == 1


def test_expand_is_noop_for_clause_without_reference():
    chunks = load_chunks()
    by_id = {chunk.chunk_id: chunk for chunk in chunks}
    seed = by_id["05-客户信息与数据安全规范#第三条"]

    expanded = expand([(seed, 1.0)], chunks)

    assert len(expanded) == 1
