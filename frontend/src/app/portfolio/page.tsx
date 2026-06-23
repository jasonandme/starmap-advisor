"use client";

import { ChangeEvent, Ref, useEffect, useMemo, useRef, useState } from "react";
import {
  api,
  ActionSuggestion,
  FundDetail,
  formatPct,
  InvestmentPreference,
  PortfolioItem,
  PortfolioStrategy
} from "@/lib/api";
import { FundDetailPanel } from "@/components/fund/FundDetailPanel";
import { createPortal } from "react-dom";

type PresetMap = Record<string, Record<string, string | number | boolean>>;
type GoalMap = Record<string, { label: string; target_allocation: Array<{ bucket: string; target_pct: string }>; rules: string[] }>;

const riskProfiles = [
  { key: "conservative", label: "稳健" },
  { key: "balanced", label: "均衡" },
  { key: "aggressive", label: "进取" }
];

const numberFields: Array<{ key: keyof InvestmentPreference; label: string; suffix: string; min: number; max: number }> = [
  { key: "max_single_fund_pct", label: "单只上限", suffix: "%", min: 1, max: 100 },
  { key: "max_qdii_pct", label: "QDII 上限", suffix: "%", min: 0, max: 100 },
  { key: "max_drawdown_pct", label: "可承受回撤", suffix: "%", min: 1, max: 80 },
  { key: "max_theme_pct", label: "主题上限", suffix: "%", min: 0, max: 100 },
  { key: "min_cash_pct", label: "现金/低波", suffix: "%", min: 0, max: 80 }
];

const actionLabels: Record<string, string> = {
  auto_invest: "定投", buy: "加仓", sell: "减仓", switch: "转换", analyze: "分析", hold: "持有", pause_auto_invest: "暂停定投"
};

