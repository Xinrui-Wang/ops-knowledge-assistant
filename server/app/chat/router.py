"""意图路由：rag / sql / hybrid。

刻意用「定义 + 反例」的提示词，而不是让模型自由发挥——
实测同一模型、同一问题，提示词含糊时会把"住宿标准"判成 sql。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.llm import LLMClient, parse_json

VALID_ROUTES = {"rag", "sql", "hybrid"}

ROUTE_SYSTEM = """你是企业运营知识助手的路由器。判断用户问题该走哪条检索路径。

- rag：问规章制度、政策、条款、流程"是怎么规定的"（答案在文档里）
- sql：问具体业务数据的数值、排名、趋势、比率（答案在数据库里）
- hybrid：既要比对制度要求、又要看实际数据，或问题同时涉及两者

反例参考：
- "住宿标准是多少" → rag（问制度规定，不是问实际花了多少）
- "销售部住宿平均花了多少" → sql（问实际数据）
- "住宿有没有超标" → hybrid（既要标准，也要实际）

只输出 JSON：{"route":"rag|sql|hybrid","reason":"一句话理由"}"""


@dataclass
class RouteDecision:
    route: str
    reason: str


def route(question: str, llm: LLMClient | None = None) -> RouteDecision:
    messages = [
        {"role": "system", "content": ROUTE_SYSTEM},
        {"role": "user", "content": question},
    ]
    raw = (llm or LLMClient()).chat(messages, max_tokens=120)
    try:
        data = parse_json(raw)
    except ValueError:
        # 解析失败时不猜，落到 hybrid（两条都跑，宁可多查不可漏答）
        return RouteDecision("hybrid", f"路由输出无法解析，降级为 hybrid：{raw[:80]}")

    decision = str(data.get("route", "")).strip().lower()
    if decision not in VALID_ROUTES:
        return RouteDecision("hybrid", f"路由结果非法（{decision}），降级为 hybrid")

    return RouteDecision(decision, str(data.get("reason", "")).strip())
