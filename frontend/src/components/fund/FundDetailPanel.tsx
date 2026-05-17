"use client";

import { useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import { FundDetail, formatPct } from "@/lib/api";

const ranges = [
  { label: "近1月", days: 30 },
  { label: "近3月", days: 90 },
  { label: "近6月", days: 180 },
  { label: "近1年", days: 365 },
  { label: "全部", days: 0 }
];

export function FundDetailPanel({ fund }: { fund: FundDetail | null }) {
  const [range, setRange] = useState(ranges[2]);

  const filteredHistory = useMemo(() => {
    const history = fund?.nav_history || [];
    if (!range.days || history.length === 0) return history;
    const last = new Date(history[history.length - 1].date).getTime();
    if (Number.isNaN(last)) return history.slice(-range.days);
    const start = last - range.days * 24 * 60 * 60 * 1000;
    const filtered = history.filter((item) => new Date(item.date).getTime() >= start);
    return filtered.length ? filtered : history.slice(-Math.min(range.days, history.length));
  }, [fund, range]);

  if (!fund) {
    return (
      <div className="flex items-center justify-center rounded-card border border-line bg-card p-8 text-sm text-ink-muted shadow-card">
        <div className="text-center">
          <div className="text-3xl mb-3 opacity-30">📊</div>
          选择一只基金后显示净值走势、技术面和短长线分析。
        </div>
      </div>
    );
  }

  const metrics = fund.metrics || {};
  const technical = fund.technical || {};
  const shortLine = buildShortLine(metrics, technical);
  const longLine = buildLongLine(metrics, fund.fund_type);

  return (
    <section className="animate-fade-in rounded-card border border-line bg-card p-5 shadow-card">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-ink">{fund.name}</h2>
          <div className="mt-1 text-sm text-ink-muted">
            <span className="font-mono">{fund.code}</span>
            <span className="mx-2 text-line">·</span>
            {fund.fund_type || "类型暂无"}
            <span className="mx-2 text-line">·</span>
            {fund.source === "akshare" ? "AKShare" : fund.source || "暂无"}
          </div>
        </div>
        <div className="text-right">
          <div className="text-xs text-ink-muted">最新净值</div>
          <div className="text-2xl font-semibold tabular-nums text-[var(--accent)]">{fund.latest_nav ?? "暂无"}</div>
        </div>
      </div>

      {fund.warning ? (
        <div className="mt-4 rounded-lg border border-amberline/30 bg-amberline/8 px-3 py-2 text-sm text-amberline">
          {fund.warning}
        </div>
      ) : null}

      <div className="mt-5 grid grid-cols-4 gap-3">
        <Metric label="近1月" value={formatPct(metrics.month_return as number)} pct={metrics.month_return as number} />
        <Metric label="近3月" value={formatPct(metrics.three_month_return as number)} pct={metrics.three_month_return as number} />
        <Metric label="最大回撤" value={formatPct(metrics.max_drawdown as number)} />
        <Metric label="年化波动" value={formatPct(metrics.volatility as number)} />
      </div>

      <div className="mt-5 flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-ink">净值走势</h3>
        <div className="flex gap-1">
          {ranges.map((item) => (
            <button
              key={item.label}
              className={`focus-ring h-7 rounded-md border px-2 text-xs transition-all ${
                range.label === item.label
                  ? "border-line-strong bg-accent-soft text-[var(--accent)]"
                  : "border-line bg-surface-2 text-ink-muted hover:text-ink"
              }`}
              onClick={() => setRange(item)}
              type="button"
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-3 h-[280px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={filteredHistory}>
            <defs>
              <linearGradient id="navFill" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor="var(--chart-1)" stopOpacity={0.22} />
                <stop offset="100%" stopColor="var(--chart-1)" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="var(--chart-grid)" strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={{ fontSize: 11, fill: "var(--text-muted)" }} minTickGap={28} />
            <YAxis tick={{ fontSize: 11, fill: "var(--text-muted)" }} domain={["dataMin", "dataMax"]} />
            <Tooltip
              contentStyle={{
                background: "var(--chart-tooltip-bg)",
                border: "1px solid var(--chart-tooltip-border)",
                borderRadius: "var(--radius-button)",
                backdropFilter: "var(--card-blur)",
                color: "var(--text-primary)"
              }}
            />
            <Area type="monotone" dataKey="nav" stroke="var(--chart-1)" fill="url(#navFill)" strokeWidth={2} />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {technical.available ? (
        <div className="mt-5 animate-fade-in-delay">
          <div className="mb-2 text-xs font-medium text-ink-muted">技术指标</div>
          <div className="grid grid-cols-3 gap-3">
            <TechIndicator
              label="RSI(14)"
              value={technical.rsi_14 != null ? Number(technical.rsi_14).toFixed(1) : "暂无"}
              signal={technical.rsi_signal}
              color={rsiColor(technical.rsi_14)}
            />
            <TechIndicator
              label="MACD"
              value={technical.macd_signal || "暂无"}
              color={macdColor(technical.macd_signal)}
            />
            <TechIndicator
              label="布林带"
              value={technical.bollinger_signal || "暂无"}
              color={bbColor(technical.bollinger_signal)}
            />
          </div>
          {technical.summary ? (
            <div className="mt-3 rounded-lg border border-line bg-surface-2 px-3 py-2 text-xs text-[var(--accent)]">
              {technical.summary}
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="mt-5 grid grid-cols-2 gap-3 animate-fade-in-delay-2">
        <AnalysisBlock title="短线分析" text={shortLine} />
        <AnalysisBlock title="长线分析" text={longLine} />
      </div>
    </section>
  );
}

function Metric({ label, value, pct }: { label: string; value: string; pct?: number | null }) {
  return (
    <div className="rounded-lg border border-line bg-surface-2/60 p-3">
      <div className="text-xs text-ink-muted">{label}</div>
      <div className={`mt-1 text-base font-semibold tabular-nums ${
        pct !== undefined && pct !== null
          ? pct > 0 ? "price-up" : pct < 0 ? "price-down" : "text-ink"
          : "text-ink"
      }`}>
        {value}
      </div>
    </div>
  );
}

function TechIndicator({ label, value, signal, color }: { label: string; value: string; signal?: string; color: string }) {
  return (
    <div className={`rounded-lg border p-3 ${color}`}>
      <div className="text-xs text-ink-muted">{label}</div>
      <div className="mt-1 text-sm font-semibold text-ink">{value}</div>
      {signal ? <div className="mt-1 text-[11px] text-ink-secondary line-clamp-2">{signal}</div> : null}
    </div>
  );
}

function rsiColor(rsi: number | null | undefined) {
  if (rsi == null) return "border-line bg-surface-2/60";
  if (rsi >= 70) return "border-up/30 bg-up/8";
  if (rsi <= 30) return "border-line bg-accent-soft";
  return "border-amberline/30 bg-amberline/8";
}

function macdColor(signal: string | undefined) {
  if (!signal) return "border-line bg-surface-2/60";
  if (signal.includes("偏多") || signal.includes("金叉")) return "border-up/30 bg-up/8";
  if (signal.includes("偏空") || signal.includes("死叉")) return "border-line bg-accent-soft";
  return "border-amberline/30 bg-amberline/8";
}

function bbColor(signal: string | undefined) {
  if (!signal) return "border-line bg-surface-2/60";
  if (signal.includes("超买")) return "border-up/30 bg-up/8";
  if (signal.includes("超卖")) return "border-line bg-accent-soft";
  return "border-line bg-surface-2/60";
}

function AnalysisBlock({ title, text }: { title: string; text: string }) {
  return (
    <div className="rounded-lg border border-line bg-surface-2/40 p-3">
      <div className="text-xs font-medium text-ink-muted">{title}</div>
      <div className="mt-2 text-sm leading-6 text-ink-secondary">{text}</div>
    </div>
  );
}

function numberValue(value: unknown) {
  const next = Number(value);
  return Number.isFinite(next) ? next : null;
}

function buildShortLine(metrics: Record<string, number | null>, technical: Record<string, any>) {
  const month = numberValue(metrics.month_return);
  const rsi = numberValue(technical.rsi_14);
  const macd = String(technical.macd_signal || "");
  if (rsi !== null && rsi >= 70) return "短线偏热，优先观察回落和成交确认，不适合一次性追高加仓。";
  if (rsi !== null && rsi <= 30) return "短线进入偏冷区域，可以关注止跌信号，但仍需结合板块资金和大盘环境。";
  if (macd.includes("金叉")) return "短线动能有修复迹象，可以小仓位跟踪，不宜脱离单只基金仓位上限。";
  if (macd.includes("死叉")) return "短线动能转弱，适合先观察或降低加仓节奏。";
  if (month !== null && month > 6) return "近1月涨幅较快，短线更适合分批而不是追高。";
  if (month !== null && month < -6) return "近1月回撤较多，短线先看是否企稳，再考虑定投或小额补仓。";
  return "短线信号中性，建议结合板块风向和当日资金流决定是否操作。";
}

function buildLongLine(metrics: Record<string, number | null>, fundType?: string) {
  const threeMonth = numberValue(metrics.three_month_return);
  const drawdown = numberValue(metrics.max_drawdown);
  const volatility = numberValue(metrics.volatility);
  if (drawdown !== null && drawdown < -18) return "长期持有需要确认最大回撤是否在你的承受范围内，仓位不宜过重。";
  if (volatility !== null && volatility > 28) return "长期波动偏高，更适合作为卫星仓或主题仓，不能替代稳健底仓。";
  if (threeMonth !== null && threeMonth > 10) return "中期趋势较强，长线要重点复核估值、持仓集中度和主题拥挤度。";
  if ((fundType || "").includes("债")) return "长期定位偏防守，适合承担组合稳定器角色，但仍要关注利率和信用风险。";
  return "长线需要回到基金经理或指数逻辑、行业景气度、费率和组合相关性，确认它在组合中是核心仓还是卫星仓。";
}

