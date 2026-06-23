"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import { api, formatPct, SectorOverview, SectorRecord } from "@/lib/api";

function formatMoney(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "暂无";
  return `${Number(value).toFixed(2)} 亿`;
}

function newsText(item: Record<string, unknown>) {
  const candidates = ["summary", "摘要", "内容", "标题", "title", "content"];
  for (const key of candidates) {
    const value = item[key];
    if (value) return String(value).replace(/https?:\/\/\S+/gi, "").trim();
  }
  return Object.entries(item)
    .filter(([key, value]) => value && !/url|link/i.test(key) && !/^https?:\/\//i.test(String(value)))
    .map(([, value]) => String(value))
    .join(" ")
    .replace(/https?:\/\/\S+/gi, "")
    .trim();
}

function looksGarbled(text: string) {
  const badMatches = text.match(/�|ï¿½|����/g);
  const badCount = badMatches?.length || 0;
  return badCount >= 2 || badCount / Math.max(text.length, 1) > 0.05;
}

function cleanNews(items: Array<Record<string, unknown>>) {
  return items
    .map((item) => ({ item, text: newsText(item) }))
    .filter(({ text }) => text && !looksGarbled(text))
    .map(({ item }) => item);
}

function formatNewsTime(item: Record<string, unknown>, fallback: string) {
  const value = item.time || item.datetime || item.date || item.publish_time || item["发布时间"] || item["时间"] || fallback;
  if (/^\d{4}-\d{2}-\d{2}$/.test(String(value).trim())) return fallback;
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) return fallback;
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false
  });
}

