"""统一问答 CLI（前端之前的验证入口）。

用法（在 server/ 目录下）：
    python -m app.chat.cli "一线城市出差住宿标准是多少"
"""

from __future__ import annotations

import json
import sys

from app.chat.orchestrator import run


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit('用法：python -m app.chat.cli "你的问题"')
    question = " ".join(sys.argv[1:])
    print(f"问题：{question}\n" + "=" * 60)

    for event in run(question):
        kind = event["type"]
        if kind == "route":
            print(f"\n[route] {event['route']}  —  {event['reason']}")
        elif kind == "retrieved":
            print(f"\n[retrieved] 命中 {len(event['sources'])} 条：")
            for src in event["sources"]:
                print(f"   - {src['citation']}  (score={src['score']})")
        elif kind == "schema_linking":
            detail = event["detail"]
            print(f"\n[schema_linking] 表={detail['tables']}")
            print(f"   理由：{detail['reason']}")
            if detail["enum_values"]:
                print(f"   值链接：{detail['enum_values']}")
        elif kind == "metrics":
            print(f"\n[metrics] 命中口径：{event['items']}")
        elif kind == "sql_generated":
            print(f"\n[sql_generated]\n{event['sql']}")
        elif kind == "sql_executed":
            print(f"\n[sql_executed] 返回 {len(event['rows'])} 行")
            for row in event["rows"][:5]:
                print(f"   {row}")
        elif kind == "answer_delta":
            print("\n[answer]\n" + event["delta"])
        elif kind == "citations":
            print("\n[citations]")
            for item in event["items"]:
                print(f"   [{item['index']}] {item['citation']}")
        elif kind == "error":
            print(f"\n[error] {event['message']}")
        elif kind == "done":
            print("\n" + "=" * 60 + "\n完成")


if __name__ == "__main__":
    main()
