"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, ArrowRight, BarChart3, Brain, LineChart, ShieldCheck, Star, TrendingUp } from "lucide-react";
import { api, FundRecord, PortfolioStrategy, SectorOverview, SectorRecord, formatPct } from "@/lib/api";
import { FundTable } from "@/components/fund/FundTable";
import { MetricCard } from "@/components/ui/MetricCard";

type HistoryItem = { id: number; query: string; response: string; created_at: string };

export default function DashboardPage() {
  const [funds, setFunds] = useState<FundRecord[]>([]);
  const [sectors, setSectors] = useState<SectorOverview | null>(null);
  const [strategy, setStrategy] = useState<PortfolioStrategy | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [watchCount, setWatchCount] = useState(0);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const loadDashboard = useCallback(async (refresh = false) => {
    setLoading(true);
    await Promise.allSettled([
      api.recommend("全部", "balanced", 6, false),
      api.watchlist(),
      api.sectorOverview(80, refresh),
      api.portfolioStrategy(refresh),
      api.history()
    ]).then(([recommend, watchlist, sectorResult, strategyResult, historyResult]) => {
      if (recommend.status === "fulfilled") setFunds(recommend.value.funds || []);
      if (watchlist.status === "fulfilled") setWatchCount(watchlist.value.items?.length || 0);
      if (sectorResult.status === "fulfilled") setSectors(sectorResult.value);
      if (strategyResult.status === "fulfilled") setStrategy(strategyResult.value);
      if (historyResult.status === "fulfilled") setHistory((historyResult.value.items || []).slice(0, 4));
      const firstError = [recommend, watchlist, sectorResult, strategyResult, historyResult]
        .find((item) => item.status === "rejected") as PromiseRejectedResult | undefined;
      if (firstError) setMessage(firstError.reason instanceof Error ? firstError.reason.message : "部分数据加载失败");
      setLastUpdated(new Date());
    }).finally(() => {
      setLoading(false);
    });
  }, []);

  useEffect(() => {
    loadDashboard(true);
    const timer = window.setInterval(() => loadDashboard(true), 60_000);
    return () => window.clearInterval(timer);
  }, [loadDashboard]);

  async function addFund(fund: FundRecord) {
    try {
      await api.addWatch(fund.code, fund.name);
      const watchlist = await api.watchlist();
      setWatchCount(watchlist.items.length);
      setMessage(`${fund.name} 已加入自选`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "加入自选失败");
    }
  }

  const exposure = strategy?.exposure;
  const pnlValue = exposure?.estimated_daily_profit ?? exposure?.snapshot_daily_profit ?? null;
  const returnValue = exposure?.estimated_daily_return_pct ?? exposure?.snapshot_daily_return_pct ?? null;
  const usesSnapshotPnl = exposure?.estimated_daily_profit == null && exposure?.snapshot_daily_profit != null;
  const quoteFreshnessText = exposure
    ? exposure.quote_latest_date
      ? exposure.quote_is_today
        ? `官方净值已更新到 ${exposure.quote_latest_date}`
        : `官方净值最新到 ${exposure.quote_latest_date}，不是 ${exposure.quote_today || "今天"} 的实时盈亏`
      : exposure.snapshot_date
        ? `当前展示导入快照 ${exposure.snapshot_date} 的盈亏，尚未拿到实时净值`
        : "暂未拿到持仓净值日期"
    : "持仓数据加载中";
  const sectorRows = useMemo(() => sectors?.sectors?.slice(0, 6) || [], [sectors]);
  const riskAlerts = strategy?.alerts || [];
  const quoteSource = sectors?.data_quality?.industry_quote_source === "ths"
    ? "同花顺行业汇总"
    : sectors?.data_quality?.industry_quote_source === "eastmoney"
      ? "东方财富行业行情"
      : "行业资金流";

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4 animate-fade-in">
        <div>
          <h1 className="text-xl font-semibold text-ink">今日工作台</h1>
          <p className="mt-1 text-sm text-ink-muted">先看仓位约束、板块资金和候选基金，再进入星图问策做深度判断。</p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => loadDashboard(true)}
            disabled={loading}
            className="focus-ring inline-flex h-9 items-center rounded-lg border border-line bg-surface-2 px-3 text-sm text-ink-secondary transition-colors hover:border-jade/30 hover:text-ink disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? "刷新中" : "刷新数据"}
          </button>
          <Link className="focus-ring inline-flex h-9 items-center gap-2 rounded-lg bg-jade px-4 text-sm text-white shadow-glow transition-all hover:shadow-glow-md" href="/chat">
            <Brain size={16} aria-hidden />
            星图问策
          </Link>
          <Link className="focus-ring inline-flex h-9 items-center gap-2 rounded-lg border border-line bg-surface-2 px-3 text-sm text-ink-secondary transition-colors hover:border-jade/30 hover:text-ink" href="/sectors">
            板块风向
            <ArrowRight size={15} aria-hidden />
          </Link>
        </div>
      </div>

      <section className="grid grid-cols-5 gap-4 animate-fade-in-delay">
        <MetricCard label="持仓市值" value={formatMoney(exposure?.total_amount)} icon={LineChart} />
        <MetricCard
          label={usesSnapshotPnl ? "快照日盈亏" : "当日盈亏"}
          value={formatSignedMoney(pnlValue)}
          tone={pnlValue == null ? "neutral" : pnlValue >= 0 ? "good" : "bad"}
          icon={TrendingUp}
        />
        <MetricCard
          label={usesSnapshotPnl ? "快照涨跌" : "净值涨跌"}
          value={formatPct(returnValue)}
          tone={returnValue == null ? "neutral" : returnValue >= 0 ? "good" : "bad"}
          icon={ShieldCheck}
        />
        <MetricCard label="最大单仓" value={exposure?.largest_position ? `${exposure.largest_position.position_pct.toFixed(1)}%` : "暂无"} tone="warn" icon={AlertTriangle} />
        <MetricCard label="自选基金" value={`${watchCount}`} tone="good" icon={Star} />
      </section>

      <div className="rounded-lg border border-line bg-surface-2/70 px-4 py-3 text-sm text-ink-secondary">
        <span className="font-medium text-ink">盈亏数据状态：</span>
        {quoteFreshnessText}
        {exposure?.quote_oldest_date && exposure.quote_oldest_date !== exposure.quote_latest_date ? `，部分基金仍停留在 ${exposure.quote_oldest_date}` : ""}
        {lastUpdated ? `。页面刷新时间：${formatClock(lastUpdated)}` : ""}
      </div>

      {message ? (
        <div className="rounded-lg border border-amberline/30 bg-amberline/8 px-4 py-3 text-sm text-amberline">
          {message}
        </div>
      ) : null}

      <section className="grid grid-cols-[minmax(0,1.1fr)_minmax(360px,0.9fr)] gap-5">
        <div className="glass-card p-5 animate-fade-in">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-ink">组合约束</h2>
              <p className="mt-1 text-sm text-ink-muted">先确认能不能动仓，再决定买什么。</p>
            </div>
            <Link className="text-sm text-jade hover:underline" href="/portfolio">调整配置</Link>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <SmallMetric label="持有基金" value={`${exposure?.holding_count || 0} 只`} />
            <SmallMetric label="QDII 仓位" value={`${(exposure?.qdii_pct || 0).toFixed(1)}%`} />
            <SmallMetric label="主题仓位" value={`${(exposure?.theme_pct || 0).toFixed(1)}%`} />
          </div>
          <div className="mt-4 space-y-2">
            {(riskAlerts.length ? riskAlerts : [{ level: "info", title: "暂无硬性预警", detail: "可以结合板块风向和基金雷达筛选候选。", action: "保持人工确认" }]).slice(0, 3).map((alert, index) => (
              <div key={`${alert.title}-${index}`} className="rounded-lg border border-line bg-surface-2/50 px-3 py-2 text-sm">
                <div className="font-medium text-ink">{alert.title}</div>
                <div className="mt-1 text-ink-secondary">{alert.detail}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="glass-card p-5 animate-fade-in-delay">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-ink">板块资金温度</h2>
              <p className="mt-1 text-sm text-ink-muted">{sectors?.as_of || "加载中"} · {quoteSource}</p>
            </div>
            <Link className="text-sm text-jade hover:underline" href="/sectors">看全量</Link>
          </div>
          <div className="space-y-1.5">
            {sectorRows.map((sector) => <SectorLine key={sector.name} sector={sector} />)}
          </div>
        </div>
      </section>

      <section className="grid grid-cols-[minmax(0,1fr)_360px] gap-5">
        <div className="animate-fade-in-delay-2">
          <div className="mb-3 flex items-end justify-between">
            <div>
              <h2 className="text-base font-semibold text-ink">均衡候选基金</h2>
              <p className="mt-1 text-sm text-ink-muted">全类型初筛，不再默认只看 QDII。</p>
            </div>
            <Link className="text-sm text-jade hover:underline" href="/funds">进入基金雷达</Link>
          </div>
          <FundTable funds={funds} onAdd={addFund} />
        </div>

        <div className="glass-card p-5 animate-fade-in-delay-2">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-base font-semibold text-ink">最近问策</h2>
            <Link className="text-sm text-jade hover:underline" href="/chat">继续提问</Link>
          </div>
          <div className="space-y-2">
            {history.length ? history.map((item) => (
              <Link key={item.id} href="/chat" className="block rounded-lg border border-line bg-surface-2/40 px-3 py-2.5 text-sm transition-all hover:border-jade/30 hover:bg-jade/5">
                <div className="line-clamp-2 font-medium text-ink">{item.query}</div>
                <div className="mt-1 text-xs text-ink-muted">{formatTime(item.created_at)}</div>
              </Link>
            )) : (
              <div className="rounded-lg border border-dashed border-line px-3 py-8 text-center text-sm text-ink-muted">暂无问策记录</div>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}

function SmallMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-surface-2/60 px-3 py-3">
      <div className="text-xs text-ink-muted">{label}</div>
      <div className="mt-1 text-lg font-semibold tabular-nums text-ink">{value}</div>
    </div>
  );
}

function SectorLine({ sector }: { sector: SectorRecord }) {
  const changePct = Number(sector.change_pct || 0);
  const netInflow = Number(sector.net_inflow || 0);
  return (
    <div className="grid grid-cols-[1fr_80px_90px_74px] items-center gap-2 rounded-lg bg-surface-2/40 px-3 py-2 text-sm transition-colors hover:bg-surface-2/70">
      <div className="min-w-0">
        <div className="truncate font-medium text-ink">{sector.name}</div>
        <div className="truncate text-xs text-ink-muted">{sector.leading_stock || "暂无领涨股"}</div>
      </div>
      <div className={`tabular-nums ${changePct >= 0 ? "price-up" : "price-down"}`}>{formatPct(sector.change_pct)}</div>
      <div className={`tabular-nums ${netInflow >= 0 ? "price-up" : "price-down"}`}>
        {sector.net_inflow == null ? "暂无" : `${netInflow.toFixed(2)} 亿`}
      </div>
      <div className="text-right text-ink-muted">{sector.recommend_label}</div>
    </div>
  );
}

function formatMoney(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "暂无";
  return `${Number(value).toFixed(0)}`;
}

function formatSignedMoney(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "暂无";
  const next = Number(value);
  return `${next >= 0 ? "+" : ""}${next.toFixed(2)}`;
}

function formatTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function formatClock(value: Date) {
  return value.toLocaleTimeString("zh-CN", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
