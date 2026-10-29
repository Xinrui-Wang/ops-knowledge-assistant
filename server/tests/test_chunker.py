from app.rag.chunker import load_chunks


def test_total_clause_count():
    chunks = load_chunks()
    assert len(chunks) == 47


def test_every_chunk_has_citation_metadata():
    for chunk in load_chunks():
        assert chunk.doc_title, chunk.chunk_id
        assert chunk.clause_no.startswith("第"), chunk.chunk_id
        assert chunk.section.startswith("第"), chunk.chunk_id
        assert chunk.text, chunk.chunk_id


def test_lodging_clause_metadata():
    chunks = {chunk.chunk_id: chunk for chunk in load_chunks()}
    chunk = chunks["01-销售费用报销管理制度#第五条"]
    assert chunk.doc_title == "销售费用报销管理制度"
    assert chunk.doc_no == "LX-OPS-FIN-2024-006"
    assert chunk.section == "第二章 费用标准"
    assert chunk.clause_title == "住宿费标准"
    assert "600" in chunk.text
    assert chunk.citation == "《销售费用报销管理制度》第五条（住宿费标准）"


def test_clause_body_contains_list_items():
    chunks = {chunk.chunk_id: chunk for chunk in load_chunks()}
    chunk = chunks["03-售后服务响应管理办法#第三条"]
    assert "P1（重大故障）" in chunk.text
    assert "P3（咨询类）" in chunk.text
