"""投研知识库候选来源清单。

这里不把网页内容硬编码进项目，只维护经过筛选的官方/开源来源。
真正写入知识库时仍走 /api/knowledge/ingest-url 或上传文件，便于审计来源。
"""
from __future__ import annotations


CURATED_KNOWLEDGE_SOURCES = [
    {
        "name": "AKShare 开源财经数据接口库",
        "url": "https://github.com/akfamily/akshare",
        "category": "data_source",
        "type": "开源项目",
        "why": "项目当前已经使用 AKShare，适合写入接口能力、字段含义和数据源限制。",
    },
    {
        "name": "Qlib 开源量化投研框架",
        "url": "https://github.com/microsoft/qlib",
        "category": "quant_framework",
        "type": "开源项目",
        "why": "适合后续做离线因子、回测、模型评估和策略研究，不直接替代实时投研。",
    },
    {
        "name": "FinRL 开源强化学习量化框架",
        "url": "https://github.com/AI4Finance-Foundation/FinRL",
        "category": "quant_framework",
        "type": "开源项目",
        "why": "适合研究型策略实验，当前阶段只建议作为候选知识源和后续扩展。",
    },
    {
        "name": "上海证券交易所投资者教育",
        "url": "https://edu.sse.com.cn/",
        "category": "investor_education",
        "type": "官方投教",
        "why": "适合沉淀 A 股交易规则、风险揭示、科创板和指数基础知识。",
    },
    {
        "name": "深圳证券交易所投资者教育中心",
        "url": "https://investor.szse.cn/investor/aboutus/eductionCentre/index.html",
        "category": "investor_education",
        "type": "官方投教",
        "why": "适合补充深市规则、交易机制和投资者教育材料。",
    },
    {
        "name": "中国证券投资基金业协会投教平台",
        "url": "https://investor.amac.org.cn/",
        "category": "fund_education",
        "type": "官方投教",
        "why": "适合沉淀公募基金基础、基金销售适当性、基金风险揭示。",
    },
]
