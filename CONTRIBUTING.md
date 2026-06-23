# Contributing

感谢你关注星图智顾。这个项目仍处于早期阶段，欢迎围绕数据接入、分析指标、前端体验、文档和测试提出改进。

## 本地开发

1. Fork 并克隆仓库。
2. 复制 `.env.example` 为 `.env`，按需配置 LLM API Key。
3. 启动后端：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

4. 启动前端：

```powershell
cd frontend
npm install
npm run dev
```

## 贡献方向

- 修复数据源变动导致的字段兼容问题
- 补充基金、股票、板块分析指标
- 改进组合风险提示和可解释性
- 增加测试、类型检查和端到端校验
- 完善部署、截图和使用文档

## 提交建议

- 保持改动聚焦，避免把格式化、重构和功能变更混在一个 PR 中。
- 涉及投资分析输出时，请同时检查风险提示是否清晰。
- 不要提交真实 API Key、数据库、日志、缓存或个人持仓截图。

## Issue 建议

提交问题时，请尽量包含：

- 复现步骤
- 期望行为和实际行为
- 前后端日志中的关键错误信息
- 操作系统、Python、Node.js 版本
- 是否配置了 LLM 与 Redis
