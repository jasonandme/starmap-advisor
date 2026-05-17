# 星图智顾 ⭐

个人基金投研 AI 助手 — 基于 AKShare 数据 + DeepSeek/通义千问大模型

## 功能

- 🔍 **基金搜索/排名** — 支持按类型筛选（股票型、混合型、QDII 等）
- 📊 **基金对比** — 多基金净值走势、费率、持仓对比
- 💬 **AI 对话** — 自然语言提问，Agent 自动调用数据 Skill
- ⭐ **自选管理** — 收藏和跟踪感兴趣的基金
- 📈 **持仓分析** — 穿透基金持仓，分析重仓股
- 🧭 **组合配置** — 支持稳健/均衡/进取偏好、仓位上限、QDII 上限、主题基金开关和回撤阈值

## 技术栈

| 层 | 技术 |
|---|------|
| 前端 | Next.js 16 + TypeScript + Tailwind CSS |
| 后端 | FastAPI + Python 3.12 |
| 数据库 | SQLite（开发）/ PostgreSQL（部署） |
| Agent | LangGraph + LangChain |
| LLM | DeepSeek（主力）/ 通义千问（备选） |
| 数据源 | AKShare（东方财富/天天基金） |

## 快速启动

如果系统没有全局 npm，可使用项目内 npm 包装脚本：

```powershell
.\scripts\npm-local.ps1 --prefix frontend install
.\scripts\npm-local.ps1 --prefix frontend run build
```

同时启动前后端：

```powershell
.\scripts\dev.ps1
```

前端默认地址：`http://localhost:3000`
后端文档地址：`http://127.0.0.1:8000/docs`

### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入你的 DeepSeek API Key
```

### 2. 启动后端

```bash
cd backend
python -m venv venv
venv\Scripts\activate      # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

### 4. 访问

- 前端：http://localhost:3000
- 后端 API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/api/health
- 系统自查：http://localhost:8000/api/system/self-check

## 项目结构

```
星图智顾/
├── backend/          # FastAPI 后端
│   ├── app/
│   │   ├── api/      # REST API 路由
│   │   ├── models/   # ORM 模型
│   │   ├── schemas/  # Pydantic 数据模型
│   │   ├── skills/   # Skill 系统
│   │   ├── agent/    # LangGraph Agent
│   │   └── data/     # 数据接入层
│   └── requirements.txt
├── frontend/         # Next.js 前端
│   └── src/
│       ├── app/      # 页面路由
│       ├── components/  # UI 组件
│       └── lib/      # 工具函数
└── docker-compose.yml
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/system/self-check` | 系统自查：配置、数据库、Skill、AKShare、LLM |
| GET | `/api/funds/search?q=...` | 基金搜索 |
| GET | `/api/funds/rank?fund_type=QDII` | 基金排名 |
| GET | `/api/funds/{code}` | 基金详情 |
| GET | `/api/funds/{code}/holdings` | 基金持仓 |
| POST | `/api/funds/compare` | 基金对比 |
| POST | `/api/chat/stream` | AI 对话（SSE） |
| GET | `/api/watchlist` | 自选列表 |
| POST | `/api/watchlist` | 添加自选 |
| DELETE | `/api/watchlist/{code}` | 删除自选 |
| GET | `/api/portfolio/preferences` | 投资偏好配置 |
| PUT | `/api/portfolio/preferences` | 保存投资偏好 |
| GET | `/api/portfolio/items` | 组合持仓/自选条目 |
| POST | `/api/portfolio/items/seed` | 导入截图持仓和自选种子数据 |
| GET | `/api/portfolio/strategy` | 基于偏好生成组合策略 |
