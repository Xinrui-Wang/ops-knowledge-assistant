#!/usr/bin/env python3
"""自测用例：按作业要求覆盖 纯 RAG / 纯 SQL / HYBRID / 歧义 / 冲突 五类。

用法（仓库根目录）：
    python eval/run_eval.py
    python eval/run_eval.py --only conflict
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from app.chat.orchestrator import run  # noqa: E402

CASES_PATH = Path(__file__).resolve().parent / "cases.json"


def collect(question: str) -> list[dict]:
    return list(run(question))


def first(events: list[dict], kind: str) -> dict | None:
    return next((event for event in events if event["type"] == kind), None)


def check(events: list[dict], expect: dict) -> list[str]:
    problems: list[str] = []

    error = first(events, "error")
    if error:
        problems.append(f"运行出错：{error['message']}")
        return problems

    route = first(events, "route")
    if expect.get("route") and (route is None or route["route"] not in expect["route"]):
        got = route["route"] if route else "无"
        problems.append(f"路由不符：期望 {expect['route']}，实际 {got}")

    if "status" in expect:
        reconciliation = first(events, "reconciliation")
        got = reconciliation["detail"]["status"] if reconciliation else "无"
        if got not in expect["status"]:
            problems.append(f"对账状态不符：期望 {expect['status']}，实际 {got}")

    if "min_rows" in expect:
        executed = first(events, "sql_executed")
        rows = len(executed["rows"]) if executed else 0
        if rows < expect["min_rows"]:
            problems.append(f"结果行数不足：期望 ≥{expect['min_rows']}，实际 {rows}")

    if "citations_contain" in expect:
        citations = first(events, "citations")
        texts = [item["citation"] for item in citations["items"]] if citations else []
        for needle in expect["citations_contain"]:
            if not any(needle in text for text in texts):
                problems.append(f"引用缺少：{needle}")

    answer = "".join(event["delta"] for event in events if event["type"] == "answer_delta")
    if expect.get("answer_not_empty") and not answer.strip():
        problems.append("答案为空")
    for needle in expect.get("answer_contains", []):
        if needle not in answer:
            problems.append(f"答案缺少关键内容：{needle}")

    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description="运行自测用例")
    parser.add_argument("--only", help="只跑 id 或 category 中包含该关键字的用例")
    args = parser.parse_args()

    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]
    if args.only:
        cases = [
            case
            for case in cases
            if args.only in case["id"] or args.only in case["category"]
        ]

    failures = 0
    for case in cases:
        print(f"\n[{case['id']}] {case['category']}")
        print(f"  问：{case['question']}")
        try:
            events = collect(case["question"])
            problems = check(events, case["expect"])
        except Exception as exc:  # noqa: BLE001
            problems = [f"异常：{type(exc).__name__}: {exc}"]

        if problems:
            failures += 1
            print("  ✗ 失败")
            for problem in problems:
                print(f"    - {problem}")
        else:
            route = first(events, "route")
            detail = f"route={route['route']}" if route else "route=?"
            reconciliation = first(events, "reconciliation")
            if reconciliation:
                detail += f", status={reconciliation['detail']['status']}"
            print(f"  ✓ 通过（{detail}）")

    print(f"\n共 {len(cases)} 条，失败 {failures} 条")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
