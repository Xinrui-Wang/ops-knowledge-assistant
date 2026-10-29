"""SQL 护栏：单条、只读、只允许查询、强制 LIMIT。

这是"提示词之外"的硬约束：即使模型被诱导写出 DELETE，这里也会拒绝。
"""

from __future__ import annotations

import re

FORBIDDEN_RE = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|pragma|vacuum|truncate)\b",
    re.IGNORECASE,
)
SELECT_RE = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)
LIMIT_RE = re.compile(r"\blimit\b", re.IGNORECASE)
FENCE_RE = re.compile(r"```(?:sql)?\s*(.*?)```", re.S | re.IGNORECASE)


class UnsafeSQL(ValueError):
    pass


def clean_llm_sql(text: str) -> str:
    """去掉 markdown 围栏、结尾分号与多余空白。"""
    text = text.strip()
    fenced = FENCE_RE.search(text)
    if fenced:
        text = fenced.group(1)
    return text.strip().rstrip(";").strip()


def validate_sql(sql: str, max_rows: int = 200) -> str:
    if not sql:
        raise UnsafeSQL("SQL 为空")
    if ";" in sql:
        raise UnsafeSQL("只允许单条语句")
    if not SELECT_RE.match(sql):
        raise UnsafeSQL("只允许 SELECT / WITH 查询")
    hit = FORBIDDEN_RE.search(sql)
    if hit:
        raise UnsafeSQL(f"包含禁止的关键字：{hit.group(0)}")
    if not LIMIT_RE.search(sql):
        sql = f"{sql}\nLIMIT {max_rows}"
    return sql
