"use client";

import { useEffect, useMemo, useState } from "react";
import { Activity, ChevronDown, ChevronRight, RefreshCw } from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import { api, FundDetail, FundRealtimeContributor, FundRealtimeEstimate, formatPct, StockRealtimeQuote } from "@/lib/api";

const ranges = [
  { label: "近1月", days: 30 },
  { label: "近3月", days: 90 },
  { label: "近6月", days: 180 },
  { label: "近1年", days: 365 },
  { label: "全部", days: 0 }
];

export function FundDetailPanel({ fund }: { fund: FundDetail | null }) {
  const [range, setRange] = useState(ranges[2]);
  const [estimate, setEstimate] = useState<FundRealtimeEstimate | null>(null);
  const [estimateLoading, setEstimateLoading] = useState(false);
  const [estimateError, setEstimateError] = useState("");

  const filteredHistory = useMemo(() => {
    const history = fund?.nav_history || [];
    if (!range.days || history.length === 0) return history;
    const last = new Date(history[history.length - 1].date).getTime();
    if (Number.isNaN(last)) return history.slice(-range.days);
    const start = last - range.days * 24 * 60 * 60 * 1000;
    const filtered = history.filter((item) => new Date(item.date).getTime() >= start);
    return filtered.length ? filtered : history.slice(-Math.min(range.days, history.length));
  }, [fund, range]);

  async function loadRealtimeEstimate(refresh = false) {
    const code = fund?.code;
    if (!code) return;
    setEstimateLoading(true);
    setEstimateError("");
    try {
      const data = await api.fundRealtimeEstimate(code, refresh);
      setEstimate(data);
    } catch (error) {
      setEstimateError(error instanceof Error ? error.message : "实时估算加载失败");
    } finally {
      setEstimateLoading(false);
    }
  }

  useEffect(() => {
    if (!fund?.code) {
      setEstimate(null);
      setEstimateError("");
      setEstimateLoading(false);
      return;
    }
    const code = fund.code;
    let active = true;
    setEstimate(null);
    async function load(refresh = false) {
      setEstimateLoading(true);
      setEstimateError("");
      try {
        const data = await api.fundRealtimeEstimate(code, refresh);
        if (active) setEstimate(data);
      } catch (error) {
        if (active) setEstimateError(error instanceof Error ? error.message : "实时估算加载失败");
      } finally {
        if (active) setEstimateLoading(false);
      }
    }
    const initialTimer = window.setTimeout(() => load(), 200);
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") load(false);
    }, 20_000);
    return () => {
      active = false;
      window.clearTimeout(initialTimer);
      window.clearInterval(timer);
    };
  }, [fund?.code]);

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
  const displayNav = estimate?.estimated_nav ?? fund.latest_nav;
  const displayReturn = estimate?.estimated_return_pct;

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
          <div className="text-xs text-ink-muted">{estimate?.estimated_nav != null ? "估算净值" : estimateLoading ? "估算中" : "最新净值"}</div>
          <div className="text-2xl font-semibold tabular-nums text-[var(--accent)]">{displayNav ?? "暂无"}</div>
          {displayReturn != null ? (
            <div className={`mt-1 text-xs tabular-nums ${displayReturn >= 0 ? "price-up" : "price-down"}`}>
              估算涨跌 {formatPct(displayReturn)}
            </div>
          ) : null}
        </div>
      </div>

      {fund.warning ? (
        <div className="mt-4 rounded-lg border border-amberline/30 bg-amberline/8 px-3 py-2 text-sm text-amberline">
          {fund.warning}
        </div>
      ) : null}

      <RealtimeEstimateCard
        estimate={estimate}
        loading={estimateLoading}
        error={estimateError}
        onRefresh={() => loadRealtimeEstimate(true)}
      />

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

