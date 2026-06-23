# Architecture

星图智顾采用前后端分离架构：前端负责投研工作台交互，后端负责数据接入、缓存、结构化分析和 Agent 编排。

## 模块划分

```text
Frontend (Next.js)
  ├─ Dashboard / Funds / Portfolio / Sectors / Chat
  └─ API client with lightweight browser cache

Backend (FastAPI)
  ├─ api/       HTTP route layer
  ├─ data/      AKShare adapters, normalization and cache helpers
  ├─ skills/    Agent-callable tools for fund search, ranking and comparison
  ├─ agent/     LLM provider selection and conversation orchestration
  ├─ rag/       Curated knowledge retrieval
  └─ models/    SQLite-backed persistence models
```

## 数据流

1. 前端页面通过 `frontend/src/lib/api.ts` 调用后端 API。
2. 后端路由层校验参数，并调用数据接入、组合分析或 Agent 服务。
3. 数据层优先读取缓存；缓存失效时通过 AKShare 拉取公开数据。
4. Agent 根据用户问题选择技能，组合结构化数据和风险提示生成回复。
5. 前端以表格、图表、卡片和流式对话展示结果。

## 设计原则

- 数据优先：先获取结构化数据，再让 LLM 做解释和归纳。
- 人工确认：任何“候选”“建议”“策略”都必须保留复核空间。
- 可降级：外部数据源异常时尽量返回明确 warning，而不是静默失败。
- 可扩展：新增数据源或分析任务时优先以 `data/` 和 `skills/` 模块扩展。

## 后续可改进点

- 引入统一的任务队列处理慢查询和批量刷新。
- 为关键数据适配器补充契约测试。
- 增加更细粒度的数据新鲜度和来源标注。
- 将本地 SQLite 场景扩展到 PostgreSQL 部署方案。
