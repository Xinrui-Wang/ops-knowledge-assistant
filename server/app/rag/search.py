"""检索调试 CLI。

用法（在 server/ 目录下）：
    python -m app.rag.search "一线城市出差住宿标准"
    python -m app.rag.search "P2 工单响应时限" --top-k 3 --json
"""

from __future__ import annotations

import argparse
import json

from app.config import settings
from app.rag.bm25 import BM25Index
from app.rag.chunker import load_chunks, write_chunks_jsonl


def main() -> None:
    parser = argparse.ArgumentParser(description="BM25 检索调试")
    parser.add_argument("query", help="查询语句")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    chunks = load_chunks()
    write_chunks_jsonl(chunks, settings.chunks_path)
    index = BM25Index(chunks)
    hits = index.search(args.query, top_k=args.top_k)

    if args.json:
        print(
            json.dumps(
                [
                    {"score": round(score, 4), **chunk.to_dict()}
                    for chunk, score in hits
                ],
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    print(f"查询：{args.query}    （语料 {len(chunks)} 个条款）\n")
    if not hits:
        print("（无命中）")
        return
    for rank, (chunk, score) in enumerate(hits, start=1):
        snippet = chunk.text.replace("\n", " ")
        if len(snippet) > 120:
            snippet = snippet[:120] + "…"
        print(f"{rank}. [{score:6.2f}] {chunk.citation}")
        print(f"   {snippet}")
        print(f"   id={chunk.chunk_id}  section={chunk.section}\n")


if __name__ == "__main__":
    main()
