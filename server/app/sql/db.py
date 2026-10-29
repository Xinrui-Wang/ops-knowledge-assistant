"""只读数据库访问：物理只读 + 行数上限 + 执行超时。"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from app.config import settings


def connect_readonly(path: Path | None = None) -> sqlite3.Connection:
    target = Path(path or settings.db_path)
    # mode=ro 由 SQLite 自身保证只读，比"检查 SQL 里有没有 delete"更硬
    conn = sqlite3.connect(f"file:{target.as_posix()}?mode=ro", uri=True, timeout=5.0)
    conn.row_factory = sqlite3.Row
    return conn


def execute(
    sql: str,
    path: Path | None = None,
    max_rows: int = 200,
    timeout_s: float = 5.0,
) -> tuple[list[str], list[dict]]:
    conn = connect_readonly(path)
    deadline = time.monotonic() + timeout_s

    def _guard() -> int:
        if time.monotonic() > deadline:
            raise TimeoutError(f"查询超过 {timeout_s}s")
        return 0

    conn.set_progress_handler(_guard, 10_000)
    try:
        cur = conn.execute(sql)
        columns = [d[0] for d in cur.description] if cur.description else []
        rows = [dict(row) for row in cur.fetchmany(max_rows)]
        return columns, rows
    finally:
        conn.close()
