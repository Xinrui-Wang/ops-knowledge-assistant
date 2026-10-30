# 企业运营知识助手

统一对话入口：用户提问，系统**自动判断**该查制度文档（RAG）、查运营数据库（Text2SQL），还是两者都查（HYBRID）。
回答带可核验的出处——文档题引用到「文档标题 + 条款编号」，数据题给出实际执行的 SQL 与查询结果。

当文档规定与实际数据不一致时，系统**同时呈现两者并标注冲突**，不做静默取舍。

---

## 快速开始

**环境要求**

- Python 3.11+
- Node.js 18+（只有构建前端时用）
- 一个 OpenAI 兼容的 LLM + Embedding 服务（开发用硅基流动）

**三步启动**

```bash
git clone git@github.com:Xinrui-Wang/ops-knowledge-assistant.git
cd ops-knowledge-assistant
cp .env.example .env      # 填入 OKA_LLM_API_KEY / OKA_EMBED_API_KEY
./run.sh
```

脚本会检查环境、建虚拟环境、装依赖、构建前端，然后启动服务。打开 http://localhost:8000 。

> 样例数据库（`data/ops.db`）与向量索引（`data/index.npz`）**已随仓库提交**，
> clone 下来无需生成，也不会额外消耗 embedding 额度。只有改动文档后才需要重建索引。

**手动启动（不想用脚本时）**

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r server/requirements.txt
cd web && npm install && npm run build && cd ..
cd server && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**重建数据与索引**（修改了 `data/docs/` 或 `data/seed.py` 之后）

```bash
python3 data/seed.py          # 重新生成 ops.db（确定性，结果不变）
cd server && python -m app.rag.index   # 重新向量化 47 条条款（会调用 embedding API）
```

**关于 key**：`.env` 不入库，必须自带。任意 OpenAI 兼容服务均可，改 `OKA_LLM_BASE_URL` /
`OKA_EMBED_MODEL` 等即可。若更换 embedding 模型或维度，请重跑索引——服务启动时会校验维度并给出提示。

---

## 架构

```
                     用户问题
                        │
                        ▼
              ┌───────────────────┐
              │  Router（LLM）     │  rag / sql / hybrid
              └─────────┬─────────┘
          ┌─────────────┴──────────────┐
          ▼                            ▼
 ┌────────────────────┐      ┌─────────────────────────────┐
 │ RAG                │      │ Text2SQL                    │
 │                    │      │                             │
 │ BM25（jieba 分词）  │      │ ① Schema Linking            │
 │ 向量（Qwen3-Emb）   │      │   向量粗筛 Top3 → LLM 精挑   │
 │      ↓ RRF 融合     │      │ ② 指标口径匹配 metrics.json  │
 │   top-5 条款        │      │ ③ 值链接（DISTINCT 枚举值）  │
 │      ↓             │      │ ④ 生成 SQL + 护栏校验        │
 │ 引用式回答 [1][2]   │      │ ⑤ 只读执行（mode=ro, LIMIT） │
 └─────────┬──────────┘      │ ⑥ 自然语言摘要 + 样本量提示   │
           │                 └──────────────┬──────────────┘
           └───────────┬────────────────────┘
                       ▼
             ┌───────────────────┐
             │ Reconciler 对账    │ consistent / violation
             │                   │ conflict / insufficient
             └─────────┬─────────┘
                       ▼
        回答（代码模板拼装，冲突时两边都呈现）
```

### 一次请求的事件流

后端以事件流形式产出，前端逐条消费（也是 SSE 接口的内容）：

```
event: route            {"route":"hybrid","reason":"..."}
event: retrieved        {"sources":[{"citation":"《售后服务响应管理办法》第四条",...}]}
event: schema_linking   {"detail":{"tables":["fact_ticket","dim_region"],"reason":"..."}}
event: metrics          {"items":["响应达标率"]}
event: sql_generated    {"sql":"SELECT ..."}
event: sql_executed     {"columns":[...],"rows":[...]}
event: reconciliation   {"detail":{"status":"violation","policy":"...","data":"..."}}
event: answer_delta     {"delta":"⚠️ 实际数据未达到制度要求..."}
event: citations        {"items":[...]}
event: done
```

SQL 执行之前，用户已经能看到选了什么表、写了什么 SQL——这是"流式"区别于"打字机效果"的地方。

---

## 目录结构

