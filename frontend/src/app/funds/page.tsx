"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import { api, FundDetail, FundRecord, formatPct } from "@/lib/api";
import { FundTable } from "@/components/fund/FundTable";
import { FundDetailPanel } from "@/components/fund/FundDetailPanel";
import { GitCompare } from "lucide-react";

const types = ["全部", "QDII", "指数型", "股票型", "混合型", "债券型"];
const CHART_COLORS = ["#10b981", "#f59e0b", "#ef4444", "#6366f1", "#ec4899"];

type TabMode = "radar" | "compare";

export default function FundsPage() {
  const [tab, setTab] = useState<TabMode>("radar");

  // Radar state
  const [fundType, setFundType] = useState("全部");
  const [funds, setFunds] = useState<FundRecord[]>([]);
  const [selected, setSelected] = useState<FundDetail | null>(null);
  const [query, setQuery] = useState("");
  const [message, setMessage] = useState("");

  // Compare state
  const [compareCodes, setCompareCodes] = useState("040046,270042,050025");
  const [compareFunds, setCompareFunds] = useState<FundDetail[]>([]);
  const [viewMode, setViewMode] = useState<"return" | "nav">("return");

  useEffect(() => {
    api.rank(fundType, 30, true)
      .then((data) => { setFunds(data.funds || []); setMessage(data.warning || ""); })
      .catch((error) => setMessage(error instanceof Error ? error.message : "加载失败"));
  }, [fundType]);

  async function addFund(fund: FundRecord) {
    try { await api.addWatch(fund.code, fund.name); setMessage(`${fund.name} 已加入自选`); }
    catch (err) { setMessage(err instanceof Error ? err.message : "加入自选失败"); }
  }

  async function search() {
    if (!query.trim()) return;
    try {
      const data = await api.searchFunds(query.trim(), true);
      setFunds(data.funds || []);
      setMessage(data.warning || `找到 ${data.funds?.length || 0} 条结果`);
    } catch (err) { setMessage(err instanceof Error ? err.message : "搜索失败"); }
  }

  async function loadDetail(code: string) {
    const detail = await api.fundDetail(code, true);
    setSelected(detail);
  }

  async function runCompare(event?: FormEvent) {
    event?.preventDefault();
    setMessage("");
    const parsed = compareCodes.split(/[,\s，]+/).map((s) => s.trim()).filter(Boolean).slice(0, 5);
    if (parsed.length < 2) { setMessage("至少输入 2 个基金代码"); return; }
    try {
      const data = await api.compare(parsed, true);
      setCompareFunds(data.funds || []);
    } catch (err) { setMessage(err instanceof Error ? err.message : "对比失败"); }
  }

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Tab switcher + search bar */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="flex rounded-lg border border-line bg-surface-2 p-1">
            <button className={`focus-ring h-9 rounded-md px-4 text-sm transition-all ${tab === "radar" ? "bg-jade/15 font-medium text-jade shadow-inner-glow" : "text-ink-muted hover:text-ink"}`} onClick={() => setTab("radar")}>
              基金雷达
            </button>
            <button className={`focus-ring flex h-9 items-center gap-1.5 rounded-md px-4 text-sm transition-all ${tab === "compare" ? "bg-jade/15 font-medium text-jade shadow-inner-glow" : "text-ink-muted hover:text-ink"}`} onClick={() => setTab("compare")}>
              <GitCompare size={14} /> 基金对比
            </button>
          </div>
          <p className="text-sm text-ink-muted">
            {tab === "radar" ? "筛选候选基金，点击查看净值与技术面。" : "输入 2-5 个基金代码，对比收益和技术指标。"}
          </p>
        </div>
        {tab === "radar" && (
          <div className="flex gap-2">
            <input value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === "Enter" && search()} className="input-styled h-10 w-56 px-3 text-sm" placeholder="代码或名称" />
            <button className="btn-primary h-10 px-4 text-sm" onClick={search}>搜索</button>
          </div>
        )}
      </div>

      {message ? <div className="rounded-xl border border-amberline/30 bg-amberline/8 px-4 py-3 text-sm text-amberline">{message}</div> : null}

      {/* ─── Radar Tab ─── */}
      {tab === "radar" && (
        <>
          <div className="flex gap-2">
            {types.map((type) => (
              <button key={type} className={`focus-ring h-9 rounded-lg border px-3 text-sm transition-all ${fundType === type ? "border-jade/40 bg-jade/12 text-jade shadow-inner-glow" : "border-line bg-surface-2 text-ink-secondary hover:border-jade/20 hover:text-ink"}`} onClick={() => setFundType(type)}>
                {type}
              </button>
            ))}
          </div>
          <div className="grid grid-cols-[minmax(0,1fr)_460px] gap-5">
            <div onClick={(e) => { const row = (e.target as HTMLElement).closest("tr"); const code = row?.querySelector(".font-mono")?.textContent?.trim(); if (code && /^\d{6}$/.test(code)) loadDetail(code); }}>
              <FundTable funds={funds} onAdd={addFund} />
            </div>
            <div className="sticky top-[72px] self-start">
              <FundDetailPanel fund={selected} />
            </div>
          </div>
        </>
      )}

      {/* ─── Compare Tab ─── */}
      {tab === "compare" && (
        <>
          <form onSubmit={runCompare} className="flex gap-2">
            <input className="input-styled h-10 w-[420px] px-3 font-mono text-sm" value={compareCodes} onChange={(e) => setCompareCodes(e.target.value)} placeholder="040046,270042,050025" />
            <button className="btn-primary h-10 px-4 text-sm">对比</button>
          </form>

          {compareFunds.length > 0 && (
            <>
              <div className="glass-card p-5">
                <div className="mb-4 flex items-center justify-between">
                  <div>
                    <h2 className="text-sm font-semibold text-ink">{viewMode === "return" ? "相对收益走势" : "单位净值走势"}</h2>
                    <p className="mt-1 text-xs text-ink-muted">同类指数联接走势可能高度重合，结合下方指标一起看。</p>
                  </div>
                  <div className="flex rounded-lg border border-line bg-surface-2 p-1">
                    <button className={`focus-ring h-7 rounded-md px-3 text-xs transition-all ${viewMode === "return" ? "bg-jade/12 text-jade" : "text-ink-muted hover:text-ink"}`} onClick={() => setViewMode("return")} type="button">相对收益</button>
                    <button className={`focus-ring h-7 rounded-md px-3 text-xs transition-all ${viewMode === "nav" ? "bg-jade/12 text-jade" : "text-ink-muted hover:text-ink"}`} onClick={() => setViewMode("nav")} type="button">单位净值</button>
                  </div>
                </div>
                <div className="h-[360px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={mergeSeries(compareFunds, viewMode)}>
                      <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
                      <XAxis dataKey="date" tick={{ fontSize: 11, fill: "var(--text-muted)" }} minTickGap={28} />
                      <YAxis tick={{ fontSize: 11, fill: "var(--text-muted)" }} domain={["dataMin", "dataMax"]} tickFormatter={(v) => viewMode === "return" ? `${Number(v).toFixed(0)}%` : Number(v).toFixed(2)} />
                      <Tooltip contentStyle={{ background: "var(--bg-card-solid)", border: "1px solid var(--border)", borderRadius: 8, color: "var(--text-primary)" }} formatter={(v, name) => [viewMode === "return" ? `${Number(v).toFixed(2)}%` : Number(v).toFixed(4), compareFunds.find((f) => f.code === String(name))?.name || String(name)]} />
                      <Legend formatter={(v) => compareFunds.find((f) => f.code === String(v))?.name || String(v)} />
                      {compareFunds.map((fund, i) => (
                        <Line key={fund.code} type="monotone" dataKey={fund.code} dot={false} stroke={CHART_COLORS[i % CHART_COLORS.length]} strokeWidth={2} strokeDasharray={i === 1 ? "6 3" : i === 3 ? "3 3" : undefined} />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4">
                {compareFunds.map((fund, i) => {
                  const tech = fund.technical || {};
                  return (
                    <div key={fund.code} className="glass-card p-4 animate-fade-in" style={{ animationDelay: `${i * 0.1}s` }}>
                      <div className="flex items-start gap-2">
                        <span className="mt-0.5 h-3 w-3 rounded-full shrink-0" style={{ background: CHART_COLORS[i % CHART_COLORS.length] }} />
                        <div>
                          <div className="font-semibold text-ink">{fund.name}</div>
                          <div className="mt-0.5 font-mono text-xs text-ink-muted">{fund.code}</div>
                        </div>
                      </div>
                      <div className="mt-4 grid grid-cols-2 gap-2 text-sm">
                        <CompareMetric label="近1月" value={formatPct(fund.metrics.month_return)} pct={fund.metrics.month_return} />
                        <CompareMetric label="近3月" value={formatPct(fund.metrics.three_month_return)} pct={fund.metrics.three_month_return} />
                        <CompareMetric label="回撤" value={formatPct(fund.metrics.max_drawdown)} />
                        <CompareMetric label="波动" value={formatPct(fund.metrics.volatility)} />
                      </div>
                      {tech.available ? (
                        <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                          <div className="rounded-md bg-surface-2/60 px-2 py-1.5"><span className="text-ink-muted">RSI </span><span className="tabular-nums text-ink">{tech.rsi_14 != null ? Number(tech.rsi_14).toFixed(1) : "—"}</span></div>
                          <div className="rounded-md bg-surface-2/60 px-2 py-1.5"><span className="text-ink-muted">MACD </span><span className="text-ink">{tech.macd_signal?.includes("偏多") ? "偏多" : tech.macd_signal?.includes("偏空") ? "偏空" : "中性"}</span></div>
                        </div>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}

function mergeSeries(funds: FundDetail[], mode: "return" | "nav") {
  const map = new Map<string, Record<string, string | number>>();
  for (const fund of funds) {
    const base = fund.nav_history?.find((p) => Number.isFinite(Number(p.nav)))?.nav;
    for (const p of fund.nav_history || []) {
      if (!map.has(p.date)) map.set(p.date, { date: p.date });
      map.get(p.date)![fund.code] = mode === "return" && base ? Number((((p.nav / base) - 1) * 100).toFixed(4)) : p.nav;
    }
  }
  return Array.from(map.values()).sort((a, b) => String(a.date).localeCompare(String(b.date)));
}

function CompareMetric({ label, value, pct }: { label: string; value: string; pct?: number | null }) {
  return (
    <div className="rounded-md bg-surface-2/60 px-3 py-2">
      <div className="text-xs text-ink-muted">{label}</div>
      <div className={`mt-1 font-medium tabular-nums ${pct !== undefined && pct !== null ? pct > 0 ? "price-up" : pct < 0 ? "price-down" : "text-ink" : "text-ink"}`}>{value}</div>
    </div>
  );
}
