"""统一问答编排：路由 → 检索/查询 → 生成答案 / 对账。

以「事件流」的形式产出，后续接前端时可直接映射成 SSE：
    route / retrieved / schema_linking / metrics / sql_generated / sql_executed /
    reconciliation / answer_delta / citations / done / error
"""

from __future__ import annotations

from typing import Iterator

from app.chat.answerer import answer_with_citations, summarize_sql
from app.chat.reconciler import compose_answer, reconcile
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


def retrieve(question: str, top_k: int = 5) -> list[tuple[Chunk, float]]:
    return get_retriever().search(question, mode="hybrid", top_k=top_k)


def sources_event(hits: list[tuple[Chunk, float]]) -> dict:
    return {
        "type": "retrieved",
        "sources": [
            {"citation": chunk.citation, "chunk_id": chunk.chunk_id, "score": round(score, 5)}
            for chunk, score in hits
        ],
    }


def citations_event(hits: list[tuple[Chunk, float]]) -> dict:
    return {
        "type": "citations",
        "items": [
            {"index": i, "citation": chunk.citation, "chunk_id": chunk.chunk_id}
            for i, (chunk, _) in enumerate(hits, start=1)
        ],
    }


def sql_events(question: str) -> Iterator[dict]:
    """生成 SQL 并执行，产出过程事件；最后一项是执行结果。"""
    schema = load_schema()
    linked = link_schema(question, schema)
    linked.enum_values = collect_enum_values(linked)
    yield {"type": "schema_linking", "detail": linked.to_dict()}

    metrics = match_metrics(question)
    yield {"type": "metrics", "items": [m["name"] for m in metrics] or ["（未匹配到登记口径）"]}

    sql = generate_sql(question, linked, schema, metrics=metrics)
    yield {"type": "sql_generated", "sql": sql}

    columns, rows = execute(sql)
    yield {"type": "sql_executed", "sql": sql, "columns": columns, "rows": rows}


def run(question: str) -> Iterator[dict]:
    try:
        decision = route(question)
        yield {"type": "route", "route": decision.route, "reason": decision.reason}

        hits: list[tuple[Chunk, float]] | None = None
        sql_payload: dict | None = None

        if decision.route in ("rag", "hybrid"):
            hits = retrieve(question)
            yield sources_event(hits)

        if decision.route in ("sql", "hybrid"):
            for event in sql_events(question):
                if event["type"] == "sql_executed":
                    sql_payload = event
                yield event

        if decision.route == "rag" and hits is not None:
            answer, _ = answer_with_citations(question, hits)
            yield {"type": "answer_delta", "delta": answer}
            yield citations_event(hits)

        elif decision.route == "sql" and sql_payload is not None:
            summary = summarize_sql(
                question,
                sql_payload["sql"],
                sql_payload["columns"],
                sql_payload["rows"],
            )
            yield {"type": "answer_delta", "delta": summary}

        elif decision.route == "hybrid" and hits is not None and sql_payload is not None:
            verdict = reconcile(
                question,
                hits,
                sql_payload["sql"],
                sql_payload["columns"],
                sql_payload["rows"],
            )
            yield {"type": "reconciliation", "detail": verdict}
            yield {"type": "answer_delta", "delta": compose_answer(verdict)}
            yield citations_event(hits)

        yield {"type": "done"}
    except Exception as exc:  # noqa: BLE001
        yield {"type": "error", "message": f"{type(exc).__name__}: {exc}"}
