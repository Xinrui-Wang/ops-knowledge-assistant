"""Text2SQL 调试 CLI。

用法（在 server/ 目录下）：
    python -m app.sql.cli "第三季度各大区销售额排名"
"""

from __future__ import annotations

import sys

from app.sql.db import execute
from app.sql.schema_linking import collect_enum_values, link_schema, load_schema
from app.sql.text2sql import generate_sql


def run(question: str) -> None:
    schema = load_schema()

    print(f"问题：{question}\n")
    print("[1] Schema Linking")
    linked = link_schema(question, schema)
    print(f"    候选表（向量粗筛）：{linked.candidates}")
    print(f"    选中表：{linked.tables}")
    print(f"    选中列：{linked.columns}")
    print(f"    理由：{linked.reason}")

    linked.enum_values = collect_enum_values(linked)
    if linked.enum_values:
        print(f"    值链接：{linked.enum_values}")

    print("\n[2] 生成 SQL")
    sql = generate_sql(question, linked, schema)
    print(f"    {sql}")

    print("\n[3] 执行")
    columns, rows = execute(sql)
    print(f"    返回 {len(rows)} 行，列：{columns}")
    for row in rows[:10]:
        print(f"    {row}")


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit('用法：python -m app.sql.cli "你的问题"')
    run(" ".join(sys.argv[1:]))


if __name__ == "__main__":
    main()
