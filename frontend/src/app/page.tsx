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
  const [selectedFund, setSelectedFund] = useState<FundRecord | null>(null);
  const [selectedSector, setSelectedSector] = useState<SectorRecord | null>(null);
  const [selectedHistory, setSelectedHistory] = useState<HistoryItem | null>(null);

  const loadDashboard = useCallback(async (refresh = false) => {
    setLoading(true);
    await Promise.allSettled([
      api.recommend("全部", "balanced", 6, false),
      api.sectorOverview(80, refresh),
      api.portfolioOverview(refresh, !refresh),
      api.history()
    ]).then(([recommend, sectorResult, strategyResult, historyResult]) => {
      if (recommend.status === "fulfilled") {
        const nextFunds = recommend.value.funds || [];
        setFunds(nextFunds);
        setSelectedFund((current) => current || nextFunds[0] || null);
      }
      if (sectorResult.status === "fulfilled") {
        setSectors(sectorResult.value);
        setSelectedSector((current) => current || sectorResult.value.sectors?.[0] || null);
      }
      if (strategyResult.status === "fulfilled") {
        setStrategy(strategyResult.value.strategy);
        setWatchCount(strategyResult.value.strategy.exposure.watchlist_count || 0);
      }
      if (historyResult.status === "fulfilled") {
        const nextHistory = (historyResult.value.items || []).slice(0, 4);
        setHistory(nextHistory);
        setSelectedHistory((current) => current || nextHistory[0] || null);
      }
      const firstError = [recommend, sectorResult, strategyResult, historyResult]
        .find((item) => item.status === "rejected") as PromiseRejectedResult | undefined;
      if (firstError) setMessage(firstError.reason instanceof Error ? firstError.reason.message : "部分数据加载失败");
      setLastUpdated(new Date());
    }).finally(() => {
      setLoading(false);
    });
  }, []);

  useEffect(() => {
    loadDashboard(false).catch(() => undefined);
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") loadDashboard(false);
    }, 60_000);
    return () => window.clearInterval(timer);
  }, [loadDashboard]);

  async function addFund(fund: FundRecord) {
    try {
      await api.createPortfolioItem({ fund_code: fund.code, fund_name: fund.name || fund.code, is_watchlist: true, is_holding: false, source: "manual" });
      const nextStrategy = await api.portfolioStrategy(false);
      setStrategy(nextStrategy);
      setWatchCount(nextStrategy.exposure.watchlist_count || 0);
      setMessage(`${fund.name} 已加入观察池`);
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
            {sectorRows.map((sector) => (
              <SectorLine
                key={sector.name}
                sector={sector}
                selected={selectedSector?.name === sector.name}
                onSelect={() => setSelectedSector(sector)}
              />
            ))}
          </div>
          {selectedSector ? <SelectedSectorCard sector={selectedSector} /> : null}
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
          <FundTable funds={funds} onAdd={addFund} onSelect={setSelectedFund} />
          {selectedFund ? <SelectedFundCard fund={selectedFund} /> : null}
        </div>

        <div className="glass-card p-5 animate-fade-in-delay-2">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-base font-semibold text-ink">最近问策</h2>
            <Link className="text-sm text-jade hover:underline" href="/chat">继续提问</Link>
          </div>
          <div className="space-y-2">
            {history.length ? history.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setSelectedHistory(item)}
                className={`block w-full rounded-lg border px-3 py-2.5 text-left text-sm transition-all hover:border-jade/30 hover:bg-jade/5 ${
                  selectedHistory?.id === item.id ? "border-jade/30 bg-jade/8" : "border-line bg-surface-2/40"
                }`}
              >
                <div className="line-clamp-2 font-medium text-ink">{item.query}</div>
                <div className="mt-1 text-xs text-ink-muted">{formatTime(item.created_at)}</div>
              </button>
            )) : (
              <div className="rounded-lg border border-dashed border-line px-3 py-8 text-center text-sm text-ink-muted">暂无问策记录</div>
            )}
          </div>
          {selectedHistory ? <HistoryPreview item={selectedHistory} /> : null}
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

