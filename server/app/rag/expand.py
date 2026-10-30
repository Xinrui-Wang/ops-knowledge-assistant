"""引用展开：顺着条款里的交叉引用，把被引用的条款一并拉入上下文。

制度文档里常见「住宿标准按《销售费用报销管理制度》第五条规定执行」。
这类条款本身信息量低，但指向的条款往往才是答案所在。
RRF 只看名次，容易把这种「引用型条款」排在前面，展开可以补上真正的依据。
"""

from __future__ import annotations

import re

from app.rag.chunker import Chunk

REFERENCE_RE = re.compile(r"《([^》]+)》\s*(第[一二三四五六七八九十百零]+条)")


def build_lookup(chunks: list[Chunk]) -> dict[str, dict[str, Chunk]]:
    lookup: dict[str, dict[str, Chunk]] = {}
    for chunk in chunks:
        lookup.setdefault(chunk.doc_title, {})[chunk.clause_no] = chunk
    return lookup


def referenced_chunks(chunk: Chunk, lookup: dict[str, dict[str, Chunk]]) -> list[Chunk]:
    found: list[Chunk] = []
    for title, clause_no in REFERENCE_RE.findall(chunk.text):
        target = lookup.get(title, {}).get(clause_no)
        if target is not None and target.chunk_id != chunk.chunk_id:
            found.append(target)
    return found


def expand(
    hits: list[tuple[Chunk, float]],
    all_chunks: list[Chunk],
    max_extra: int = 3,
) -> list[tuple[Chunk, float]]:
    """在检索结果末尾追加被引用条款；已存在的不重复添加。"""
    lookup = build_lookup(all_chunks)
    seen = {chunk.chunk_id for chunk, _ in hits}
    extras: list[Chunk] = []

    for chunk, _score in hits:
        for target in referenced_chunks(chunk, lookup):
            if target.chunk_id in seen:
                continue
            seen.add(target.chunk_id)
            extras.append(target)
            if len(extras) >= max_extra:
                return hits + [(item, 0.0) for item in extras]

    return hits + [(item, 0.0) for item in extras]
