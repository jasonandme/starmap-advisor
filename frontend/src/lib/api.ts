export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export type FundRecord = {
  code: string;
  name: string;
  fund_type?: string;
  unit_nav?: number;
  nav_date?: string;
  daily_return?: number;
  week_return?: number;
  month_return?: number;
  three_month_return?: number;
  six_month_return?: number;
  year_return?: number;
  this_year_return?: number;
  score?: number;
  risk_level?: string;
  estimated_return_pct?: number | null;
  estimated_nav?: number | null;
  estimate_completeness?: "full" | "partial" | "unavailable" | string | null;
  estimate_as_of?: string | null;
  estimate_confidence?: string | null;
  estimate_warning?: string | null;
  source?: string;
  warning?: string;
};

export type FundDetail = {
  code: string;
  name: string;
  fund_type?: string;
  latest_nav?: number;
  metrics: Record<string, number | null>;
  nav_history: Array<{ date: string; nav: number; daily_return?: number }>;
  technical?: Record<string, any>;
  source?: string;
  warning?: string;
};

export type FundRealtimeContributor = {
  stock_code?: string;
  stock_name?: string;
  bond_code?: string;
  bond_name?: string;
  hold_ratio?: number | null;
  change_pct?: number | null;
  contribution_pct?: number | null;
  latest_price?: number | null;
  quote_source?: string | null;
};

export type StockRealtimeQuote = {
  code: string;
  name?: string | null;
  latest_price?: number | null;
  change_pct?: number | null;
  turnover_rate?: number | null;
  amount?: number | null;
  source?: string | null;
  [key: string]: unknown;
};

export type FundRealtimeEstimate = {
  code: string;
  estimated_return_pct?: number | null;
  estimated_nav?: number | null;
  base_nav?: number | null;
  official_daily_return?: number | null;
  nav_date?: string | null;
  as_of?: string;
  source?: string;
  method?: string;
  estimate_completeness?: "full" | "partial" | "unavailable" | string | null;
  asset_allocation?: {
    stock_pct?: number | null;
    bond_pct?: number | null;
    bank_cash_pct?: number | null;
    other_pct?: number | null;
    report_date?: string | null;
    source?: string | null;
    items?: Array<Record<string, unknown>>;
  };
  coverage?: {
    stock_disclosed_ratio?: number | null;
    stock_quote_covered_ratio?: number | null;
    uncovered_stock_ratio?: number | null;
    bond_disclosed_ratio?: number | null;
    bond_quote_covered_ratio?: number | null;
    quote_coverage_ratio?: number | null;
    asset_coverage_ratio?: number | null;
    confidence?: string;
  };
  contribution?: {
    stock_direct_pct?: number | null;
    stock_estimated_pct?: number | null;
    bond_direct_pct?: number | null;
    bond_estimated_pct?: number | null;
    bank_cash_pct?: number | null;
    other_pct?: number | null;
  };
  stock_contributors?: FundRealtimeContributor[];
  bond_contributors?: FundRealtimeContributor[];
  warnings?: string[];
  data_quality?: Record<string, unknown>;
};

export type SectorRecord = {
  name: string;
  code?: string;
  latest_price?: number | null;
  change_amount?: number | null;
  change_pct?: number | null;
  market_value?: number | null;
  turnover_rate?: number | null;
  rising_count: number;
  falling_count: number;
  leading_stock?: string;
  leading_stock_change_pct?: number | null;
  inflow?: number | null;
  outflow?: number | null;
  net_inflow?: number | null;
  company_count?: number;
  risk_score: number;
  risk_level: string;
  recommend_score: number;
  recommend_label: string;
  reasons: string[];
  source?: string;
};

export type SectorOverview = {
  as_of: string;
  count: number;
  sectors: SectorRecord[];
  recommended: SectorRecord[];
  risk_alerts: SectorRecord[];
  flow_summary: {
    total_inflow: number;
    total_outflow: number;
    total_net_inflow: number;
    positive_count: number;
    negative_count: number;
  };
  source: string;
  data_quality?: {
    industry_quote_status?: string;
    industry_quote_source?: string;
    industry_flow_status?: string;
    industry_quote_error?: string | null;
    note?: string;
  };
};

export type LlmOption = {
  id: string;
  name: string;
  model: string;
  reasoner_model?: string;
  configured: boolean;
};

export type InvestmentPreference = {
  id?: number;
  risk_profile: string;
  strategy_goal: string;
  max_single_fund_pct: number;
  max_qdii_pct: number;
  allow_sector_funds: boolean;
  max_drawdown_pct: number;
  max_theme_pct: number;
  min_cash_pct: number;
  rebalance_frequency: string;
  notes?: string;
  updated_at?: string;
};

