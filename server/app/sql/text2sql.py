"""根据 linked schema 生成 SQL。

生成器拿到的上下文只包含 schema linking 选中的表和列——物理上编不出别的表。
"""

from __future__ import annotations

from app.llm import LLMClient
from app.sql.guardrails import clean_llm_sql, validate_sql
from app.sql.schema_linking import LinkedSchema, load_schema

SQL_SYSTEM = """你是 SQLite 专家。根据用户问题写一条查询语句。

规则：
- 只输出 SQL，不要解释，不要 markdown 围栏；
- 只能使用下面列出的表及其列，不得使用其他表；
- 日期列是 TEXT，格式 YYYY-MM-DD，筛选季度用 BETWEEN；
- 按某个维度分组统计时，额外输出 COUNT(*) AS sample_count（用于判断样本量）；
- 需要排名时用 ORDER BY，必要时加 LIMIT。

示例：
用户问题：第三季度各大区销售额排名
SQL：
SELECT r.region_name, ROUND(SUM(s.amount), 2) AS sales
FROM fact_sales s
JOIN dim_region r ON s.region_id = r.region_id
WHERE s.order_date BETWEEN '2026-07-01' AND '2026-09-30'
GROUP BY r.region_name
ORDER BY sales DESC
LIMIT 10"""


def build_context(linked: LinkedSchema, schema: dict | None = None) -> str:
    schema = schema or load_schema()
    lines: list[str] = ["可用表和列（★ 为 schema linking 判定的相关列；同表其他列也可使用）："]
    for table in linked.tables:
        meta = schema[table]
        lines.append(f"表 {table}：{meta['comment']}")
        focus = set(linked.columns.get(table, []))
        for col, desc in meta["columns"].items():
            mark = " ★" if col in focus else ""
            lines.append(f"  - {col}：{desc}{mark}")

    if linked.enum_values:
        lines.append("\n枚举值（值链接，必须原样使用）：")
        for key, vals in linked.enum_values.items():
            lines.append(f"  {key} ∈ {vals}")

    return "\n".join(lines)


def generate_sql(
    question: str,
    linked: LinkedSchema,
    schema: dict | None = None,
    llm: LLMClient | None = None,
) -> str:
    context = build_context(linked, schema)
    messages = [
        {"role": "system", "content": SQL_SYSTEM},
        {"role": "user", "content": f"{context}\n\n用户问题：{question}"},
    ]
    raw = (llm or LLMClient()).chat(messages, max_tokens=600)
    return validate_sql(clean_llm_sql(raw))
