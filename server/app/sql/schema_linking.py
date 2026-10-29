"""Schema Linking：问题 → 相关表/列（显式步骤）。

分两级，确保「全量 DDL 不进生成提示词」：
  1. 粗筛（向量）：只用表级描述和问题算相似度，取 Top-N 张表；
  2. 精挑（LLM）：只把候选表的字段说明交给模型，输出结构化 JSON：表、列、理由。

第三层「值链接」由 collect_enum_values 完成：把低基数列的枚举值取出来，
避免模型写出 `WHERE region = '华东'` 这种静默返回 0 行的错。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import numpy as np

from app.config import settings
from app.llm import LLMClient, parse_json
from app.rag.embeddings import EmbeddingClient

# 低基数、适合做值链接的列
CATEGORICAL_COLUMNS = {
    "region_name",
    "region_group",
    "channel",
    "priority",
    "expense_type",
    "city_tier",
    "product_line",
    "product_name",
    "employee_dept",
}

LINK_SYSTEM = """你是企业运营知识助手的 schema 分析器。
根据用户问题，从候选表中选择回答问题所必需的最少表和列，并说明理由。
规则：
- 只能从候选表及其列中选择，不要编造；
- 只选真正需要的列，但必须包含：统计列、筛选条件列（如日期范围、大区）、关联键；
- 只输出 JSON，不要任何解释。

输出格式：
{"tables":["表名"],"columns":{"表名":["列名"]},"reason":"一句话说明为什么选这些表列"}"""


@dataclass
class LinkedSchema:
    candidates: list[str]
    tables: list[str]
    columns: dict[str, list[str]]
    reason: str
    enum_values: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "candidates": self.candidates,
            "tables": self.tables,
            "columns": self.columns,
            "reason": self.reason,
            "enum_values": self.enum_values,
        }


def load_schema() -> dict:
    return json.loads(settings.schema_path.read_text(encoding="utf-8"))["tables"]


def table_text(name: str, meta: dict) -> str:
    cols = "、".join(f"{col}（{desc}）" for col, desc in meta["columns"].items())
    return f"表 {name}：{meta['comment']}。字段：{cols}"


def coarse_filter(
    question: str,
    schema: dict,
    top_n: int = 3,
    embedder: EmbeddingClient | None = None,
) -> list[str]:
    names = list(schema)
    embedder = embedder or EmbeddingClient()
    matrix = embedder.embed_documents([table_text(n, schema[n]) for n in names])
    matrix = matrix / (np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-9)
    query = embedder.embed_query(question)
    query = query / (np.linalg.norm(query) + 1e-9)
    scores = matrix @ query
    order = np.argsort(-scores)[:top_n]
    return [names[i] for i in order]


def link_schema(
    question: str,
    schema: dict | None = None,
    top_n: int = 3,
    llm: LLMClient | None = None,
    embedder: EmbeddingClient | None = None,
) -> LinkedSchema:
    schema = schema or load_schema()
    candidates = coarse_filter(question, schema, top_n=top_n, embedder=embedder)

    catalog = "\n".join(table_text(name, schema[name]) for name in candidates)
    messages = [
        {"role": "system", "content": LINK_SYSTEM},
        {"role": "user", "content": f"候选表：\n{catalog}\n\n用户问题：{question}"},
    ]
    raw = (llm or LLMClient()).chat(messages, max_tokens=400)
    data = parse_json(raw)

    # 校验：丢弃模型编造的、或不在候选集里的表和列
    picked = [t for t in data.get("tables", []) if t in candidates]
    columns: dict[str, list[str]] = {}
    for table, cols in (data.get("columns") or {}).items():
        if table not in picked:
            continue
        valid = [c for c in cols if c in schema[table]["columns"]]
        if valid:
            columns[table] = valid

    if not picked:
        raise ValueError(f"schema linking 未选中任何表，原始输出：{raw[:200]}")

    return LinkedSchema(
        candidates=candidates,
        tables=picked,
        columns=columns,
        reason=str(data.get("reason", "")).strip(),
    )


def collect_enum_values(linked: LinkedSchema, limit: int = 20) -> dict[str, list[str]]:
    """值链接：取出选中列里的低基数枚举值。"""
    from app.sql.db import execute

    values: dict[str, list[str]] = {}
    for table, cols in linked.columns.items():
        for col in cols:
            if col not in CATEGORICAL_COLUMNS:
                continue
            _, rows = execute(
                f'SELECT DISTINCT "{col}" AS v FROM {table} WHERE "{col}" IS NOT NULL LIMIT {limit}'
            )
            found = [str(row["v"]) for row in rows]
            if found:
                values[f"{table}.{col}"] = found
    return values