export type PortfolioItem = {
  id: number;
  fund_code: string;
  fund_name: string;
  source: string;
  amount: number;
  yesterday_profit?: number | null;
  holding_profit?: number | null;
  holding_return_pct?: number | null;
  latest_nav?: number | null;
  previous_nav?: number | null;
  nav_date?: string | null;
  nav_daily_return?: number | null;
  estimated_daily_return_pct?: number | null;
  estimated_nav?: number | null;
  estimated_daily_profit?: number | null;
  estimate_as_of?: string | null;
  estimate_confidence?: string | null;
  estimate_source?: string | null;
  estimate_completeness?: "full" | "partial" | "unavailable" | string | null;
  estimate_warning?: string | null;
  snapshot_daily_profit?: number | null;
  snapshot_date?: string | null;
  quote_source?: string | null;
  quote_warning?: string | null;
  tags: string[];
  confidence: string;
  is_holding: boolean;
  is_watchlist: boolean;
  notes?: string;
};

function refreshParam(refresh?: boolean) {
  return refresh ? "&refresh=true" : "";
}

function refreshQuery(refresh?: boolean) {
  return refresh ? "?refresh=true" : "";
}

export type PortfolioAction = {
  id: number;
  item_id?: number | null;
  fund_code: string;
  fund_name: string;
  action_type: string;
  amount?: number | null;
  target_fund_code?: string;
  target_fund_name?: string;
  schedule?: string;
  status: string;
  reason?: string;
  created_at: string;
};

export type ActionSuggestion = {
  action_type: string;
  label: string;
  priority: string;
  reason: string;
};

export type PortfolioStrategy = {
  preference: InvestmentPreference;
  exposure: {
    total_amount: number;
    estimated_daily_profit?: number | null;
    estimated_daily_return_pct?: number | null;
    snapshot_daily_profit?: number | null;
    snapshot_daily_return_pct?: number | null;
    snapshot_covered_count?: number;
    snapshot_date?: string | null;
    quote_covered_count?: number;
    quote_latest_date?: string | null;
    quote_oldest_date?: string | null;
    quote_date_counts?: Record<string, number>;
    quote_today?: string;
    quote_is_today?: boolean;
    holding_count: number;
    watchlist_count: number;
    qdii_amount: number;
    qdii_pct: number;
    theme_amount: number;
    theme_pct: number;
    pension_amount: number;
    pension_pct: number;
    largest_position?: {
      fund_name: string;
      position_pct: number;
      amount: number;
      tags: string[];
    } | null;
    top_positions: Array<{
      id: number;
      fund_code: string;
      fund_name: string;
      amount: number;
      position_pct: number;
      holding_return_pct?: number | null;
      nav_daily_return?: number | null;
      estimated_daily_profit?: number | null;
      snapshot_daily_profit?: number | null;
      snapshot_date?: string | null;
      tags: string[];
    }>;
    constraints: Record<string, number | boolean>;
  };
  alerts: Array<{ level: string; title: string; detail: string; action: string }>;
  current_strategy: {
    profile_label: string;
    profile_description: string;
    goal_label: string;
    target_allocation: Array<{ bucket: string; target_pct: string }>;
    rules: string[];
    actions: string[];
  };
  strategy_options: Record<
    string,
    { label: string; target_allocation: Array<{ bucket: string; target_pct: string }>; rules: string[] }
  >;
  disclaimer: string;
};

type CacheEntry<T = unknown> = {
  expiresAt: number;
  data?: T;
  promise?: Promise<T>;
};

const responseCache = new Map<string, CacheEntry>();

function isLiveRefreshPath(path: string) {
  return /[?&]refresh=true\b/.test(path);
}

function cacheKey(path: string, init?: RequestInit) {
  const method = (init?.method || "GET").toUpperCase();
  return `${method}:${path}`;
}

function cacheTtl(path: string, init?: RequestInit) {
  const method = (init?.method || "GET").toUpperCase();
  if (method !== "GET" || isLiveRefreshPath(path)) return 0;
  if (path.startsWith("/api/portfolio/overview")) return 20_000;
  if (path.startsWith("/api/portfolio/items")) return 20_000;
  if (path.startsWith("/api/portfolio/strategy")) return 20_000;
  if (path.startsWith("/api/portfolio/preferences")) return 5 * 60_000;
  if (path.startsWith("/api/sectors/overview")) return 60_000;
  if (path.startsWith("/api/sectors/")) return 60_000;
  if (path.startsWith("/api/funds/realtime-estimates")) return 20_000;
  if (path.startsWith("/api/funds/recommend")) return 5 * 60_000;
  if (path.startsWith("/api/funds/rank")) return 5 * 60_000;
  if (path.startsWith("/api/funds/search")) return 60_000;
  if (/^\/api\/funds\/[^/?]+(\?.*)?$/.test(path)) return 10 * 60_000;
  if (path.startsWith("/api/analysis/history")) return 60_000;
  if (path.startsWith("/api/system/llm-options")) return 5 * 60_000;
  if (path.startsWith("/api/health")) return 10_000;
  return 0;
}