function SectorLine({ sector, selected, onSelect }: { sector: SectorRecord; selected?: boolean; onSelect?: () => void }) {
  const changePct = Number(sector.change_pct || 0);
  const netInflow = Number(sector.net_inflow || 0);
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`grid w-full grid-cols-[1fr_80px_90px_74px] items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition-colors hover:bg-surface-2/70 ${
        selected ? "bg-jade/8 ring-1 ring-jade/20" : "bg-surface-2/40"
      }`}
    >
      <div className="min-w-0">
        <div className="truncate font-medium text-ink">{sector.name}</div>
        <div className="truncate text-xs text-ink-muted">{sector.leading_stock || "暂无领涨股"}</div>
      </div>
      <div className={`tabular-nums ${changePct >= 0 ? "price-up" : "price-down"}`}>{formatPct(sector.change_pct)}</div>
      <div className={`tabular-nums ${netInflow >= 0 ? "price-up" : "price-down"}`}>
        {sector.net_inflow == null ? "暂无" : `${netInflow.toFixed(2)} 亿`}
      </div>
      <div className="text-right text-ink-muted">{sector.recommend_label}</div>
    </button>
  );
}

function SelectedSectorCard({ sector }: { sector: SectorRecord }) {
  const netInflow = Number(sector.net_inflow || 0);
  return (
    <div className="mt-4 rounded-lg border border-line bg-surface-2/50 px-3 py-3 text-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-semibold text-ink">{sector.name}</div>
          <div className="mt-1 text-xs text-ink-muted">领涨：{sector.leading_stock || "暂无"} · {sector.recommend_label}</div>
        </div>
        <div className={`tabular-nums ${netInflow >= 0 ? "price-up" : "price-down"}`}>
          {sector.net_inflow == null ? "资金暂无" : `${netInflow.toFixed(2)} 亿`}
        </div>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2">
        <SmallMetric label="涨跌幅" value={formatPct(sector.change_pct)} />
        <SmallMetric label="上涨/下跌" value={`${sector.rising_count || 0}/${sector.falling_count || 0}`} />
        <SmallMetric label="风险" value={sector.risk_level || "暂无"} />
      </div>
      {sector.reasons?.length ? (
        <div className="mt-3 space-y-1 text-xs text-ink-secondary">
          {sector.reasons.slice(0, 2).map((reason) => <div key={reason}>• {reason}</div>)}
        </div>
      ) : null}
    </div>
  );
}

function SelectedFundCard({ fund }: { fund: FundRecord }) {
  return (
    <div className="mt-3 rounded-lg border border-line bg-surface-2/50 px-3 py-3 text-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-semibold text-ink">{fund.name || fund.code}</div>
          <div className="mt-1 font-mono text-xs text-ink-muted">{fund.code} · {fund.fund_type || "类型暂无"}</div>
        </div>
        <div className="text-right">
          <div className="text-xs text-ink-muted">风险调整评分</div>
          <div className="text-lg font-semibold tabular-nums text-ink">{fund.score ?? "暂无"}</div>
        </div>
      </div>
      <div className="mt-3 grid grid-cols-4 gap-2">
        <SmallMetric label="当日" value={formatPct(fund.daily_return)} />
        <SmallMetric label="近1月" value={formatPct(fund.month_return)} />
        <SmallMetric label="近3月" value={formatPct(fund.three_month_return)} />
        <SmallMetric label="近1年" value={formatPct(fund.year_return)} />
      </div>
      <div className="mt-3 text-xs leading-5 text-ink-muted">
        此处是总览内筛选摘要。持仓披露通常按季度或半年更新，不能把它当作实时换仓信号；实时部分主要来自净值和股票行情估算。
      </div>
    </div>
  );
}

function HistoryPreview({ item }: { item: HistoryItem }) {
  return (
    <div className="mt-4 rounded-lg border border-line bg-surface-2/50 px-3 py-3 text-sm">
      <div className="font-medium text-ink">{item.query}</div>
      <div className="mt-2 line-clamp-6 whitespace-pre-wrap text-ink-secondary">{item.response || "暂无回答内容"}</div>
      <div className="mt-2 text-xs text-ink-muted">{formatTime(item.created_at)}</div>
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
