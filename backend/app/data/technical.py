"""
星图智顾 - 技术指标分析模块

基于 pandas_ta 对基金净值序列计算技术指标，输出结构化信号。
用于增强 fund_detail Skill 和 Agent 的短线分析能力。
"""
from __future__ import annotations

import math
from typing import Any

import pandas as pd

try:
    import pandas_ta as ta
    HAS_PANDAS_TA = True
except ImportError:
    HAS_PANDAS_TA = False


def compute_technical_indicators(nav_history: list[dict[str, Any]]) -> dict[str, Any]:
    """
    对基金净值序列计算常用技术指标。

    输入: nav_history = [{"date": "2025-01-01", "nav": 1.234, "daily_return": 0.5}, ...]
    输出: 技术指标字典，包含最新值和信号判断
    """
    if not HAS_PANDAS_TA or len(nav_history) < 20:
        return {"available": False, "reason": "数据不足或 pandas_ta 未安装"}

    df = pd.DataFrame(nav_history)
    df = df[df["nav"].notna()].copy()
    if len(df) < 20:
        return {"available": False, "reason": "有效净值数据不足 20 条"}

    # 用净值作为 close 列
    df["close"] = df["nav"].astype(float)
    df = df.sort_values("date").reset_index(drop=True)

    result: dict[str, Any] = {"available": True}

    # --- RSI (14日) ---
    try:
        rsi = ta.rsi(df["close"], length=14)
        if rsi is not None and not rsi.empty:
            latest_rsi = _safe_float(rsi.iloc[-1])
            result["rsi_14"] = latest_rsi
            result["rsi_signal"] = _rsi_signal(latest_rsi)
    except Exception:
        pass

    # --- MACD (12, 26, 9) ---
    try:
        macd = ta.macd(df["close"], fast=12, slow=26, signal=9)
        if macd is not None and not macd.empty:
            cols = macd.columns.tolist()
            macd_line = _safe_float(macd[cols[0]].iloc[-1]) if len(cols) > 0 else None
            signal_line = _safe_float(macd[cols[2]].iloc[-1]) if len(cols) > 2 else None
            histogram = _safe_float(macd[cols[1]].iloc[-1]) if len(cols) > 1 else None
            result["macd"] = {
                "macd_line": macd_line,
                "signal_line": signal_line,
                "histogram": histogram,
            }
            result["macd_signal"] = _macd_signal(macd_line, signal_line, histogram)
    except Exception:
        pass

    # --- 均线 (MA5, MA10, MA20, MA60) ---
    try:
        for period in [5, 10, 20, 60]:
            if len(df) >= period:
                sma = ta.sma(df["close"], length=period)
                if sma is not None and not sma.empty:
                    result[f"ma_{period}"] = _safe_float(sma.iloc[-1])

        latest_price = float(df["close"].iloc[-1])
        ma_signals = []
        for period in [5, 10, 20, 60]:
            ma_key = f"ma_{period}"
            if ma_key in result and result[ma_key] is not None:
                if latest_price > result[ma_key]:
                    ma_signals.append(f"价格在 MA{period} 上方")
                else:
                    ma_signals.append(f"价格在 MA{period} 下方")
        result["ma_position"] = ma_signals
    except Exception:
        pass

    # --- 布林带 (20, 2) ---
    try:
        bbands = ta.bbands(df["close"], length=20, std=2)
        if bbands is not None and not bbands.empty:
            cols = bbands.columns.tolist()
            result["bollinger"] = {
                "lower": _safe_float(bbands[cols[0]].iloc[-1]),
                "mid": _safe_float(bbands[cols[1]].iloc[-1]),
                "upper": _safe_float(bbands[cols[2]].iloc[-1]),
            }
            latest_price = float(df["close"].iloc[-1])
            upper = result["bollinger"]["upper"]
            lower = result["bollinger"]["lower"]
            if upper and lower:
                if latest_price >= upper * 0.98:
                    result["bollinger_signal"] = "接近上轨，短期可能超买"
                elif latest_price <= lower * 1.02:
                    result["bollinger_signal"] = "接近下轨，短期可能超卖"
                else:
                    result["bollinger_signal"] = "在布林带中轨附近"
    except Exception:
        pass

    # --- 综合短线信号 ---
    result["summary"] = _build_summary(result)

    return result


def _safe_float(value: Any) -> float | None:
    """安全转换为 float"""
    if value is None:
        return None
    try:
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, 4)
    except (TypeError, ValueError):
        return None


def _rsi_signal(rsi: float | None) -> str:
    if rsi is None:
        return "数据不足"
    if rsi >= 70:
        return "超买区域（RSI≥70），短期回调风险增加"
    if rsi >= 60:
        return "偏强（RSI 60-70），动量向上但需关注是否过热"
    if rsi <= 30:
        return "超卖区域（RSI≤30），短期反弹概率增加"
    if rsi <= 40:
        return "偏弱（RSI 30-40），动量向下但可能接近支撑"
    return "中性（RSI 40-60），无明显超买超卖"


def _macd_signal(macd_line: float | None, signal_line: float | None, histogram: float | None) -> str:
    if macd_line is None or signal_line is None:
        return "数据不足"
    if macd_line > signal_line and histogram and histogram > 0:
        return "MACD 金叉且柱状放大，短线偏多"
    if macd_line > signal_line:
        return "MACD 在信号线上方，趋势偏多"
    if macd_line < signal_line and histogram and histogram < 0:
        return "MACD 死叉且柱状放大，短线偏空"
    if macd_line < signal_line:
        return "MACD 在信号线下方，趋势偏空"
    return "MACD 与信号线持平，趋势不明"


def _build_summary(indicators: dict[str, Any]) -> str:
    signals = []

    rsi_sig = indicators.get("rsi_signal", "")
    if "超买" in rsi_sig:
        signals.append("RSI 超买")
    elif "超卖" in rsi_sig:
        signals.append("RSI 超卖")

    macd_sig = indicators.get("macd_signal", "")
    if "偏多" in macd_sig:
        signals.append("MACD 偏多")
    elif "偏空" in macd_sig:
        signals.append("MACD 偏空")

    bb_sig = indicators.get("bollinger_signal", "")
    if "超买" in bb_sig:
        signals.append("布林上轨承压")
    elif "超卖" in bb_sig:
        signals.append("布林下轨支撑")

    if not signals:
        return "技术面暂无显著信号，建议结合基本面和持仓分析。"

    bullish = sum(1 for s in signals if any(w in s for w in ["偏多", "超卖", "支撑"]))
    bearish = sum(1 for s in signals if any(w in s for w in ["偏空", "超买", "承压"]))

    detail = "；".join(signals)
    if bullish > bearish:
        return f"短线技术面偏多：{detail}。但技术指标存在滞后性，不建议单独作为买入依据。"
    if bearish > bullish:
        return f"短线技术面偏空：{detail}。建议观望或分批操作，避免追高。"
    return f"短线技术面多空交织：{detail}。建议等待方向明确再操作。"
