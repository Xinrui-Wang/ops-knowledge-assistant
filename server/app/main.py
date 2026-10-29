"""FastAPI 入口：SSE 问答接口 + 静态前端托管。

开发：
    uvicorn app.main:app --host 0.0.0.0 --port 8000
前端：
    cd web && npm run dev      # 5173，/api 代理到 8000
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.chat.orchestrator import run

app = FastAPI(title="企业运营知识助手")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    question: str


def to_sse(event: dict) -> str:
    payload = json.dumps(event, ensure_ascii=False)
    return f"event: {event['type']}\ndata: {payload}\n\n"


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.post("/api/chat/stream")
def chat_stream(request: ChatRequest) -> StreamingResponse:
    def generate():
        for event in run(request.question):
            yield to_sse(event)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # 关掉 nginx 等反向代理的缓冲，否则流式会被攒成一坨
            "X-Accel-Buffering": "no",
        },
    )


# 构建产物存在时直接托管（单进程部署方式）
dist = Path(__file__).resolve().parents[2] / "web" / "dist"
if dist.exists():
    app.mount("/", StaticFiles(directory=dist, html=True), name="web")
