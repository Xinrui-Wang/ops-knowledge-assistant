"""全局配置。所有可变项走环境变量（前缀 OKA_）或项目根目录 .env。"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_prefix="OKA_",
        extra="ignore",
    )

    # 数据路径
    docs_dir: Path = DATA_DIR / "docs"
    db_path: Path = DATA_DIR / "ops.db"
    schema_path: Path = DATA_DIR / "schema.json"
    chunks_path: Path = DATA_DIR / "chunks.jsonl"

    # LLM（OpenAI 兼容协议）
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""

    # Embedding（OpenAI 兼容协议）
    embed_base_url: str = ""
    embed_api_key: str = ""
    embed_model: str = ""

    # 检索
    top_k_sparse: int = 8
    top_k_dense: int = 8
    rrf_k: int = 60


settings = Settings()
