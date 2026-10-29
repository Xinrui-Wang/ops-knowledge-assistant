"""答案生成：RAG 引用式回答 + SQL 结果自然语言摘要。"""

from __future__ import annotations

import json

from app.llm import LLMClient
from app.rag.chunker import Chunk

ANSWER_SYSTEM = """你是企业运营知识助手。只能依据【参考资料】回答，不得编造。

规则：
- 每个结论后面用 [编号] 标注来源，编号对应参考资料的编号；
- 条款编号要原样写出，例如"《销售费用报销管理制度》第五条"；
- 如果参考资料不足以回答，直接说明"现有制度中未找到相关规定"，不要猜；
- 用中文，简洁，先给结论再给依据。"""

SQL_SUMMARY_SYSTEM = """你是数据分析助手。根据 SQL 查询结果，用中文简要回答用户问题。

规则：
- 先给结论，再列关键数字；
- 如果结果中含有 sample_count 且小于 5，必须提示"样本量过小，结论可能不稳定"；
- 不要编造结果里没有的数据；
- 如果结果为空，明确说"未查询到数据"，并提示可能是筛选条件问题。"""


def answer_with_citations(
    question: str,
    hits: list[tuple[Chunk, float]],
    llm: LLMClient | None = None,
) -> tuple[str, list[dict]]:
    sources = "\n\n".join(
        f"[{i}] {chunk.citation}\n{chunk.text}" for i, (chunk, _) in enumerate(hits, start=1)
    )
    messages = [
        {"role": "system", "content": ANSWER_SYSTEM},
        {"role": "user", "content": f"参考资料：\n{sources}\n\n用户问题：{question}"},
    ]
    text = (llm or LLMClient()).chat(messages, max_tokens=700)
    citations = [
        {"index": i, "citation": chunk.citation, "chunk_id": chunk.chunk_id}
        for i, (chunk, _) in enumerate(hits, start=1)
    ]
    return text, citations


def summarize_sql(
    question: str,
    sql: str,
    columns: list[str],
    rows: list[dict],
    llm: LLMClient | None = None,
) -> str:
    payload = {"columns": columns, "rows": rows[:20]}
    messages = [
        {"role": "system", "content": SQL_SUMMARY_SYSTEM},
        {
            "role": "user",
            "content": (
                f"用户问题：{question}\n\n执行的 SQL：\n{sql}\n\n"
                f"查询结果：\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
            ),
        },
    ]
    return (llm or LLMClient()).chat(messages, max_tokens=500)
