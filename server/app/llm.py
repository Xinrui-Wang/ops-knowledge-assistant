"""OpenAI 兼容的 Chat 客户端。

默认关闭思维链（enable_thinking=False）：路由、schema linking、写 SQL 这类任务
不需要长推理，开着会慢 10 倍且更容易跑偏。
"""

from __future__ import annotations

import json
import re

import httpx

from app.config import settings


class LLMClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self.base_url = (base_url or settings.llm_base_url).rstrip("/")
        self.api_key = api_key or settings.llm_api_key
        self.model = model or settings.llm_model
        if not self.base_url or not self.api_key:
            raise RuntimeError("未配置 LLM：请设置 OKA_LLM_BASE_URL / OKA_LLM_API_KEY")

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.0,
        max_tokens: int = 800,
        enable_thinking: bool = False,
    ) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "enable_thinking": enable_thinking,
        }
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
            timeout=settings.llm_timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"].get("content") or ""


def parse_json(text: str) -> dict:
    """从模型输出里抠出 JSON（容忍 ```json 围栏和前后废话）。"""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"模型输出里没有 JSON：{text[:200]}")
    return json.loads(text[start : end + 1])
