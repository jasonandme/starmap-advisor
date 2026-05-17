"""
星图智顾 - API 路由：股票相关（辅助基金持仓分析）
"""
from fastapi import APIRouter, Query, HTTPException
from app.data.akshare_news import get_stock_news as get_stock_news_data
from app.data.akshare_stock import get_stock_quote as get_stock_quote_data
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/stocks", tags=["股票"])


@router.get("/{code}/quote", summary="股票实时行情")
async def get_stock_quote(code: str):
    """获取单只股票的实时行情"""
    try:
        return await get_stock_quote_data(code)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"股票行情获取失败 [{code}]: {e}")
        raise HTTPException(status_code=500, detail=f"数据获取失败: {str(e)}")


@router.get("/{code}/news", summary="个股新闻")
async def get_stock_news(code: str):
    """获取个股相关新闻"""
    try:
        return await get_stock_news_data(code)
    except Exception as e:
        logger.error(f"个股新闻获取失败 [{code}]: {e}")
        raise HTTPException(status_code=500, detail=f"数据获取失败: {str(e)}")
