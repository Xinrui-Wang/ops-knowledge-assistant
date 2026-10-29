"""轻量 BM25 稀疏检索（jieba 分词，纯 Python，无外部服务依赖）。"""

from __future__ import annotations

import math
import re
from collections import Counter

import jieba

from app.rag.chunker import Chunk

jieba.setLogLevel(60)

PUNCT_RE = re.compile(r"[\s，。、；：？！“”‘’（）《》【】,.!?;:\"'()\[\]{}<>|/\\_=+*#%&^~`@$—…·-]+")


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for token in jieba.cut(text):
        token = PUNCT_RE.sub("", token.strip()).lower()
        if token:
            tokens.append(token)
    return tokens


def chunk_search_text(chunk: Chunk) -> str:
    """参与检索的文本：标题、条款号、条款主题都计入，便于命中「第X条」类问法。"""
    return " ".join(
        part
        for part in (chunk.doc_title, chunk.section, chunk.clause_no, chunk.clause_title, chunk.text)
        if part
    )


class BM25Index:
    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.k1 = k1
        self.b = b

        self.docs_tokens = [tokenize(chunk_search_text(c)) for c in chunks]
        self.doc_freqs = [Counter(tokens) for tokens in self.docs_tokens]
        self.doc_lens = [len(tokens) for tokens in self.docs_tokens]
        self.avg_dl = sum(self.doc_lens) / len(self.doc_lens) if self.doc_lens else 0.0

        df: Counter[str] = Counter()
        for tokens in self.docs_tokens:
            df.update(set(tokens))
        n = len(self.docs_tokens)
        self.idf = {
            term: math.log(1 + (n - freq + 0.5) / (freq + 0.5)) for term, freq in df.items()
        }

    def _score(self, query_tokens: list[str], index: int) -> float:
        freqs = self.doc_freqs[index]
        dl = self.doc_lens[index]
        score = 0.0
        for term in query_tokens:
            tf = freqs.get(term, 0)
            if not tf:
                continue
            idf = self.idf.get(term, 0.0)
            score += idf * tf * (self.k1 + 1) / (
                tf + self.k1 * (1 - self.b + self.b * dl / self.avg_dl)
            )
        return score

    def search(self, query: str, top_k: int = 5) -> list[tuple[Chunk, float]]:
        query_tokens = tokenize(query)
        if not query_tokens:
            return []
        scored = [
            (self.chunks[i], self._score(query_tokens, i))
            for i in range(len(self.chunks))
        ]
        scored = [item for item in scored if item[1] > 0]
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:top_k]
