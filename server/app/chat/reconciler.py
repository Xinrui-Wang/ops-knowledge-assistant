"""制度与数据的对账。

原则：不让模型"选一个信"，只让它判断「一致 / 冲突 / 无法比对」，
最终回复由代码按固定模板拼装——冲突时两边都必须出现在回答里。
"""

from __future__ import annotations

import json

from app.llm import LLMClient, parse_json
from app.rag.chunker import Chunk

RECONCILE_SYSTEM = """你是企业运营知识助手的口径核对员。
下面给你【制度条款】和【数据库查询结果】，判断二者是否一致。

status 四选一：
- consistent：制度要求与实际数据相符（实际做到了）
- violation：制度写明了标准，实际数据未达到该标准（不达标 / 超标 / 违规）
- conflict：两方对同一事实给出互相矛盾的陈述，无法用"达标/不达标"概括
- insufficient：制度没有可比对的量化要求，或双方口径不同无法比较

只输出 JSON：
{"status":"consistent|violation|conflict|insufficient",
 "policy":"制度要求的要点（必须带条款号）",
 "data":"数据反映的实际情况（必须带关键数字）",
 "explanation":"判断依据；违反或冲突时指出具体差在哪里；数据不足时说明缺什么"}

规则：
- 只能依据给定材料，不得补充外部知识；
- 「实际未达标」属于 violation，不要因为口径一致就判 consistent。"""

CONFLICT_NOTE = "\n\n（制度与数据同时呈现，未做取舍；建议由业务方确认口径后再下结论。）"


def reconcile(
    question: str,
    policy_hits: list[tuple[Chunk, float]],
    sql: str,
    columns: list[str],
    rows: list[dict],
    llm: LLMClient | None = None,
) -> dict:
    policy_text = "\n\n".join(
        f"[{i}] {chunk.citation}\n{chunk.text}"
        for i, (chunk, _) in enumerate(policy_hits, start=1)
    )
    data_text = json.dumps({"columns": columns, "rows": rows[:20]}, ensure_ascii=False, indent=2)

    messages = [
        {"role": "system", "content": RECONCILE_SYSTEM},
        {
            "role": "user",
            "content": (
                f"用户问题：{question}\n\n【制度条款】\n{policy_text}\n\n"
                f"【数据库查询结果】\n执行 SQL：\n{sql}\n结果：\n{data_text}"
            ),
        },
    ]
    raw = (llm or LLMClient()).chat(messages, max_tokens=600)

    try:
        data = parse_json(raw)
    except ValueError:
        return {
            "status": "insufficient",
            "policy": "",
            "data": "",
            "explanation": f"对账结果无法解析，原始输出：{raw[:120]}",
        }

    status = str(data.get("status", "")).strip().lower()
    if status not in ("consistent", "violation", "conflict", "insufficient"):
        status = "insufficient"

    return {
        "status": status,
        "policy": str(data.get("policy", "")).strip(),
        "data": str(data.get("data", "")).strip(),
        "explanation": str(data.get("explanation", "")).strip(),
    }


def compose_answer(verdict: dict) -> str:
    """按固定模板拼装：冲突时两边都出现，不静默择一。"""
    label = {
        "consistent": "✅ 制度要求与实际数据相符",
        "violation": "⚠️ 实际数据未达到制度要求",
        "conflict": "⚠️ 制度与数据存在冲突",
        "insufficient": "❔ 无法直接比对",
    }.get(verdict["status"], "❔ 无法直接比对")

    parts = [label]
    if verdict.get("policy"):
        parts.append(f"制度要求：{verdict['policy']}")
    if verdict.get("data"):
        parts.append(f"实际数据：{verdict['data']}")
    if verdict.get("explanation"):
        parts.append(verdict["explanation"])
    if verdict["status"] in ("conflict", "violation"):
        parts.append(CONFLICT_NOTE.strip())
    return "\n\n".join(parts)