```
server/
  app/
    main.py              FastAPI 入口 + SSE 接口 + 静态托管
    config.py            环境变量配置（OKA_ 前缀）
    llm.py               OpenAI 兼容 Chat 客户端（默认关闭思维链）
    chat/
      router.py          意图路由
      orchestrator.py    编排：事件流
      answerer.py        RAG 引用式回答 / SQL 摘要
      reconciler.py      制度与数据对账 + 回答模板
      cli.py             命令行版问答
    rag/
      chunker.py         条款级切分（47 条，带出处元数据）
      bm25.py            稀疏检索
      embeddings.py      向量化（查询加指令前缀）
      vector_store.py    numpy 向量检索
      hybrid.py          RRF 融合
      index.py / search.py  建索引 / 检索调试 CLI
    sql/
      schema_linking.py  粗筛 + 精挑 + 值链接
      text2sql.py        生成 SQL
      guardrails.py      只读 / 单条 / 仅 SELECT / 强制 LIMIT
      db.py              只读连接 + 超时
      metrics.py         指标口径匹配
      cli.py             命令行版 Text2SQL
  tests/                 21 个单元测试
web/                     Vite + React + TS 前端
data/
  docs/                  5 份制度文档（47 条）
  seed.py                生成 ops.db + schema.json
  metrics.json           指标口径表
  README.md              数据说明与埋点
eval/
  cases.json             自测用例
  run_eval.py            自测脚本
DECISIONS.md             关键决策与作业三问
```

---

## 路由策略与失败模式

路由由一次 LLM 调用完成，输出 `rag / sql / hybrid`，解析失败或结果非法时**降级为 hybrid**（两条都跑，宁可多查不可漏答）。

**失败模式（实测）**

1. **歧义问题路由不稳定**。同一个问题「差旅费用怎么控制比较好」两次运行分别得到 `rag` 与 `hybrid`。
   同样提示词、`temperature=0` 仍会漂移——LLM 服务端本身存在非确定性，且该问题在两可之间。
2. **术语方向判反**。早期提示词下「住宿标准是多少」被判成 `sql`（把"标准"理解成实际花费水平）。
   加入反例（住宿标准→rag；销售部住宿平均花了多少→sql；住宿有没有超标→hybrid）后不再出现，但依赖样本覆盖。
3. **内部黑话**。"客单""CSAT""动销"这类词对分类器是噪声，提示词无法穷举公司内部叫法。

**为什么不能完美解决**：意图不是数据里的客观属性，而是用户想干什么；同一句话在不同上下文含义不同。
当前系统是**无状态单轮**，没有对话历史与澄清追问，只能做一次性文本分类。

**缓解与代价**：降级 hybrid 保证不漏答，但延迟与 token 成本翻倍。要真正降低误路由率，需要多轮上下文、
置信度阈值转澄清追问，以及基于真实误路由样本的持续迭代——均超出本次范围。

---

## 演示路径

| # | 问题 | 路径 | 看点 |
| --- | --- | --- | --- |
| 1 | 一线城市出差住宿标准是多少 | RAG | 引用精确到《销售费用报销管理制度》第五条 |
| 2 | 第三季度各大区销售额排名如何 | SQL | schema linking 选表理由 + 结果摘要 |
| 3 | 华东区第三季度售后响应是否达标 | HYBRID | 制度 2 小时 vs 达标率 13.89% → **violation** |
| 4 | 销售一部一线城市住宿报销有没有超标 | HYBRID | 制度 600 元/晚 vs 实际 716.54 元/晚 → **violation** |
| 5 | 哪个大区客单价最高 | SQL | 西北区 3 单，触发「样本量过小」提示 |
| 6 | 差旅费用怎么控制比较好 | 歧义 | 路由可能落在 rag 或 hybrid，见上文失败模式 |

---

## 自测用例

```bash
python eval/run_eval.py            # 全部
python eval/run_eval.py --only conflict
```

覆盖 纯 RAG / 纯 SQL（含小样本）/ HYBRID（一致）/ 冲突 ×2 / 歧义跨域，共 8 条。
断言路由、对账状态、引用条款与关键内容，失败退出码非 0。

单元测试：

```bash
cd server && python -m pytest -q
```

---

## 做了什么 / 没做什么

**基础要求**：RAG（条款级引用）、Text2SQL（显式 schema linking、只读执行、自然语言摘要）、
统一 Chat 前端与自动路由、歧义测试问题、README 路由失败模式——均已完成。

**加分项（三选二）**：

- ✅ **流式进度事件**：路由、检索、选表、SQL、执行、对账各自成事件，前端分块渲染。
- ✅ **冲突 / 缺失 / 异常处理**：四态对账 + 小样本提示 + 未登记口径不假设。
- ❌ **Skill 配置**：主动放弃。设计输出契约 + 组件注册表 + 流式渲染 tool 参数，工作量约等于整个前端；
  在三选二的前提下，把它换成把前两项做透更划算。

---

## 已知局限

详见 `DECISIONS.md` 第三节，摘要：

1. 切分依赖文档结构标记，真实 Word/PDF 需先做结构识别；
2. 语料规模小（47 条款 / 5 表），表数量增多时粗筛需重新设计；
3. 路由无会话上下文，歧义问题只能降级兜底；
4. SQL 执行失败无自动重试；
5. 小样本阈值 `sample_count < 5` 为经验值，无统计依据；
6. 冲突判定仍由 LLM 给出，未做数值层面的硬比对。
