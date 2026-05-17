"""
星图智顾 - API 路由汇总
"""
from app.api.fund import router as fund_router
from app.api.stock import router as stock_router
from app.api.chat import router as chat_router
from app.api.watchlist import router as watchlist_router
from app.api.analysis import router as analysis_router
from app.api.system import router as system_router
from app.api.portfolio import router as portfolio_router
from app.api.knowledge import router as knowledge_router
from app.api.sector import router as sector_router

all_routers = [
    fund_router,
    stock_router,
    chat_router,
    watchlist_router,
    analysis_router,
    system_router,
    portfolio_router,
    knowledge_router,
    sector_router,
]
