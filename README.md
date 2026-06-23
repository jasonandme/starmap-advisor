# 星图智顾

星图智顾是一个面向个人投研场景的开源 AI 工作台，聚焦基金筛选、持仓分析、板块观察和自然语言问答。项目使用 AKShare 接入公开市场数据，通过 FastAPI 提供分析接口，并用 Next.js 构建可交互的前端界面。

项目目标不是替代投资判断，而是把分散的数据检索、基金比较、组合约束和风险提示整理成一个可复核的研究流程。

## 功能概览

- 基金搜索、排名、详情、持仓穿透与净值走势查看
- 多基金对比，包括收益、费率、技术指标和持仓差异
- 组合管理，支持持仓/自选、风险偏好、仓位约束和调仓建议
- 板块观察，展示行业表现、资金流向、风险分数和相关新闻
- AI 问答，支持通过 Agent 调用数据技能并生成结构化分析
- 本地缓存与降级数据，降低外部数据源波动对开发体验的影响

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | Next.js, React, TypeScript, Tailwind CSS, Recharts |
| 后端 | FastAPI, Python, SQLAlchemy, Pydantic |
| 数据 | AKShare, SQLite, Redis |
| AI | LangChain, LangGraph, OpenAI-compatible LLM API |
| 部署 | Docker Compose |

## 项目结构

```text
.
├── backend/                 # FastAPI 服务
│   ├── app/
│   │   ├── agent/           # LLM 与 Agent 编排
│   │   ├── api/             # REST API 路由
│   │   ├── data/            # AKShare 数据接入与缓存
│   │   ├── models/          # SQLAlchemy 模型
│   │   ├── rag/             # 轻量知识检索
│   │   ├── schemas/         # Pydantic Schema
│   │   └── skills/          # Agent 可调用技能
│   └── requirements.txt
├── frontend/                # Next.js 前端
│   └── src/
│       ├── app/             # 页面路由
│       ├── components/      # UI 组件
│       └── lib/             # API 客户端与工具函数
├── docs/                    # 架构、路线图与风险说明
├── scripts/                 # 本地开发脚本
└── docker-compose.yml
```

## 快速开始

### 1. 准备环境变量

```bash
cp .env.example .env
```

至少配置一个兼容 OpenAI SDK 的大模型服务，例如 DeepSeek、通义千问或 Kimi。没有配置 LLM 时，部分数据查询页面仍可运行，但 AI 对话能力会受限。

### 2. 启动后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

后端文档地址：`http://127.0.0.1:8000/docs`

### 3. 启动前端

```powershell
cd frontend
npm install
npm run dev
```

前端地址：`http://localhost:3000`

### 4. Windows 一键开发脚本

项目提供了一个便捷脚本，可同时启动前后端：

```powershell
.\scripts\dev.ps1
```

如果本机没有全局 npm，可使用项目内的 npm 包装脚本：

```powershell
.\scripts\npm-local.ps1 --prefix frontend install
.\scripts\npm-local.ps1 --prefix frontend run build
```

## Docker Compose

```bash
docker compose up --build
```

默认服务：

- 前端：`http://localhost:3000`
- 后端：`http://localhost:8000`
- API 文档：`http://localhost:8000/docs`
- Redis：`localhost:6379`

## 常用 API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/health` | 健康检查 |
| `GET` | `/api/system/self-check` | 配置、数据库、数据源与 LLM 自检 |
| `GET` | `/api/funds/search?q=...` | 基金搜索 |
| `GET` | `/api/funds/rank?fund_type=QDII` | 基金排名 |
| `GET` | `/api/funds/{code}` | 基金详情 |
| `GET` | `/api/funds/{code}/holdings` | 基金持仓 |
| `POST` | `/api/funds/compare` | 多基金对比 |
| `GET` | `/api/sectors/overview` | 板块概览 |
| `GET` | `/api/portfolio/overview` | 组合概览 |
| `POST` | `/api/chat/stream` | AI 流式问答 |

## 开源定位

这个仓库更适合作为一个可学习、可扩展的投研产品原型：

- 展示从数据接入、缓存、API、Agent 到前端交互的完整链路
- 保留清晰的风险边界，所有分析均为研究辅助，不构成投资建议
- 优先使用公开数据源和本地可运行组件，便于复现和二次开发
- 通过模块化技能系统支持后续扩展更多数据源、指标和分析任务

## 风险声明

本项目仅用于技术研究、学习和信息整理。市场数据可能延迟、缺失或受第三方接口变化影响；AI 输出可能存在错误、遗漏或过度概括。任何基金、股票、仓位或调仓相关内容都不构成投资建议，也不应作为交易依据。

更完整的说明见 [docs/DISCLAIMER.md](docs/DISCLAIMER.md)。

## 文档

- [架构说明](docs/ARCHITECTURE.md)
- [更新日志](CHANGELOG.md)
- [路线图](docs/ROADMAP.md)
- [风险与合规边界](docs/DISCLAIMER.md)
- [贡献指南](CONTRIBUTING.md)

## License

本项目采用 [MIT License](LICENSE) 开源。