export function clearApiCache(prefix?: string) {
  if (!prefix) {
    responseCache.clear();
    return;
  }
  for (const key of responseCache.keys()) {
    if (key.includes(prefix)) responseCache.delete(key);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const ttl = cacheTtl(path, init);
  const key = cacheKey(path, init);
  const now = Date.now();
  if (ttl > 0) {
    const cached = responseCache.get(key) as CacheEntry<T> | undefined;
    if (cached?.data !== undefined && cached.expiresAt > now) return cached.data;
    if (cached?.promise) return cached.promise;
  }

  const isFormData = init?.body instanceof FormData;
  const promise = fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(init?.headers || {})
    },
    cache: "no-store"
  }).then(async (response) => {
    if (!response.ok) {
      const text = await response.text();
      let message = text || `HTTP ${response.status}`;
      try {
        const data = JSON.parse(text);
        const next = data.detail || data.message || message;
        message = formatApiError(next);
      } catch {
        // Keep the raw response text when it is not JSON.
      }
      throw new Error(message);
    }
    return response.json() as Promise<T>;
  });

  if (ttl > 0) responseCache.set(key, { expiresAt: now + ttl, promise });
  try {
    const data = await promise;
    if (ttl > 0) responseCache.set(key, { expiresAt: Date.now() + ttl, data });
    const method = (init?.method || "GET").toUpperCase();
    if (method !== "GET" && !path.startsWith("/api/funds/compare")) clearApiCache();
    return data;
  } catch (error) {
    if (ttl > 0) responseCache.delete(key);
    throw error;
  }
}

function formatApiError(value: unknown) {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) {
    return value
      .map((item) => {
        if (!item || typeof item !== "object") return String(item);
        const record = item as Record<string, unknown>;
        const field = Array.isArray(record.loc) ? record.loc.slice(1).join(".") : "参数";
        const msg = String(record.msg || "校验失败");
        const limit = (record.ctx as Record<string, unknown> | undefined)?.le;
        if (record.type === "less_than_equal" && limit != null) return `${field} 不能超过 ${limit}`;
        return `${field}：${msg}`;
      })
      .join("；");
  }
  if (value && typeof value === "object") return JSON.stringify(value);
  return String(value || "请求失败");
}

