"""统一问答编排：路由 → 检索/查询 → 生成答案。

以「事件流」的形式产出，后续接前端时可以直接映射成 SSE：
    route / retrieved / schema_linking / sql_generated / sql_executed /
    answer_delta / done / error
"""

from __future__ import annotations

from typing import Iterator

from app.chat.answerer import answer_with_citations, summarize_sql
from app.chat.router import route
from app.config import settings
from app.rag.chunker import Chunk, load_chunks
from app.rag.hybrid import HybridRetriever
from app.rag.vector_store import VectorIndex
from app.sql.db import execute
from app.sql.metrics import match_metrics
from app.sql.schema_linking import collect_enum_values, link_schema, load_schema
from app.sql.text2sql import generate_sql

_retriever: HybridRetriever | None = None


def get_retriever() -> HybridRetriever:
    global _retriever
    if _retriever is None:
        chunks = load_chunks()
        index = VectorIndex.load(settings.index_path) if settings.index_path.exists() else None
        _retriever = HybridRetriever(chunks, vector_index=index)
    return _retriever


def _rag_events(question: str) -> Iterator[dict]:
    hits = get_retriever().search(question, mode="hybrid", top_k=5)
    yield {
        "type": "retrieved",
        "sources": [
            {"citation": chunk.citation, "chunk_id": chunk.chunk_id, "score": round(score, 5)}
            for chunk, score in hits
        ],
    }
    answer, citations = answer_with_citations(question, hits)
    yield {"type": "answer_delta", "delta": answer}
    yield {"type": "citations", "items": citations}


def _sql_events(question: str) -> Iterator[dict]:
    schema = load_schema()
    linked = link_schema(question, schema)
    linked.enum_values = collect_enum_values(linked)
    yield {"type": "schema_linking", "detail": linked.to_dict()}

    metrics = match_metrics(question)
    yield {"type": "metrics", "items": [m["name"] for m in metrics] or ["（未匹配到登记口径）"]}

    sql = generate_sql(question, linked, schema, metrics=metrics)
    yield {"type": "sql_generated", "sql": sql}

    columns, rows = execute(sql)
    yield {"type": "sql_executed", "columns": columns, "rows": rows}

    yield {"type": "answer_delta", "delta": summarize_sql(question, sql, columns, rows)}


def run(question: str) -> Iterator[dict]:
    try:
        decision = route(question)
        yield {"type": "route", "route": decision.route, "reason": decision.reason}

        if decision.route in ("rag", "hybrid"):
            yield from _rag_events(question)
        if decision.route in ("sql", "hybrid"):
            yield from _sql_events(question)

        yield {"type": "done"}
    except Exception as exc:  # noqa: BLE001
        yield {"type": "error", "message": f"{type(exc).__name__}: {exc}"}
