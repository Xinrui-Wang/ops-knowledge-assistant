"""指标口径表：把业务黑话钉死成可执行的计算方式。

没有登记的指标不猜——由上层显式声明「文档未定义该口径」。
"""

from __future__ import annotations

import json

from app.config import DATA_DIR


def load_metrics() -> list[dict]:
    path = DATA_DIR / "metrics.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("metrics", [])


def match_metrics(question: str) -> list[dict]:
    """按别名做子串匹配。中文不需要分词，直接包含判断即可。"""
    hits: list[dict] = []
    for metric in load_metrics():
        if any(alias in question for alias in metric.get("aliases", [])):
            hits.append(metric)
    return hits
