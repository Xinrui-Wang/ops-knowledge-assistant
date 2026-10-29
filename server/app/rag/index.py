"""构建向量索引。

用法（在 server/ 目录下）：
    python -m app.rag.index            # 全量重建
"""

from __future__ import annotations

from app.config import settings
from app.rag.chunker import load_chunks, write_chunks_jsonl
from app.rag.vector_store import VectorIndex


def main() -> None:
    chunks = load_chunks()
    write_chunks_jsonl(chunks, settings.chunks_path)
    print(f"切分完成：{len(chunks)} 个条款")

    index = VectorIndex.build(chunks)
    path = index.save(settings.index_path)
    print(f"向量索引已保存：{path}（{index.matrix.shape[0]} 条 × {index.matrix.shape[1]} 维）")


if __name__ == "__main__":
    main()
