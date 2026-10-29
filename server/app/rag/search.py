"""检索调试 CLI。

用法（在 server/ 目录下）：
    python -m app.rag.search "一线城市出差住宿标准" --mode hybrid
    python -m app.rag.search "住酒店能报多少钱" --mode vector --top-k 3
    python -m app.rag.search "第五条" --mode bm25
"""

from __future__ import annotations

import argparse
import json

from app.config import settings
from app.rag.chunker import load_chunks, write_chunks_jsonl
from app.rag.hybrid import HybridRetriever
from app.rag.vector_store import VectorIndex


def main() -> None:
    parser = argparse.ArgumentParser(description="检索调试（BM25 / 向量 / RRF 混合）")
    parser.add_argument("query", help="查询语句")
    parser.add_argument("--mode", choices=["bm25", "vector", "hybrid"], default="hybrid")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    chunks = load_chunks()
    write_chunks_jsonl(chunks, settings.chunks_path)

    vector_index = None
    if args.mode in ("vector", "hybrid"):
        if not settings.index_path.exists():
            raise SystemExit("向量索引不存在，请先运行：python -m app.rag.index")
        vector_index = VectorIndex.load(settings.index_path)

    retriever = HybridRetriever(chunks, vector_index=vector_index)
    hits = retriever.search(args.query, mode=args.mode, top_k=args.top_k)

    if args.json:
        print(
            json.dumps(
                [{"score": round(score, 5), **chunk.to_dict()} for chunk, score in hits],
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    print(f"查询：{args.query}    模式：{args.mode}    语料：{len(chunks)} 条\n")
    if not hits:
        print("（无命中）")
        return
    for rank, (chunk, score) in enumerate(hits, start=1):
        snippet = chunk.text.replace("\n", " ")
        if len(snippet) > 120:
            snippet = snippet[:120] + "…"
        print(f"{rank}. [{score:.5f}] {chunk.citation}")
        print(f"   {snippet}")
        print(f"   id={chunk.chunk_id}\n")


if __name__ == "__main__":
    main()