export default function SectorsPage() {
  const [data, setData] = useState<SectorOverview | null>(null);
  const [selected, setSelected] = useState<SectorRecord | null>(null);
  const [news, setNews] = useState<Array<Record<string, unknown>>>([]);
  const [newsFetchedAt, setNewsFetchedAt] = useState("");
  const [newsLoading, setNewsLoading] = useState(false);
  const [message, setMessage] = useState("");

  const loadNews = useCallback((sector: SectorRecord, refresh = false) => {
    setNewsLoading(true);
    api.sectorNews(sector.name, 8, refresh)
      .then((result) => {
        setNews(result.news || []);
        setNewsFetchedAt(new Date().toLocaleString("zh-CN", {
          year: "numeric",
          month: "2-digit",
          day: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hour12: false
        }));
        setMessage(result.warning || "");
      })
      .catch((error) => setMessage(error instanceof Error ? error.message : "板块资讯加载失败"))
      .finally(() => setNewsLoading(false));
  }, []);

  const loadOverview = useCallback((refresh = false) => {
    api.sectorOverview(100, refresh)
      .then((result) => {
        setData(result);
        setSelected((current) => {
          if (!current) return result.recommended[0] || result.sectors[0] || null;
          return result.sectors.find((item) => item.name === current.name) || result.recommended[0] || result.sectors[0] || null;
        });
      })
      .catch((error) => setMessage(error instanceof Error ? error.message : "板块数据加载失败"));
  }, []);

  useEffect(() => {
    loadOverview(false);
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") loadOverview(false);
    }, 60_000);
    return () => window.clearInterval(timer);
  }, [loadOverview]);

  useEffect(() => {
    if (!selected) return;
    loadNews(selected, false);
  }, [loadNews, selected]);

  useEffect(() => {
    if (!selected) return;
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") loadNews(selected, false);
    }, 60_000);
    return () => window.clearInterval(timer);
  }, [loadNews, selected]);

  const topMomentum = useMemo(() => {
    return [...(data?.sectors || [])]
      .sort((a, b) => (b.change_pct || 0) - (a.change_pct || 0))
      .slice(0, 12);
  }, [data]);

  const topFlow = useMemo(() => {
    return [...(data?.sectors || [])]
      .filter((item) => item.net_inflow !== null && item.net_inflow !== undefined)
      .sort((a, b) => (b.net_inflow || 0) - (a.net_inflow || 0))
      .slice(0, 12);
  }, [data]);

  const weakMomentum = useMemo(() => {
    return [...(data?.sectors || [])]
      .sort((a, b) => (a.change_pct || 0) - (b.change_pct || 0))
      .slice(0, 12);
  }, [data]);

  const bottomFlow = useMemo(() => {
    return [...(data?.sectors || [])]
      .filter((item) => item.net_inflow !== null && item.net_inflow !== undefined)
      .sort((a, b) => (a.net_inflow || 0) - (b.net_inflow || 0))
      .slice(0, 12);
  }, [data]);

  const readableNews = useMemo(() => cleanNews(news), [news]);

  const rows = data?.sectors || [];

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-ink">板块风向</h1>
          <p className="mt-1 text-sm text-ink-muted">
            跟踪行业板块强弱、资金流向、风险分层和实时资讯，用来辅助基金主题选择。
          </p>
        </div>
        <div className="glass-card px-3 py-2 text-right">
          <div className="text-xs text-ink-muted">更新时间</div>
          <div className="mt-1 font-medium text-ink">{data?.as_of || "加载中"}</div>
        </div>
      </div>

      {message ? (
        <div className="rounded-xl border border-amberline/30 bg-amberline/8 px-4 py-3 text-sm text-amberline">{message}</div>
      ) : null}

      <div className="grid grid-cols-4 gap-3">
        <Summary label="优先观察" value={`${data?.recommended.length || 0} 个`} />
        <Summary label="高风险板块" value={`${data?.risk_alerts.filter((item) => item.risk_level === "高").length || 0} 个`} />
        <Summary label="资金净流入" value={formatMoney(data?.flow_summary.total_net_inflow)} />
        <Summary label="覆盖板块" value={`${data?.count || 0} 个`} />
      </div>

      <div className="grid grid-cols-[minmax(0,1fr)_430px] gap-5">
        <section className="space-y-5">
          <div className="grid grid-cols-2 gap-5">
            <ChartPanel title="当日强势板块" data={topMomentum} dataKey="change_pct" unit="%" />
            <ChartPanel title="当日弱势板块" data={weakMomentum} dataKey="change_pct" unit="%" negativeTone />
            <ChartPanel title="资金净流入靠前" data={topFlow} dataKey="net_inflow" unit="亿" />
            <ChartPanel title="资金净流出靠前" data={bottomFlow} dataKey="net_inflow" unit="亿" negativeTone />
          </div>

          <div className="glass-card overflow-hidden">
            <div className="flex items-center justify-between border-b border-line px-4 py-3">
              <h2 className="text-sm font-semibold text-ink">板块明细</h2>
              <span className="text-xs text-ink-muted">点击板块查看风险和资讯</span>
            </div>
            <div className="max-h-[560px] overflow-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-surface-1 text-left text-xs text-ink-muted">
                  <tr>
                    <th className="px-4 py-3 font-medium">板块</th>
                    <th className="px-3 py-3 font-medium">涨跌幅</th>
                    <th className="px-3 py-3 font-medium">资金净流</th>
                    <th className="px-3 py-3 font-medium">风险</th>
                    <th className="px-3 py-3 font-medium">建议</th>
                    <th className="px-3 py-3 font-medium">领涨股</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((item, index) => {
                    const active = selected?.name === item.name;
                    return (
                      <tr
                        key={item.name}
                        className={`cursor-pointer border-t border-line/50 transition-colors hover:bg-surface-2/60 ${
                          active ? "bg-jade/8" : index % 2 === 0 ? "" : "bg-surface-1/30"
                        }`}
                        onClick={() => setSelected(item)}
                      >
                        <td className="px-4 py-3 font-medium text-ink">{item.name}</td>
                        <td className={`px-3 py-3 tabular-nums ${Number(item.change_pct || 0) >= 0 ? "price-up" : "price-down"}`}>
                          {formatPct(item.change_pct)}
                        </td>
                        <td className={`px-3 py-3 tabular-nums ${Number(item.net_inflow || 0) >= 0 ? "price-up" : "price-down"}`}>
                          {formatMoney(item.net_inflow)}
                        </td>
                        <td className="px-3 py-3"><RiskBadge level={item.risk_level} /></td>
                        <td className="px-3 py-3 text-ink-secondary">{item.recommend_label}</td>
                        <td className="px-3 py-3 text-ink-muted">{item.leading_stock || "暂无"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <aside className="sticky top-[72px] grid max-h-[calc(100vh-92px)] grid-rows-[auto_minmax(220px,1fr)] gap-4 overflow-hidden self-start">
          <div className="glass-card p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="mb-1 text-xs font-medium text-ink-muted">当前选中板块</div>
                <h2 className="text-lg font-semibold text-ink">{selected?.name || "选择板块"}</h2>
                <div className="mt-1 text-sm text-ink-muted">{selected?.source || data?.source || "数据加载中"}</div>
              </div>
              {selected ? <RiskBadge level={selected.risk_level} /> : null}
            </div>

            {selected ? (
              <>
                <div className="mt-5 grid grid-cols-2 gap-3">
                  <Summary label="推荐评分" value={selected.recommend_score.toFixed(1)} compact />
                  <Summary label="风险评分" value={selected.risk_score.toFixed(1)} compact />
                  <Summary label="换手率" value={formatPct(selected.turnover_rate)} compact />
                  <Summary label="上涨家数" value={`${selected.rising_count} 家`} compact />
                </div>
                <div className="mt-5 space-y-2">
                  <div className="text-sm font-medium text-ink">判断依据</div>
                  {selected.reasons.map((reason) => (
                    <div key={reason} className="rounded-lg bg-surface-2/60 px-3 py-2 text-sm leading-6 text-ink-secondary">
                      {reason}
                    </div>
                  ))}
                </div>
              </>
            ) : null}
          </div>

          <div className="glass-card flex min-h-0 flex-col overflow-hidden p-5">
            <div className="flex shrink-0 items-start justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-ink">最新资讯</h2>
                <div className="mt-1 text-xs text-ink-muted">
                  每 60 秒自动刷新{newsFetchedAt ? ` · ${newsFetchedAt}` : ""}
                </div>
              </div>
              <button
                className="focus-ring h-8 rounded-lg border border-line bg-surface-2 px-2.5 text-xs text-ink-muted transition-colors hover:border-jade/30 hover:text-jade disabled:opacity-60"
                disabled={!selected || newsLoading}
                onClick={() => selected && loadNews(selected, true)}
                type="button"
              >
                {newsLoading ? "刷新中" : "刷新"}
              </button>
            </div>
            <div className="mt-3 min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
              {readableNews.length ? readableNews.map((item, index) => (
                <div key={index} className="rounded-lg bg-surface-2/40 px-3 py-2 text-sm leading-6 text-ink-secondary">
                  <div className="mb-1 text-xs tabular-nums text-ink-muted">{formatNewsTime(item, newsFetchedAt)}</div>
                  <div>{newsText(item)}</div>
                </div>
              )) : (
                <div className="rounded-lg bg-surface-2/40 px-3 py-3 text-sm text-ink-muted">暂无可展示资讯，已过滤异常编码内容</div>
              )}
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

function Summary({ label, value, compact = false }: { label: string; value: string; compact?: boolean }) {
  return (
    <div className={`glass-card ${compact ? "p-3" : "p-4"}`}>
      <div className="text-xs text-ink-muted">{label}</div>
      <div className="mt-1 text-lg font-semibold tabular-nums text-ink">{value}</div>
    </div>
  );
}

function RiskBadge({ level }: { level: string }) {
  const style = level === "高"
    ? "border-up/30 bg-up/10 text-up"
    : level === "中"
      ? "border-amberline/30 bg-amberline/10 text-amberline"
      : "border-jade/30 bg-jade/10 text-jade";
  return <span className={`rounded-md border px-2 py-1 text-xs font-medium ${style}`}>{level}风险</span>;
}

function ChartPanel({
  title,
  data,
  dataKey,
  unit,
  negativeTone = false
}: {
  title: string;
  data: SectorRecord[];
  dataKey: "change_pct" | "net_inflow";
  unit: string;
  negativeTone?: boolean;
}) {
  return (
    <div className="glass-card p-4">
      <h2 className="text-sm font-semibold text-ink">{title}</h2>
      <div className="mt-4 h-[340px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ left: 8, right: 34, top: 8, bottom: 8 }} barCategoryGap={8}>
            <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" horizontal={false} />
            <XAxis type="number" tick={{ fontSize: 11, fill: "var(--text-muted)" }} />
            <YAxis
              type="category"
              dataKey="name"
              width={118}
              interval={0}
              tickLine={false}
              tick={{ fontSize: 11, fill: "var(--text-muted)" }}
            />
            <Tooltip
              contentStyle={{
                background: "var(--bg-card-solid)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                color: "var(--text-primary)"
              }}
              formatter={(value) => [`${Number(value).toFixed(2)} ${unit}`, title]}
            />
            <Bar dataKey={dataKey} radius={[0, 5, 5, 0]} barSize={18}>
              {data.map((item) => (
                <Cell
                  key={item.name}
                  fill={negativeTone ? "var(--down)" : Number(item[dataKey] || 0) >= 0 ? "var(--up)" : "var(--down)"}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
