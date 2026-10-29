# 企业运营知识助手

统一对话入口，自动路由到 **RAG（制度/政策问答）**、**Text2SQL（运营数据查询）** 或 **HYBRID（两者结合）**，
回答带可核验的出处（文档标题 + 条款编号 / 命中的 SQL 与数据口径）。

> 状态：开发中。

## 目录结构

```
server/        后端（Python + FastAPI）
web/           前端（Vite + React + TS）
data/docs/     样本文档（切分与检索的语料）
eval/          自测用例与评测脚本
```

## 文档

- `DECISIONS.md` — 关键技术决策与取舍
- `DEMO.md` — 固定演示路径