function RealtimeEstimateCard({
  estimate,
  loading,
  error,
  onRefresh
}: {
  estimate: FundRealtimeEstimate | null;
  loading: boolean;
  error: string;
  onRefresh: () => void;
}) {
  const [showAllHoldings, setShowAllHoldings] = useState(false);
  const [selectedStockCode, setSelectedStockCode] = useState<string | null>(null);
  const [stockQuote, setStockQuote] = useState<StockRealtimeQuote | null>(null);
  const [stockLoading, setStockLoading] = useState(false);
  const [stockError, setStockError] = useState("");
  const allocation = estimate?.asset_allocation || {};
  const coverage = estimate?.coverage || {};
  const contribution = estimate?.contribution || {};
  const stockContributors = estimate?.stock_contributors || [];
  const visibleStockContributors = showAllHoldings ? stockContributors : stockContributors.slice(0, 8);
  const estimatedReturn = numberValue(estimate?.estimated_return_pct);
  const stockContribution = numberValue(contribution.stock_estimated_pct);
  const bondContribution = numberValue(contribution.bond_estimated_pct);

  async function toggleStockQuote(item: FundRealtimeContributor) {
    const code = item.stock_code;
    if (!code) return;
    if (selectedStockCode === code) {
      setSelectedStockCode(null);
      setStockQuote(null);
      setStockError("");
      return;
    }
    setSelectedStockCode(code);
    setStockQuote(null);
    setStockError("");
    setStockLoading(true);
    try {
      const data = await api.stockQuote(code);
      setStockQuote(data);
    } catch (error) {
      setStockError(error instanceof Error ? error.message : "股票行情加载失败");
    } finally {
      setStockLoading(false);
    }
  }

  return (
    <div className="mt-5 rounded-lg border border-line bg-surface-2/45 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-2">
          <div className="mt-0.5 rounded-md bg-jade/12 p-1.5 text-jade">
            <Activity size={16} aria-hidden />
          </div>
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-ink">实时持仓估算</h3>
            <p className="mt-1 text-xs leading-5 text-ink-muted">
              按最近披露持仓与实时行情估算，现金/银行存款和无行情资产按 0 贡献处理。
            </p>
          </div>
        </div>
        <button
          className="focus-ring inline-flex h-8 shrink-0 items-center gap-1.5 rounded-lg border border-line bg-surface-1 px-2.5 text-xs text-ink-secondary transition-colors hover:border-jade/30 hover:text-jade disabled:cursor-not-allowed disabled:opacity-60"
          disabled={loading}
          onClick={onRefresh}
          type="button"
        >
          <RefreshCw size={13} className={loading ? "animate-spin" : ""} aria-hidden />
          刷新
        </button>
      </div>

      {error ? (
        <div className="mt-3 rounded-lg border border-amberline/30 bg-amberline/8 px-3 py-2 text-xs text-amberline">
          {error}
        </div>
      ) : null}

      {!estimate && !error ? (
        <div className="mt-3 rounded-lg border border-dashed border-line px-3 py-5 text-center text-xs text-ink-muted">
          {loading ? "正在读取披露持仓和实时行情..." : "暂无实时估算数据"}
        </div>
      ) : null}

      {estimate ? (
        <>
          <div className="mt-4 grid grid-cols-4 gap-3">
            <EstimateMetric label="估算涨跌" value={formatPct(estimatedReturn)} pct={estimatedReturn} />
            <EstimateMetric label="估算净值" value={estimate.estimated_nav == null ? "暂无" : Number(estimate.estimated_nav).toFixed(4)} />
            <EstimateMetric label="官方净值涨跌" value={formatPct(estimate.official_daily_return)} pct={estimate.official_daily_return} />
            <EstimateMetric label="可信度" value={coverage.confidence || "暂无"} />
          </div>

          <div className="mt-4 grid grid-cols-[1fr_1fr] gap-3">
            <div className="rounded-lg border border-line bg-surface-1/60 p-3">
              <div className="mb-2 flex items-center justify-between text-xs">
                <span className="font-medium text-ink-muted">资产比例</span>
                <span className="font-mono text-ink-muted">{formatReportDate(allocation.report_date)}</span>
              </div>
              <AssetShare label="股票" value={allocation.stock_pct} tone="up" />
              <AssetShare label="债券" value={allocation.bond_pct} tone="warn" />
              <AssetShare label="银行/现金" value={allocation.bank_cash_pct} tone="neutral" />
              <AssetShare label="其他" value={allocation.other_pct} tone="neutral" />
            </div>

            <div className="rounded-lg border border-line bg-surface-1/60 p-3">
              <div className="mb-2 text-xs font-medium text-ink-muted">贡献拆解</div>
              <ContributorSummary label="股票估算贡献" value={stockContribution} />
              <ContributorSummary label="债券估算贡献" value={bondContribution} />
              <ContributorSummary label="银行/现金贡献" value={0} />
              <div className="mt-2 rounded-md bg-surface-2/70 px-2 py-1.5 text-[11px] leading-5 text-ink-muted">
                行情覆盖 {formatPct(coverage.quote_coverage_ratio)}，资产外推覆盖 {formatPct(coverage.asset_coverage_ratio)}
              </div>
            </div>
          </div>

          {stockContributors.length ? (
            <div className="mt-4">
              <div className="mb-2 flex items-center justify-between gap-3">
                <div>
                  <div className="text-xs font-medium text-ink-muted">持仓股票实时贡献</div>
                  <div className="mt-0.5 text-[11px] text-ink-muted">
                    {stockContributors.length} 只披露股票，点击股票查看实时交易快照
                  </div>
                </div>
                {stockContributors.length > 8 ? (
                  <button
                    className="focus-ring h-7 rounded-md border border-line bg-surface-1 px-2 text-xs text-ink-secondary transition-colors hover:border-jade/30 hover:text-jade"
                    onClick={() => setShowAllHoldings((value) => !value)}
                    type="button"
                  >
                    {showAllHoldings ? "收起" : `展开全部 ${stockContributors.length}`}
                  </button>
                ) : null}
              </div>
              <div className="rounded-lg border border-line bg-surface-1/50">
                <div className="grid grid-cols-[minmax(0,1fr)_70px_70px_78px_28px] gap-2 border-b border-line px-3 py-2 text-[11px] text-ink-muted">
                  <div>股票</div>
                  <div className="text-right">持仓</div>
                  <div className="text-right">涨跌</div>
                  <div className="text-right">贡献</div>
                  <div />
                </div>
                {visibleStockContributors.map((item, index) => (
                  <div key={`${item.stock_code || item.stock_name}-${index}`}>
                    <RealtimeContributorLine
                      item={item}
                      selected={selectedStockCode === item.stock_code}
                      onSelect={() => toggleStockQuote(item)}
                    />
                    {selectedStockCode === item.stock_code ? (
                      <StockQuotePanel quote={stockQuote} loading={stockLoading} error={stockError} fallback={item} />
                    ) : null}
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {estimate.warnings?.length ? (
            <div className="mt-3 space-y-1">
              {estimate.warnings.slice(0, 3).map((warning) => (
                <div key={warning} className="rounded-md bg-amberline/8 px-2.5 py-1.5 text-[11px] leading-5 text-amberline">
                  {warning}
                </div>
              ))}
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

function EstimateMetric({ label, value, pct }: { label: string; value: string; pct?: number | null }) {
  return (
    <div className="rounded-lg bg-surface-1/70 px-3 py-2.5">
      <div className="text-xs text-ink-muted">{label}</div>
      <div className={`mt-1 text-base font-semibold tabular-nums ${
        pct == null ? "text-ink" : pct >= 0 ? "price-up" : "price-down"
      }`}>
        {value}
      </div>
    </div>
  );
}

function AssetShare({ label, value, tone }: { label: string; value?: number | null; tone: "up" | "warn" | "neutral" }) {
  const pct = Math.max(0, Math.min(Number(value || 0), 100));
  const color = tone === "up" ? "bg-jade" : tone === "warn" ? "bg-amberline" : "bg-line-strong";
  return (
    <div className="mb-2 last:mb-0">
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="text-ink-secondary">{label}</span>
        <span className="tabular-nums text-ink-muted">{formatPct(value)}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-surface-2">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function ContributorSummary({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="flex items-center justify-between border-b border-line/60 py-1.5 text-xs last:border-0">
      <span className="text-ink-secondary">{label}</span>
      <span className={`tabular-nums ${value == null ? "text-ink-muted" : value >= 0 ? "price-up" : "price-down"}`}>
        {formatPct(value)}
      </span>
    </div>
  );
}

function RealtimeContributorLine({
  item,
  selected,
  onSelect
}: {
  item: FundRealtimeContributor;
  selected: boolean;
  onSelect: () => void;
}) {
  const contribution = numberValue(item.contribution_pct);
  return (
    <button
      className={`focus-ring grid w-full grid-cols-[minmax(0,1fr)_70px_70px_78px_28px] items-center gap-2 border-b border-line/50 px-3 py-2 text-left text-xs transition-colors last:border-b-0 hover:bg-surface-2/70 ${
        selected ? "bg-jade/8" : ""
      }`}
      onClick={onSelect}
      type="button"
    >
      <div className="min-w-0">
        <div className="truncate font-medium text-ink">{item.stock_name || item.bond_name || "未命名持仓"}</div>
        <div className="font-mono text-[11px] text-ink-muted">{item.stock_code || item.bond_code || "代码暂无"}</div>
      </div>
      <div className="text-right tabular-nums text-ink-secondary">{formatPct(item.hold_ratio)}</div>
      <div className={`text-right tabular-nums ${item.change_pct == null ? "text-ink-muted" : item.change_pct >= 0 ? "price-up" : "price-down"}`}>
        {formatPct(item.change_pct)}
      </div>
      <div className={`text-right tabular-nums font-medium ${contribution == null ? "text-ink-muted" : contribution >= 0 ? "price-up" : "price-down"}`}>
        {formatPct(contribution)}
      </div>
      <div className="flex justify-end text-ink-muted">
        {selected ? <ChevronDown size={14} aria-hidden /> : <ChevronRight size={14} aria-hidden />}
      </div>
    </button>
  );
}

function StockQuotePanel({
  quote,
  loading,
  error,
  fallback
}: {
  quote: StockRealtimeQuote | null;
  loading: boolean;
  error: string;
  fallback: FundRealtimeContributor;
}) {
  const changePct = quote?.change_pct ?? fallback.change_pct;
  return (
    <div className="border-b border-line/50 bg-surface-2/55 px-3 py-3">
      {loading ? (
        <div className="text-xs text-ink-muted">正在读取股票实时交易快照...</div>
      ) : error ? (
        <div className="rounded-md border border-amberline/30 bg-amberline/8 px-2.5 py-2 text-xs text-amberline">{error}</div>
      ) : (
        <div className="grid grid-cols-5 gap-2 text-xs">
          <StockQuoteMetric label="最新价" value={quote?.latest_price ?? fallback.latest_price ?? null} />
          <StockQuoteMetric label="涨跌幅" value={changePct} pct />
          <StockQuoteMetric label="换手率" value={quote?.turnover_rate ?? null} pct />
          <StockQuoteMetric label="成交额" value={formatAmount(quote?.amount)} />
          <StockQuoteMetric label="来源" value={quote?.source || fallback.quote_source || "暂无"} />
        </div>
      )}
    </div>
  );
}

function StockQuoteMetric({ label, value, pct = false }: { label: string; value: unknown; pct?: boolean }) {
  const numeric = typeof value === "number" ? value : null;
  return (
    <div className="rounded-md bg-surface-1/80 px-2.5 py-2">
      <div className="text-[11px] text-ink-muted">{label}</div>
      <div className={`mt-1 truncate tabular-nums text-sm font-medium ${
        pct && numeric != null ? numeric >= 0 ? "price-up" : "price-down" : "text-ink"
      }`}>
        {pct && numeric != null ? formatPct(numeric) : value == null || value === "" ? "暂无" : String(value)}
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

function formatReportDate(value: unknown) {
  if (!value) return "报告期暂无";
  const text = String(value);
  if (/^\d{8}$/.test(text)) return `${text.slice(0, 4)}-${text.slice(4, 6)}-${text.slice(6, 8)}`;
  return text;
}

function formatAmount(value: unknown) {
  const amount = Number(value);
  if (!Number.isFinite(amount)) return "暂无";
  if (Math.abs(amount) >= 100_000_000) return `${(amount / 100_000_000).toFixed(2)}亿`;
  if (Math.abs(amount) >= 10_000) return `${(amount / 10_000).toFixed(2)}万`;
  return amount.toFixed(2);
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

