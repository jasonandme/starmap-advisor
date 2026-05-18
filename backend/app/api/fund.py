"""
星图智顾 - API 路由：基金相关
"""
from fastapi import APIRouter, Query, HTTPException
from app.schemas.fund import FundCompareRequest
from app.data.akshare_fund import (
    compare_funds as compare_funds_data,
    get_fund_detail as get_fund_detail_data,
    get_fund_holdings as get_fund_holdings_data,
    get_fund_nav as get_fund_nav_data,
    get_fund_rank as get_fund_rank_data,
    recommend_funds as recommend_funds_data,
    search_funds as search_funds_data,
)
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/funds", tags=["基金"])


@router.get("/search", summary="基金模糊搜索")
async def search_funds_route(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    refresh: bool = Query(default=False, description="绕过本地缓存强制刷新"),
):
    """根据代码或名称搜索基金"""
    try:
        return await search_funds_data(q, force_refresh=refresh)
    except Exception as e:
        logger.error(f"基金搜索失败: {e}")
        raise HTTPException(status_code=500, detail=f"数据获取失败: {str(e)}")


@router.get("/rank", summary="基金排名")
async def get_fund_rank(
    fund_type: str = Query(default="全部", description="基金类型"),
    top_n: int = Query(default=20, ge=1, le=100, description="返回数量"),
    refresh: bool = Query(default=False, description="绕过本地缓存强制刷新"),
):
    """获取指定类型的基金排名"""
    try:
        return await get_fund_rank_data(fund_type=fund_type, top_n=top_n, force_refresh=refresh)
    except Exception as e:
        logger.error(f"基金排名获取失败: {e}")
        raise HTTPException(status_code=500, detail=f"数据获取失败: {str(e)}")


@router.get("/recommend", summary="基金推荐候选")
async def get_fund_recommendations(
    fund_type: str = Query(default="QDII", description="基金类型"),
    risk: str = Query(default="balanced", description="风险偏好：conservative/balanced/aggressive"),
    top_n: int = Query(default=5, ge=1, le=20, description="返回数量"),
    refresh: bool = Query(default=False, description="绕过本地缓存强制刷新"),
):
    """基于结构化数据生成基金候选池。"""
    try:
        return await recommend_funds_data(fund_type=fund_type, risk_preference=risk, top_n=top_n, force_refresh=refresh)
    except Exception as e:
        logger.error(f"基金推荐失败: {e}")
        raise HTTPException(status_code=500, detail=f"推荐失败: {str(e)}")


@router.get("/macro/indicators", summary="宏观经济指标")
async def get_macro_snapshot(refresh: bool = Query(default=False, description="绕过本地缓存强制刷新")):
    """获取 CPI/PMI/M2 等宏观指标快照"""
    from app.data.akshare_extra import get_macro_indicators
    try:
        return await get_macro_indicators(force_refresh=refresh)
    except Exception as e:
        logger.error(f"宏观指标获取失败: {e}")
        raise HTTPException(status_code=500, detail=f"数据获取失败: {str(e)}")


@router.get("/{code}", summary="基金详情")
async def get_fund_detail_route(code: str, refresh: bool = Query(default=False, description="绕过本地缓存强制刷新")):
    """获取单只基金的详细信息"""
    try:
        return await get_fund_detail_data(code, force_refresh=refresh)
    except Exception as e:
        logger.error(f"基金详情获取失败 [{code}]: {e}")
        raise HTTPException(status_code=500, detail=f"数据获取失败: {str(e)}")


@router.get("/{code}/nav", summary="基金净值走势")
async def get_fund_nav_history(
    code: str,
    limit: int = Query(default=180, ge=20, le=1000, description="净值点数量"),
    refresh: bool = Query(default=False, description="绕过本地缓存强制刷新"),
):
    """获取基金净值走势。"""
    try:
        return await get_fund_nav_data(code, limit=limit, force_refresh=refresh)
    except Exception as e:
        logger.error(f"基金净值获取失败 [{code}]: {e}")
        raise HTTPException(status_code=500, detail=f"数据获取失败: {str(e)}")


@router.get("/{code}/holdings", summary="基金持仓")
async def get_fund_holdings_route(code: str, year: str | None = Query(default=None)):
    """获取基金持仓明细"""
    try:
        return await get_fund_holdings_data(code, year=year)
    except Exception as e:
        logger.error(f"基金持仓获取失败 [{code}]: {e}")
        raise HTTPException(status_code=500, detail=f"数据获取失败: {str(e)}")


@router.post("/compare", summary="基金对比")
async def compare_funds(req: FundCompareRequest, refresh: bool = Query(default=False, description="绕过本地缓存强制刷新")):
    """对比多只基金的核心指标"""
    return await compare_funds_data(req.codes, force_refresh=refresh)


@router.get("/{code}/dividend", summary="基金分红历史")
async def get_fund_dividend_route(code: str):
    """获取基金分红历史记录"""
    from app.data.akshare_extra import get_fund_dividend
    try:
        return await get_fund_dividend(code)
    except Exception as e:
        logger.error(f"基金分红获取失败 [{code}]: {e}")
        raise HTTPException(status_code=500, detail=f"数据获取失败: {str(e)}")
