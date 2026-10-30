#!/usr/bin/env bash
# 一键启动：装依赖 → 检查数据 → 构建前端 → 启动服务
# 前提：已把 .env.example 复制为 .env 并填好 API key
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  echo "✗ 缺少 .env"
  echo "  cp .env.example .env  然后把 OKA_LLM_API_KEY / OKA_EMBED_API_KEY 填上"
  exit 1
fi

PYTHON=${PYTHON:-python3}
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "✗ 找不到 $PYTHON，请先安装 Python 3.11+"
  exit 1
fi

if [ ! -d .venv ]; then
  echo "→ 创建虚拟环境 .venv"
  "$PYTHON" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "→ 安装后端依赖"
pip install -q -r server/requirements.txt

if [ ! -f data/ops.db ]; then
  echo "→ 生成样例数据"
  python data/seed.py
fi

if [ ! -f data/index.npz ]; then
  echo "→ 构建向量索引（会调用 embedding API）"
  (cd server && python -m app.rag.index)
fi

if [ ! -d web/dist ]; then
  if ! command -v npm >/dev/null 2>&1; then
    echo "✗ 缺少 npm，无法构建前端。装 Node.js 18+ 后重试，"
    echo "  或手动执行：cd web && npm install && npm run build"
    exit 1
  fi
  echo "→ 构建前端"
  (cd web && npm install --silent && npm run build)
fi

echo ""
echo "✓ 启动：http://localhost:${PORT:-8000}"
cd server
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
