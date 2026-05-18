"use client";

import { FormEvent, useState } from "react";
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
import { api, FundDetail, formatPct } from "@/lib/api";

const CHART_COLORS = ["#10b981", "#f59e0b", "#ef4444", "#6366f1", "#ec4899"];

export default function ComparePage() {
  const [codes, setCodes] = useState("040046,270042,050025");
  const [funds, setFunds] = useState<FundDetail[]>([]);
  const [error, setError] = useState("");
  const [viewMode, setViewMode] = useState<"return" | "nav">("return");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    const parsed = codes.split(/[,\s，]+/).map((item) => item.trim()).filter(Boolean).slice(0, 5);
    if (parsed.length < 2) {
      setError("至少输入 2 个基金代码");
      return;
    }
    try {
      const data = await api.compare(parsed, true);
      setFunds(data.funds || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "对比失败");
    }
  }

  const chartData = mergeSeries(funds, viewMode);
  const fundNameByCode = Object.fromEntries(funds.map((fund) => [fund.code, fund.name]));

  return (
    <div className="space-y-5 animate-fade-in">
      <div>
        <h1 className="text-xl font-semibold text-ink">基金对比</h1>
        <p className="mt-1 text-sm text-ink-muted">支持 2-5 只基金，默认用相对收益对比，避免净值接近时线条重叠。</p>
      </div>
      <form onSubmit={submit} className="flex gap-2">
        <input
          className="focus-ring h-10 w-[420px] rounded-lg border border-line bg-surface-2 px-3 font-mono text-sm text-ink placeholder:text-ink-muted"
          value={codes}
          onChange={(event) => setCodes(event.target.value)}
          placeholder="040046,270042"
        />
        <button className="focus-ring h-10 rounded-lg bg-jade px-4 text-sm text-white shadow-glow transition-all hover:shadow-glow-md">对比</button>
      </form>
      {error ? <div className="rounded-lg border border-up/30 bg-up/8 px-4 py-3 text-sm text-up">{error}</div> : null}

      <section className="glass-card p-5">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-ink">{viewMode === "return" ? "相对收益走势" : "单位净值走势"}</h2>
            <p className="mt-1 text-xs text-ink-muted">
              同类指数联接基金走势可能高度重合，请结合图例和下方指标一起看。
            </p>
          </div>
          <div className="flex rounded-lg border border-line bg-surface-2 p-1">
            <button
              className={`focus-ring h-7 rounded-md px-3 text-xs transition-all ${viewMode === "return" ? "bg-jade/12 text-jade" : "text-ink-muted hover:text-ink"}`}
              onClick={() => setViewMode("return")}
              type="button"
            >
              相对收益
            </button>
            <button
              className={`focus-ring h-7 rounded-md px-3 text-xs transition-all ${viewMode === "nav" ? "bg-jade/12 text-jade" : "text-ink-muted hover:text-ink"}`}
              onClick={() => setViewMode("nav")}
              type="button"
            >
              单位净值
            </button>
          </div>
        </div>
        <div className="h-[360px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <CartesianGrid stroke="rgba(56,78,120,0.15)" strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#5a6a85" }} minTickGap={28} />
              <YAxis
                tick={{ fontSize: 11, fill: "#5a6a85" }}
                domain={["dataMin", "dataMax"]}
                tickFormatter={(value) => viewMode === "return" ? `${Number(value).toFixed(0)}%` : Number(value).toFixed(2)}
              />
              <Tooltip
                contentStyle={{
                  background: "rgba(17,25,45,0.95)",
                  border: "1px solid rgba(56,78,120,0.4)",
                  borderRadius: 8,
                  color: "#e8ecf4"
                }}
                formatter={(value, name) => [
                  viewMode === "return" ? `${Number(value).toFixed(2)}%` : Number(value).toFixed(4),
                  fundNameByCode[String(name)] || String(name)
                ]}
              />
              <Legend formatter={(value) => fundNameByCode[String(value)] || String(value)} />
              {funds.map((fund, index) => (
                <Line
                  key={fund.code}
                  type="monotone"
                  dataKey={fund.code}
                  dot={false}
                  stroke={CHART_COLORS[index % CHART_COLORS.length]}
                  strokeWidth={2}
                  strokeDasharray={index === 1 ? "6 3" : index === 3 ? "3 3" : undefined}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="grid grid-cols-3 gap-4">
        {funds.map((fund, index) => {
          const tech = fund.technical || {};
          return (
            <div key={fund.code} className="glass-card p-4 animate-fade-in" style={{ animationDelay: `${index * 0.1}s` }}>
              <div className="flex items-start gap-2">
                <span className="mt-0.5 h-3 w-3 rounded-full" style={{ background: CHART_COLORS[index % CHART_COLORS.length] }} />
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
                  <div className="rounded-md bg-surface-2/60 px-2 py-1.5">
                    <span className="text-ink-muted">RSI </span>
                    <span className="tabular-nums text-ink">{tech.rsi_14 != null ? Number(tech.rsi_14).toFixed(1) : "—"}</span>
                  </div>
                  <div className="rounded-md bg-surface-2/60 px-2 py-1.5">
                    <span className="text-ink-muted">MACD </span>
                    <span className="text-ink">{tech.macd_signal?.includes("偏多") ? "偏多" : tech.macd_signal?.includes("偏空") ? "偏空" : "中性"}</span>
                  </div>
                </div>
              ) : null}
            </div>
          );
        })}
      </section>
    </div>
  );
}

function mergeSeries(funds: FundDetail[], mode: "return" | "nav") {
  const map = new Map<string, Record<string, string | number>>();
  for (const fund of funds) {
    const base = fund.nav_history?.find((point) => Number.isFinite(Number(point.nav)))?.nav;
    for (const point of fund.nav_history || []) {
      if (!map.has(point.date)) map.set(point.date, { date: point.date });
      map.get(point.date)![fund.code] = mode === "return" && base
        ? Number((((point.nav / base) - 1) * 100).toFixed(4))
        : point.nav;
    }
  }
  return Array.from(map.values()).sort((a, b) => String(a.date).localeCompare(String(b.date)));
}

function CompareMetric({ label, value, pct }: { label: string; value: string; pct?: number | null }) {
  return (
    <div className="rounded-md bg-surface-2/60 px-3 py-2">
      <div className="text-xs text-ink-muted">{label}</div>
      <div className={`mt-1 font-medium tabular-nums ${
        pct !== undefined && pct !== null
          ? pct > 0 ? "price-up" : pct < 0 ? "price-down" : "text-ink"
          : "text-ink"
      }`}>
        {value}
      </div>
    </div>
  );
}