function formatMoney(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "--";
  return Number(value).toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function quoteStatusText(item: PortfolioItem) {
  if (item.estimated_daily_return_pct != null) {
    const prefix = item.estimate_completeness === "partial" ? "部分估算" : "估算";
    return item.estimate_as_of ? `${prefix} ${item.estimate_as_of.slice(11, 19) || item.estimate_as_of}` : prefix;
  }
  if (item.nav_date) return `官方 ${item.nav_date}`;
  if (item.quote_source === "snapshot" || item.quote_source === "imported_snapshot") return item.snapshot_date ? `快照 ${item.snapshot_date}` : "快照数据";
  if (item.quote_source === "error") return "净值未刷新";
  return "";
}

function estimateStatusText(item: PortfolioItem) {
  if (item.estimated_daily_return_pct != null) return item.estimate_completeness === "partial" ? "覆盖有限" : "";
  if (!item.estimate_warning && !item.quote_warning) return "";
  if (item.estimate_confidence === "不可估") return "不可估";
  return "估值有限";
}

function realtimeReturn(item: PortfolioItem) {
  return item.estimated_daily_return_pct ?? item.nav_daily_return;
}

function metricTone(value: number | null | undefined): "up" | "down" | undefined {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return undefined;
  return value >= 0 ? "up" : "down";
}

export default function PortfolioPage() {
  const [preference, setPreference] = useState<InvestmentPreference | null>(null);
  const [presets, setPresets] = useState<PresetMap>({});
  const [goals, setGoals] = useState<GoalMap>({});
  const [items, setItems] = useState<PortfolioItem[]>([]);
  const [strategy, setStrategy] = useState<PortfolioStrategy | null>(null);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [ocrText, setOcrText] = useState("");
  const [sourceType, setSourceType] = useState("holding");
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [suggestions, setSuggestions] = useState<ActionSuggestion[]>([]);
  const [actionDraft, setActionDraft] = useState({ action_type: "analyze", amount: "", schedule: "", target_fund_code: "", target_fund_name: "", reason: "" });
  const [showImport, setShowImport] = useState(false);
  const [selectedFund, setSelectedFund] = useState<FundDetail | null>(null);
  const [detailCache, setDetailCache] = useState<Record<string, FundDetail>>({});
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const actionRef = useRef<HTMLDivElement>(null);

  const holdings = useMemo(() => items.filter((i) => i.is_holding).sort((a, b) => (b.amount || 0) - (a.amount || 0)), [items]);
  const watchlistOnly = useMemo(() => items.filter((i) => i.is_watchlist && !i.is_holding).sort((a, b) => a.fund_name.localeCompare(b.fund_name, "zh-CN")), [items]);
  const totalAmount = strategy?.exposure.total_amount || 0;
  const dailyPnl = strategy?.exposure.estimated_daily_profit ?? null;
  const dailyReturnPct = strategy?.exposure.estimated_daily_return_pct ?? null;
  const snapshotPnl = strategy?.exposure.snapshot_daily_profit ?? null;
  const snapshotReturnPct = strategy?.exposure.snapshot_daily_return_pct ?? null;
  const pnlDisplayValue = dailyPnl ?? snapshotPnl;
  const returnDisplayValue = dailyReturnPct ?? snapshotReturnPct;
  const snapshotNote = strategy?.exposure.snapshot_date ?? undefined;
  const pnlLabel = dailyPnl === null && snapshotPnl !== null ? "快照日盈亏" : "当日盈亏";
  const returnLabel = dailyReturnPct === null && snapshotReturnPct !== null ? "快照涨跌" : "净值涨跌";

  async function load(refresh = false, quick = false) {
    const data = await api.portfolioOverview(refresh, quick);
    setPreference(data.preference);
    setPresets(data.presets);
    setGoals(data.goal_options);
    setItems(data.items || []);
    setStrategy(data.strategy);
  }

  useEffect(() => {
    load(false, true)
      .then(() => {
        setLoading(false);
        window.setTimeout(() => load(false, false).catch(() => undefined), 400);
      })
      .catch((e) => {
        setMessage(e instanceof Error ? e.message : "加载失败");
        setLoading(false);
      });
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") load(false, false).catch(() => undefined);
    }, 20_000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!detailOpen) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [detailOpen]);

  function positionPct(item: PortfolioItem) { return totalAmount > 0 ? (item.amount / totalAmount) * 100 : 0; }

  function applyRiskProfile(profile: string) {
    if (!preference) return;
    const preset = presets[profile] || {};
    setPreference({ ...preference, risk_profile: profile, max_single_fund_pct: Number(preset.max_single_fund_pct ?? preference.max_single_fund_pct), max_qdii_pct: Number(preset.max_qdii_pct ?? preference.max_qdii_pct), allow_sector_funds: Boolean(preset.allow_sector_funds ?? preference.allow_sector_funds), max_drawdown_pct: Number(preset.max_drawdown_pct ?? preference.max_drawdown_pct), max_theme_pct: Number(preset.max_theme_pct ?? preference.max_theme_pct), min_cash_pct: Number(preset.min_cash_pct ?? preference.min_cash_pct), rebalance_frequency: String(preset.rebalance_frequency ?? preference.rebalance_frequency) });
  }

  function setPreferenceValue(key: keyof InvestmentPreference, value: string | number | boolean) {
    if (!preference) return;
    setPreference({ ...preference, risk_profile: "custom", [key]: value } as InvestmentPreference);
  }

  async function save() {
    if (!preference) return;
    setSaving(true);
    try { const data = await api.updatePortfolioPreferences(preference); setPreference(data.preference); setMessage("偏好已保存"); await load(); }
    catch (e) { setMessage(e instanceof Error ? e.message : "保存失败"); }
    finally { setSaving(false); }
  }

  async function openAction(item: PortfolioItem, actionType = "analyze") {
    setExpandedId(item.id);
    setActionDraft({ action_type: actionType, amount: "", schedule: actionType === "auto_invest" ? "每周" : "", target_fund_code: "", target_fund_name: "", reason: "" });
    try {
      const data = await api.actionSuggestions(item.id);
      setSuggestions(data.suggestions);
      const found = data.suggestions.find((r) => r.action_type === actionType);
      if (found) setActionDraft((d) => ({ ...d, reason: found.reason }));
    } catch { setSuggestions([]); }
    setTimeout(() => actionRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }), 100);
  }

  function itemToFundDetail(item: PortfolioItem): FundDetail {
    return {
      code: item.fund_code,
      name: item.fund_name,
      fund_type: item.tags?.[0],
      latest_nav: item.estimated_nav ?? item.latest_nav ?? undefined,
      metrics: { daily_return: realtimeReturn(item) ?? null },
      nav_history: (item.estimated_nav ?? item.latest_nav) && (item.estimate_as_of || item.nav_date) ? [{ date: item.estimate_as_of || item.nav_date || "", nav: item.estimated_nav ?? item.latest_nav ?? 0, daily_return: realtimeReturn(item) ?? undefined }] : [],
      source: item.quote_source || "portfolio_snapshot",
      warning: item.quote_warning || undefined
    };
  }

  function closeFundDetail() {
    setDetailOpen(false);
    setSelectedFund(null);
    setDetailLoading(false);
  }

  async function openFundDetail(item: PortfolioItem) {
    if (!item.fund_code) {
      setMessage("这只基金还没有匹配到代码，先补齐代码后才能查看详情。");
      return;
    }
    setDetailOpen(true);
    const cached = detailCache[item.fund_code];
    setSelectedFund(cached || itemToFundDetail(item));
    setDetailLoading(!cached);
    try {
      const detail = await api.fundDetail(item.fund_code);
      setSelectedFund(detail);
      setDetailCache((cache) => ({ ...cache, [item.fund_code]: detail }));
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "基金详情加载失败");
    } finally {
      setDetailLoading(false);
    }
  }

  async function recordAction() {
    const item = items.find((i) => i.id === expandedId);
    if (!item) return;
    setSaving(true);
    try {
      await api.createPortfolioAction(item.id, { action_type: actionDraft.action_type, amount: actionDraft.amount ? Number(actionDraft.amount) : null, schedule: actionDraft.schedule, target_fund_code: actionDraft.target_fund_code, target_fund_name: actionDraft.target_fund_name, reason: actionDraft.reason });
      setMessage(`${item.fund_name} 的${actionLabels[actionDraft.action_type] || "操作"}已记录。`);
      setExpandedId(null);
    } catch (e) { setMessage(e instanceof Error ? e.message : "记录失败"); }
    finally { setSaving(false); }
  }

  async function upload() {
    if (!uploadFile && !ocrText.trim()) { setMessage("上传截图或粘贴 OCR 文本。"); return; }
    setSaving(true);
    try {
      if (uploadFile) {
        const fd = new FormData(); fd.append("file", uploadFile); fd.append("source_type", sourceType);
        if (ocrText.trim()) fd.append("ocr_text", ocrText.trim());
        const data = await api.importPortfolioImage(fd);
        setMessage(`${data.message} 新增 ${data.created} 条，更新 ${data.updated} 条。`);
      } else {
        const data = await api.importPortfolioText(ocrText.trim(), sourceType);
        setMessage(`${data.message}，新增 ${data.created} 条，更新 ${data.updated} 条。`);
      }
      setUploadFile(null); setOcrText(""); setShowImport(false);
      await api.resolvePortfolioCodes().catch(() => {});
      await load();
    } catch (e) { setMessage(e instanceof Error ? e.message : "导入失败"); }
    finally { setSaving(false); }
  }

  if (loading) return <div className="flex items-center justify-center py-20 text-sm text-ink-muted">加载持仓数据...</div>;
  if (!preference || !strategy) return <div className="glass-card px-4 py-3 text-sm text-ink-secondary">持仓数据暂不可用。</div>;

  const alerts = strategy.alerts || [];

  return (
    <div className="space-y-5 animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-ink">我的持仓</h1>
          <p className="mt-1 text-sm text-ink-muted">持仓概览、当日盈亏、操作记录与投资约束。</p>
        </div>
        <div className="flex gap-2">
          <button className="btn-secondary h-9 px-3 text-sm" onClick={() => setShowImport(!showImport)}>
            {showImport ? "收起导入" : "导入持仓"}
          </button>
        </div>
      </div>

      {message ? <div className="rounded-xl border border-jade/30 bg-jade/8 px-4 py-3 text-sm text-jade">{message}</div> : null}

      {/* Metrics */}
      <section className="grid grid-cols-6 gap-3">
        <MetricBox label="持仓市值" value={formatMoney(totalAmount)} />
        <MetricBox
          label={pnlLabel}
          value={pnlDisplayValue === null ? "暂无" : `${pnlDisplayValue >= 0 ? "+" : ""}${pnlDisplayValue.toFixed(2)}`}
          tone={metricTone(pnlDisplayValue)}
          note={dailyPnl === null && snapshotPnl !== null ? snapshotNote : undefined}
        />
        <MetricBox
          label={returnLabel}
          value={returnDisplayValue === null ? "暂无" : formatPct(returnDisplayValue)}
          tone={metricTone(returnDisplayValue)}
          note={dailyReturnPct === null && snapshotReturnPct !== null ? snapshotNote : undefined}
        />
        <MetricBox label="QDII 占比" value={formatPct(strategy.exposure.qdii_pct)} />
        <MetricBox label="主题占比" value={formatPct(strategy.exposure.theme_pct)} />
        <MetricBox label="持有 / 观察" value={`${holdings.length} / ${watchlistOnly.length}`} />
      </section>

      {/* Import panel - collapsible */}
      {showImport && (
        <section className="glass-card p-4 animate-fade-in">
          <div className="text-sm font-semibold text-ink mb-3">截图 / OCR 导入</div>
          <div className="grid grid-cols-[1fr_1fr_auto] gap-2 items-end">
            <div>
              <div className="text-xs text-ink-muted mb-1">来源类型</div>
              <select className="input-styled h-9 w-full px-2 text-sm" value={sourceType} onChange={(e) => setSourceType(e.target.value)}>
                <option value="holding">持仓</option>
                <option value="watchlist">自选</option>
              </select>
            </div>
            <div>
              <div className="text-xs text-ink-muted mb-1">截图文件</div>
              <input className="block h-9 w-full text-xs text-ink-secondary file:mr-2 file:h-9 file:rounded-lg file:border-0 file:bg-surface-2 file:px-3 file:text-sm file:text-ink-secondary" type="file" accept="image/*" onChange={(e: ChangeEvent<HTMLInputElement>) => setUploadFile(e.target.files?.[0] || null)} />
            </div>
            <button className="btn-primary h-9 px-4 text-sm" onClick={upload} disabled={saving}>导入</button>
          </div>
          <textarea className="input-styled mt-3 h-16 w-full resize-none px-3 py-2 text-sm" placeholder="可选：粘贴 OCR 文本" value={ocrText} onChange={(e) => setOcrText(e.target.value)} />
          <div className="mt-2 text-xs text-ink-muted">导入后会自动尝试匹配基金代码。</div>
        </section>
      )}

      {/* Main grid: Holdings + Preferences */}
      <div className="grid grid-cols-[minmax(0,1fr)_320px] gap-5">
        {/* Holdings Table */}
        <section className="glass-card min-w-0 overflow-hidden">
          <div className="flex items-center justify-between border-b border-line px-4 py-3">
            <div className="text-sm font-semibold text-ink">当前持仓</div>
            <div className="text-xs text-ink-muted">点击操作按钮展开面板</div>
          </div>
          <div className="overflow-x-auto">
          <table className="min-w-[1360px] w-full table-fixed text-sm">
            <thead className="bg-surface-2/50 text-left text-xs text-ink-muted">
              <tr>
                <th className="w-[22%] px-4 py-3 font-medium">基金</th>
                <th className="w-[9%] px-4 py-3 text-right font-medium">金额</th>
                <th className="w-[7%] px-4 py-3 text-right font-medium">占比</th>
                <th className="w-[9%] px-4 py-3 text-right font-medium">净值涨跌</th>
                <th className="w-[9%] px-4 py-3 text-right font-medium">{pnlLabel}</th>
                <th className="w-[9%] px-4 py-3 text-right font-medium">持有收益</th>
                <th className="w-[14%] px-4 py-3 font-medium">标签</th>
                <th className="sticky right-0 z-20 w-[21%] bg-surface-2 px-4 py-3 text-right font-medium shadow-[-8px_0_14px_rgba(15,23,42,0.04)]">操作</th>
              </tr>
            </thead>
            <tbody>
              {holdings.map((item, idx) => (
                <HoldingRow key={item.id} item={item} idx={idx} positionPct={positionPct(item)} isExpanded={expandedId === item.id} onAction={(action) => openAction(item, action)} onOpenDetail={() => openFundDetail(item)} actionRef={expandedId === item.id ? actionRef : undefined} actionDraft={actionDraft} setActionDraft={setActionDraft} suggestions={suggestions} onRecord={recordAction} onClose={() => setExpandedId(null)} saving={saving} />
              ))}
              {holdings.length === 0 && (
                <tr><td colSpan={8} className="px-4 py-12 text-center text-sm text-ink-muted">暂无持仓，点击"导入持仓"添加。</td></tr>
              )}
            </tbody>
          </table>
          </div>
        </section>

        {/* Right column: Preferences + Alerts */}
        <div className="space-y-4">
          <section className="glass-card p-4 space-y-3">
            <div>
              <div className="text-sm font-semibold text-ink">投资约束</div>
              <div className="mt-1 text-xs text-ink-muted">调整后影响推荐和风险提示。</div>
            </div>
            <div className="grid grid-cols-3 rounded-lg border border-line bg-surface-2 p-1">
              {riskProfiles.map((p) => (
                <button key={p.key} className={`focus-ring h-8 rounded-md text-sm transition-all ${preference.risk_profile === p.key ? "bg-jade/15 font-medium text-jade shadow-inner-glow" : "text-ink-muted hover:text-ink"}`} onClick={() => applyRiskProfile(p.key)}>
                  {p.label}
                </button>
              ))}
            </div>
            <label className="block">
              <span className="mb-1 block text-xs text-ink-muted">策略目标</span>
              <select className="input-styled h-9 w-full px-2 text-sm" value={preference.strategy_goal} onChange={(e) => setPreferenceValue("strategy_goal", e.target.value)}>
                {Object.entries(goals).map(([k, g]) => <option key={k} value={k}>{g.label}</option>)}
              </select>
            </label>
            <div className="grid grid-cols-2 gap-2">
              {numberFields.map((f) => (
                <label key={f.key} className="block">
                  <span className="mb-1 block text-xs text-ink-muted">{f.label}</span>
                  <div className="flex h-9 overflow-hidden rounded-lg border border-line bg-surface-2">
                    <input className="min-w-0 flex-1 bg-transparent px-2 text-sm text-ink outline-none" type="number" min={f.min} max={f.max} step="1" value={Number(preference[f.key] ?? 0)} onChange={(e) => setPreferenceValue(f.key, Number(e.target.value))} />
                    <span className="flex w-8 items-center justify-center border-l border-line text-xs text-ink-muted">{f.suffix}</span>
                  </div>
                </label>
              ))}
            </div>
            <label className="flex items-center justify-between rounded-lg border border-line bg-surface-2 px-3 py-2 text-sm">
              <span className="text-ink-secondary">允许行业主题基金</span>
              <input className="h-4 w-4 accent-jade" type="checkbox" checked={preference.allow_sector_funds} onChange={(e) => setPreferenceValue("allow_sector_funds", e.target.checked)} />
            </label>
            <button className="btn-primary h-9 w-full text-sm" onClick={save} disabled={saving}>保存约束</button>
          </section>

          {/* Alerts */}
          {alerts.length > 0 && (
            <section className="glass-card p-4">
              <div className="mb-3 text-sm font-semibold text-ink">风险提示</div>
              <div className="space-y-2">
                {alerts.map((a, i) => (
                  <div key={`${a.title}-${i}`} className={`rounded-lg border px-3 py-2 text-sm ${a.level === "high" ? "border-up/30 bg-up/8 text-up" : a.level === "medium" ? "border-amberline/30 bg-amberline/8 text-amberline" : "border-line bg-surface-2/60 text-ink-secondary"}`}>
                    <div className="font-medium">{a.title}</div>
                    <div className="mt-1 text-xs leading-5 opacity-80">{a.detail}</div>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>
      </div>

      {/* Watchlist */}
      {watchlistOnly.length > 0 && (
        <section className="glass-card overflow-hidden animate-fade-in-delay">
          <div className="flex items-center justify-between border-b border-line px-4 py-3">
            <div className="text-sm font-semibold text-ink">观察池</div>
            <div className="text-xs text-ink-muted">{watchlistOnly.length} 只未持有候选</div>
          </div>
          <div className="overflow-x-auto">
          <table className="min-w-[980px] w-full table-fixed text-sm">
            <thead className="bg-surface-2/50 text-left text-xs text-ink-muted">
              <tr>
                <th className="w-[32%] px-4 py-3 font-medium">基金</th>
                <th className="w-[11%] px-4 py-3 text-right font-medium">当日涨跌</th>
                <th className="w-[11%] px-4 py-3 text-right font-medium">最新净值</th>
                <th className="w-[12%] px-4 py-3 font-medium">净值日期</th>
                <th className="px-4 py-3 font-medium">标签</th>
                <th className="sticky right-0 z-20 w-64 bg-surface-2 px-4 py-3 text-right font-medium shadow-[-8px_0_14px_rgba(15,23,42,0.04)]">操作</th>
              </tr>
            </thead>
            <tbody>
              {watchlistOnly.map((item, idx) => (
                <tr key={item.id} className={`border-b border-line/50 transition-colors hover:bg-surface-2/60 ${idx % 2 ? "bg-surface-1/30" : ""}`}>
                  <td className="px-4 py-3">
                    <button
                      className="focus-ring text-left font-medium text-ink transition-colors hover:text-jade hover:underline"
                      onClick={() => openFundDetail(item)}
                      title="查看基金详情"
                      type="button"
                    >
                      {item.fund_name}
                    </button>
                    <div className="mt-0.5 font-mono text-xs text-ink-muted">{item.fund_code || "代码待确认"}</div>
                  </td>
                  <td className={`px-4 py-3 text-right tabular-nums font-medium ${realtimeReturn(item) == null ? "text-ink-muted" : Number(realtimeReturn(item)) >= 0 ? "price-up" : "price-down"}`}>
                    {formatPct(realtimeReturn(item))}
                    <div className="mt-0.5 text-[11px] font-normal text-ink-muted">{quoteStatusText(item)}</div>
                    {estimateStatusText(item) ? <div className="mt-0.5 text-[11px] font-normal text-amberline" title={item.estimate_warning || item.quote_warning || ""}>{estimateStatusText(item)}</div> : null}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-ink-secondary">
                    {(item.estimated_nav ?? item.latest_nav) == null ? "暂无" : Number(item.estimated_nav ?? item.latest_nav).toFixed(4)}
                  </td>
                  <td className="px-4 py-3 text-xs text-ink-muted">
                    {item.nav_date || item.snapshot_date || "暂无"}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {(item.tags || []).map((t) => <span key={t} className="badge">{t}</span>)}
                    </div>
                  </td>
                  <td className="sticky right-0 z-10 bg-surface-1 px-4 py-3 text-right shadow-[-8px_0_14px_rgba(15,23,42,0.04)]">
                    <div className="ml-auto flex min-w-[232px] justify-end gap-1.5">
                      {["analyze", "buy", "sell", "auto_invest"].map((a) => (
                        <button key={a} className="focus-ring h-8 min-w-[52px] whitespace-nowrap rounded-lg border border-line bg-surface-2 px-2.5 text-xs leading-none text-ink-muted transition-all hover:border-jade/30 hover:text-jade" onClick={() => openAction(item, a)} title={actionLabels[a]}>
                          {actionLabels[a]}
                        </button>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </section>
      )}

      {detailOpen && createPortal((
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-transparent px-4 py-8"
          onClick={closeFundDetail}
          role="presentation"
        >
          <section
            className="flex h-[min(860px,calc(100dvh-64px))] w-[min(1120px,calc(100vw-32px))] flex-col overflow-hidden rounded-card border border-line bg-surface-1 shadow-2xl"
            onClick={(event) => event.stopPropagation()}
            aria-modal="true"
            role="dialog"
          >
            <div className="sticky top-0 z-10 flex items-center justify-between border-b border-line bg-surface-1/95 px-5 py-3">
              <div>
                <div className="text-sm font-semibold text-ink">基金详情</div>
                <div className="text-xs text-ink-muted">独立窗口滚动，不影响持仓总览。</div>
              </div>
              <button
                className="focus-ring rounded-lg border border-line bg-surface-1 px-3 py-2 text-sm text-ink-secondary shadow-quiet transition-colors hover:border-jade/30 hover:text-ink"
                onClick={closeFundDetail}
                type="button"
              >
                关闭
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-5 py-4 pb-14">
            {detailLoading ? (
              <div className="mb-3 rounded-lg border border-line bg-surface-2/60 px-3 py-2 text-xs text-ink-muted">
                正在补齐净值历史和技术指标，已先显示当前列表快照。
              </div>
            ) : null}
            {detailLoading && !selectedFund ? (
              <div className="glass-card flex min-h-[360px] items-center justify-center text-sm text-ink-muted">
                正在加载基金详情...
              </div>
            ) : (
              <FundDetailPanel fund={selectedFund} />
            )}
            </div>
          </section>
        </div>
      ), document.body)}
    </div>
  );
}

/* ─── Sub-components ─── */

function MetricBox({ label, value, tone, note }: { label: string; value: string; tone?: "up" | "down"; note?: string }) {
  return (
    <div className="glass-card p-3">
      <div className="text-xs text-ink-muted">{label}</div>
      <div className={`mt-1 text-xl font-semibold tabular-nums ${tone === "up" ? "price-up" : tone === "down" ? "price-down" : "text-ink"}`}>{value}</div>
      {note ? <div className="mt-1 text-[11px] text-ink-muted">{note}</div> : null}
    </div>
  );
}

function HoldingRow({ item, idx, positionPct, isExpanded, onAction, onOpenDetail, actionRef, actionDraft, setActionDraft, suggestions, onRecord, onClose, saving }: {
  item: PortfolioItem; idx: number; positionPct: number; isExpanded: boolean;
  onAction: (action: string) => void; onOpenDetail: () => void; actionRef?: Ref<HTMLDivElement>;
  actionDraft: any; setActionDraft: (d: any) => void; suggestions: ActionSuggestion[];
  onRecord: () => void; onClose: () => void; saving: boolean;
}) {
  const returnPct = item.holding_return_pct;
  const navDailyReturn = realtimeReturn(item);
  const estimatedDailyProfit = item.estimated_daily_profit ?? item.snapshot_daily_profit ?? null;
  const dailyProfitLabel = item.estimated_daily_return_pct != null ? "估算" : item.snapshot_daily_profit != null ? quoteStatusText(item) : quoteStatusText(item);
  const quoteStatus = quoteStatusText(item);
  return (
    <>
      <tr className={`border-b border-line/50 transition-colors hover:bg-surface-2/60 ${idx % 2 ? "bg-surface-1/30" : ""} ${isExpanded ? "bg-jade/5" : ""}`}>
        <td className="px-4 py-3">
          <button
            className="focus-ring text-left font-medium text-ink transition-colors hover:text-jade hover:underline"
            onClick={onOpenDetail}
            title="查看基金详情"
            type="button"
          >
            {item.fund_name}
          </button>
          <div className="mt-0.5 font-mono text-xs text-ink-muted">{item.fund_code || "代码待确认"}</div>
        </td>
        <td className="px-4 py-3 text-right tabular-nums text-ink-secondary">{formatMoney(item.amount)}</td>
        <td className="px-4 py-3 text-right">
          <div className="flex items-center justify-end gap-2">
            <span className="tabular-nums text-ink-secondary">{formatPct(positionPct)}</span>
            <div className="progress-bar w-12"><div className="progress-bar-fill" style={{ width: `${Math.min(positionPct, 100)}%` }} /></div>
          </div>
        </td>
        <td className={`px-4 py-3 text-right tabular-nums font-medium ${navDailyReturn == null ? "text-ink-muted" : navDailyReturn >= 0 ? "price-up" : "price-down"}`}>
          <div>{formatPct(navDailyReturn)}</div>
          {quoteStatus ? <div className="mt-0.5 text-[11px] font-normal text-ink-muted">{quoteStatus}</div> : null}
          {estimateStatusText(item) ? <div className="mt-0.5 text-[11px] font-normal text-amberline" title={item.estimate_warning || item.quote_warning || ""}>{estimateStatusText(item)}</div> : null}
        </td>
        <td className={`px-4 py-3 text-right tabular-nums font-medium ${estimatedDailyProfit == null ? "text-ink-muted" : estimatedDailyProfit >= 0 ? "price-up" : "price-down"}`}>
          <div>{estimatedDailyProfit == null ? "暂无" : `${estimatedDailyProfit >= 0 ? "+" : ""}${estimatedDailyProfit.toFixed(2)}`}</div>
          {dailyProfitLabel ? <div className="mt-0.5 text-[11px] font-normal text-ink-muted">{dailyProfitLabel}</div> : null}
        </td>
        <td className={`px-4 py-3 text-right tabular-nums font-medium ${returnPct == null ? "text-ink-muted" : returnPct >= 0 ? "price-up" : "price-down"}`}>
          {returnPct == null ? "暂无" : formatPct(returnPct)}
        </td>
        <td className="px-4 py-3">
          <div className="flex flex-wrap gap-1">
            {(item.tags || []).map((t) => <span key={t} className="badge">{t}</span>)}
          </div>
        </td>
        <td className="sticky right-0 z-10 bg-surface-1 px-4 py-3 text-right shadow-[-8px_0_14px_rgba(15,23,42,0.04)]">
          <div className="ml-auto flex min-w-[232px] justify-end gap-1.5">
            {["analyze", "buy", "sell", "auto_invest"].map((a) => (
              <button key={a} className={`focus-ring h-8 min-w-[52px] whitespace-nowrap rounded-lg border px-2.5 text-xs leading-none transition-all ${isExpanded && actionDraft.action_type === a ? "border-jade/30 bg-jade/15 text-jade" : "border-line bg-surface-2 text-ink-muted hover:border-jade/30 hover:text-jade"}`} onClick={() => onAction(a)} title={actionLabels[a]}>
                {actionLabels[a]}
              </button>
            ))}
          </div>
        </td>
      </tr>
      {isExpanded && (
        <tr>
          <td colSpan={8} className="px-4 py-3 bg-surface-2/30 border-b border-line">
            <div ref={actionRef} className="animate-fade-in grid grid-cols-[1fr_1fr_auto] gap-3 items-end">
              <div className="grid grid-cols-2 gap-2">
                <input className="input-styled h-9 px-3 text-sm" placeholder="金额（可选）" value={actionDraft.amount} onChange={(e) => setActionDraft({ ...actionDraft, amount: e.target.value })} />
                <input className="input-styled h-9 px-3 text-sm" placeholder="周期（可选）" value={actionDraft.schedule} onChange={(e) => setActionDraft({ ...actionDraft, schedule: e.target.value })} />
              </div>
              <textarea className="input-styled h-9 min-h-[36px] resize-none px-3 py-2 text-sm" placeholder="理由（可选）" value={actionDraft.reason} onChange={(e) => setActionDraft({ ...actionDraft, reason: e.target.value })} />
              <div className="flex gap-2">
                <button className="btn-primary h-9 px-4 text-sm" onClick={onRecord} disabled={saving}>记录</button>
                <button className="btn-secondary h-9 px-3 text-sm" onClick={onClose}>取消</button>
              </div>
            </div>
            {suggestions.length > 0 && (
              <div className="mt-2 flex gap-2">
                {suggestions.slice(0, 2).map((s) => (
                  <button key={s.action_type} className="rounded-lg bg-surface-2/60 px-3 py-1.5 text-left text-xs text-ink-muted transition-colors hover:text-jade" onClick={() => setActionDraft({ ...actionDraft, action_type: s.action_type, reason: s.reason })}>
                    {s.label}：{s.reason}
                  </button>
                ))}
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  );
}
