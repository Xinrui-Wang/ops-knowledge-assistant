"""制度文档切分器。

切分单位是「条款」，而不是固定长度：
  - `# 标题`        → 文档标题（doc_title）
  - `## 第X章 ...`  → 章节（section）
  - `**第X条（主题）**` → 条款（clause_no + clause_title）

每个 chunk 都带完整出处元数据，回答时可以精确引用到「文档标题 + 第X条」。
单条超过 MAX_CHARS 时按句子切分，并用 `#p2`、`#p3` 标注段序。
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.config import settings

CLAUSE_RE = re.compile(r"^\*\*(第[一二三四五六七八九十百零]+条)(?:[（(](.+?)[）)])?\*\*\s*$")
META_RE = re.compile(r"^\|\s*(文号|版本|生效日期|归口部门)\s*\|\s*(.+?)\s*\|\s*$")
SENTENCE_RE = re.compile(r"[^。；！？]*[。；！？]?")

MAX_CHARS = 500


@dataclass
class Chunk:
    chunk_id: str
    doc_file: str
    doc_title: str
    doc_no: str
    section: str
    clause_no: str
    clause_title: str
    text: str
    part: int = 1

    @property
    def char_len(self) -> int:
        return len(self.text)

    @property
    def citation(self) -> str:
        return f"《{self.doc_title}》{self.clause_no}" + (
            f"（{self.clause_title}）" if self.clause_title else ""
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["char_len"] = self.char_len
        return d


@dataclass
class _Clause:
    clause_no: str
    clause_title: str
    body: list[str] = field(default_factory=list)


def _split_long(text: str) -> list[str]:
    """超过 MAX_CHARS 的条款按句子切分，尽量均分。"""
    if len(text) <= MAX_CHARS:
        return [text]

    sentences = [s for s in SENTENCE_RE.findall(text) if s.strip()]
    parts: list[str] = []
    buf = ""
    for sentence in sentences:
        if buf and len(buf) + len(sentence) > MAX_CHARS:
            parts.append(buf.strip())
            buf = sentence
        else:
            buf += sentence
    if buf.strip():
        parts.append(buf.strip())
    return parts or [text]


def parse_document(path: Path) -> list[Chunk]:
    lines = path.read_text(encoding="utf-8").splitlines()

    doc_title = ""
    meta: dict[str, str] = {}
    section = ""
    chunks: list[Chunk] = []
    current: _Clause | None = None

    def flush() -> None:
        nonlocal current
        if current is None:
            return
        body = "\n".join(line for line in current.body).strip()
        header = current.clause_no + (
            f"（{current.clause_title}）" if current.clause_title else ""
        )
        text = f"{header}\n{body}".strip() if body else header

        for i, part_text in enumerate(_split_long(text), start=1):
            suffix = f"#p{i}" if i > 1 else ""
            chunks.append(
                Chunk(
                    chunk_id=f"{path.stem}#{current.clause_no}{suffix}",
                    doc_file=path.name,
                    doc_title=doc_title,
                    doc_no=meta.get("文号", ""),
                    section=section,
                    clause_no=current.clause_no,
                    clause_title=current.clause_title,
                    text=part_text,
                    part=i,
                )
            )
        current = None

    for raw in lines:
        line = raw.rstrip()

        if not doc_title and line.startswith("# "):
            doc_title = line[2:].strip()
            continue

        if line.startswith("## "):
            flush()
            section = line[3:].strip()
            continue

        if current is None:
            m = META_RE.match(line)
            if m:
                meta[m.group(1)] = m.group(2)
                continue

        m = CLAUSE_RE.match(line)
        if m:
            flush()
            current = _Clause(clause_no=m.group(1), clause_title=(m.group(2) or "").strip())
            continue

        if current is not None:
            current.body.append(raw.rstrip())

    flush()
    return chunks


def load_chunks(docs_dir: Path | None = None) -> list[Chunk]:
    docs_dir = docs_dir or settings.docs_dir
    chunks: list[Chunk] = []
    for path in sorted(docs_dir.glob("*.md")):
        chunks.extend(parse_document(path))
    return chunks


def write_chunks_jsonl(chunks: list[Chunk], out_path: Path | None = None) -> Path:
    out_path = out_path or settings.chunks_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for chunk in chunks:
            fh.write(json.dumps(chunk.to_dict(), ensure_ascii=False) + "\n")
    return out_path