export const api = {
  health: () => request<{ status: string; app: string; version: string }>("/api/health"),
  llmOptions: () => request<{ active: string; options: LlmOption[] }>("/api/system/llm-options"),
  recommend: (fundType = "QDII", risk = "balanced", topN = 5, refresh = false) =>
    request<{ funds: FundRecord[]; warning?: string; source?: string }>(
      `/api/funds/recommend?fund_type=${encodeURIComponent(fundType)}&risk=${risk}&top_n=${topN}${refreshParam(refresh)}`
    ),
  rank: (fundType = "全部", topN = 30, refresh = false) =>
    request<{ funds: FundRecord[]; warning?: string; source?: string }>(
      `/api/funds/rank?fund_type=${encodeURIComponent(fundType)}&top_n=${topN}${refreshParam(refresh)}`
    ),
  searchFunds: (query: string, refresh = false) =>
    request<{ funds: FundRecord[]; warning?: string }>(
      `/api/funds/search?q=${encodeURIComponent(query)}${refreshParam(refresh)}`
    ),
  fundDetail: (code: string, refresh = false) => request<FundDetail>(`/api/funds/${code}${refreshQuery(refresh)}`),
  fundRealtimeEstimate: (code: string, refresh = false) =>
    request<FundRealtimeEstimate>(`/api/funds/${code}/realtime-estimate${refreshQuery(refresh)}`),
  stockQuote: (code: string) => request<StockRealtimeQuote>(`/api/stocks/${code}/quote`),
  sectorOverview: (limit = 80, refresh = false) => request<SectorOverview>(`/api/sectors/overview?limit=${limit}${refreshParam(refresh)}`),
  sectorNews: (name: string, limit = 10, refresh = false) =>
    request<{ name: string; news: Array<Record<string, unknown>>; matched: boolean; warning?: string | null }>(
      `/api/sectors/${encodeURIComponent(name)}/news?limit=${limit}${refreshParam(refresh)}`
    ),
  compare: (codes: string[], refresh = false) =>
    request<{ funds: FundDetail[] }>(`/api/funds/compare${refreshQuery(refresh)}`, {
      method: "POST",
      body: JSON.stringify({ codes })
    }),
  watchlist: () =>
    request<{ items: Array<{ id: number; fund_code: string; fund_name: string; note?: string }> }>(
      "/api/watchlist"
    ),
  addWatch: (fund_code: string, fund_name = "", note = "") =>
    request<{ message: string }>("/api/watchlist", {
      method: "POST",
      body: JSON.stringify({ fund_code, fund_name, note })
    }),
  removeWatch: (fundCode: string) =>
    request<{ message: string }>(`/api/watchlist/${fundCode}`, { method: "DELETE" }),
  history: () =>
    request<{ items: Array<{ id: number; title: string; query: string; response: string; created_at: string }> }>(
      "/api/analysis/history"
    ),
  portfolioOverview: (refresh = false, quick = false) =>
    request<{
      preference: InvestmentPreference;
      presets: Record<string, Record<string, string | number | boolean>>;
      goal_options: Record<
        string,
        { label: string; target_allocation: Array<{ bucket: string; target_pct: string }>; rules: string[] }
      >;
      count: number;
      items: PortfolioItem[];
      strategy: PortfolioStrategy;
    }>(`/api/portfolio/overview?quick=${quick ? "true" : "false"}${refresh ? "&refresh=true" : ""}`),
  portfolioPreferences: () =>
    request<{
      preference: InvestmentPreference;
      presets: Record<string, Record<string, string | number | boolean>>;
      goal_options: Record<
        string,
        { label: string; target_allocation: Array<{ bucket: string; target_pct: string }>; rules: string[] }
      >;
    }>("/api/portfolio/preferences"),
  updatePortfolioPreferences: (preference: Partial<InvestmentPreference> & { apply_profile_defaults?: boolean }) =>
    request<{ message: string; preference: InvestmentPreference }>("/api/portfolio/preferences", {
      method: "PUT",
      body: JSON.stringify(preference)
    }),
  portfolioItems: (refresh = false) => request<{ count: number; items: PortfolioItem[] }>(`/api/portfolio/items${refreshQuery(refresh)}`),
  createPortfolioItem: (payload: Partial<PortfolioItem> & { fund_code?: string; fund_name: string }) =>
    request<{ message: string; item: PortfolioItem }>("/api/portfolio/items", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  resolvePortfolioCodes: () =>
    request<{
      message: string;
      resolved_count: number;
      unresolved_count: number;
      resolved: Array<{ id: number; fund_name: string; match: { code: string; name: string; score: number } }>;
    }>("/api/portfolio/items/resolve-codes", { method: "POST" }),
  seedPortfolio: () =>
    request<{ message: string; created: number; updated: number; note: string }>("/api/portfolio/items/seed", {
      method: "POST"
    }),
  portfolioStrategy: (refresh = false) => request<PortfolioStrategy>(`/api/portfolio/strategy${refreshQuery(refresh)}`),
  fundRealtimeEstimates: (codes: string[], refresh = false) =>
    request<{
      count: number;
      estimates: Record<string, FundRealtimeEstimate>;
      as_of?: string;
      ttl_seconds?: number;
      stock_quote_ttl_seconds?: number;
      holding_ttl_seconds?: number;
      method?: string;
    }>(`/api/funds/realtime-estimates?codes=${encodeURIComponent(codes.join(","))}${refreshParam(refresh)}`),
  importPortfolioImage: (formData: FormData) =>
    request<{
      id: number;
      status: string;
      message: string;
      created: number;
      updated: number;
      parsed_items: Array<Record<string, unknown>>;
    }>("/api/portfolio/import-image", {
      method: "POST",
      body: formData
    }),
  importPortfolioText: (text: string, source_type = "holding") =>
    request<{ message: string; created: number; updated: number; parsed_items: Array<Record<string, unknown>> }>(
      "/api/portfolio/import-text",
      {
        method: "POST",
        body: JSON.stringify({ text, source_type })
      }
    ),
  actionSuggestions: (itemId: number) =>
    request<{ item: PortfolioItem; suggestions: ActionSuggestion[] }>(
      `/api/portfolio/items/${itemId}/action-suggestions`
    ),
  createPortfolioAction: (
    itemId: number,
    payload: {
      action_type: string;
      amount?: number | null;
      target_fund_code?: string;
      target_fund_name?: string;
      schedule?: string;
      status?: string;
      reason?: string;
    }
  ) =>
    request<{ message: string; action: PortfolioAction }>(`/api/portfolio/items/${itemId}/actions`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  fundDividend: (code: string) =>
    request<{ code: string; count: number; dividends: Array<Record<string, unknown>>; total_dividends?: number; warning?: string }>(
      `/api/funds/${code}/dividend`
    ),
  macroIndicators: (refresh = false) =>
    request<{
      indicators: Record<string, { name: string; value: number | null; date: string; unit: string }>;
      as_of: string;
      errors?: string[];
    }>(`/api/funds/macro/indicators${refreshQuery(refresh)}`)
};

export function formatPct(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "暂无";
  return `${Number(value).toFixed(2)}%`;
}
