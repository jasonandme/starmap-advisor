export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export type FundRecord = {
  code: string;
  name: string;
  fund_type?: string;
  unit_nav?: number;
  daily_return?: number;
  week_return?: number;
  month_return?: number;
  three_month_return?: number;
  six_month_return?: number;
  year_return?: number;
  this_year_return?: number;
  score?: number;
  risk_level?: string;
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
  estimated_daily_profit?: number | null;
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const isFormData = init?.body instanceof FormData;
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(init?.headers || {})
    },
    cache: "no-store"
  });
  if (!response.ok) {
    const text = await response.text();
    let message = text || `HTTP ${response.status}`;
    try {
      const data = JSON.parse(text);
      message = data.detail || data.message || message;
    } catch {
      // Keep the raw response text when it is not JSON.
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string; app: string; version: string }>("/api/health"),
  llmOptions: () => request<{ active: string; options: LlmOption[] }>("/api/system/llm-options"),
  recommend: (fundType = "QDII", risk = "balanced", topN = 5) =>
    request<{ funds: FundRecord[]; warning?: string; source?: string }>(
      `/api/funds/recommend?fund_type=${encodeURIComponent(fundType)}&risk=${risk}&top_n=${topN}`
    ),
  rank: (fundType = "全部", topN = 30) =>
    request<{ funds: FundRecord[]; warning?: string; source?: string }>(
      `/api/funds/rank?fund_type=${encodeURIComponent(fundType)}&top_n=${topN}`
    ),
  searchFunds: (query: string) =>
    request<{ funds: FundRecord[]; warning?: string }>(
      `/api/funds/search?q=${encodeURIComponent(query)}`
    ),
  fundDetail: (code: string) => request<FundDetail>(`/api/funds/${code}`),
  sectorOverview: (limit = 80) => request<SectorOverview>(`/api/sectors/overview?limit=${limit}`),
  sectorNews: (name: string, limit = 10) =>
    request<{ name: string; news: Array<Record<string, unknown>>; matched: boolean; warning?: string | null }>(
      `/api/sectors/${encodeURIComponent(name)}/news?limit=${limit}`
    ),
  compare: (codes: string[]) =>
    request<{ funds: FundDetail[] }>("/api/funds/compare", {
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
  portfolioItems: () => request<{ count: number; items: PortfolioItem[] }>("/api/portfolio/items"),
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
  portfolioStrategy: () => request<PortfolioStrategy>("/api/portfolio/strategy"),
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
  macroIndicators: () =>
    request<{
      indicators: Record<string, { name: string; value: number | null; date: string; unit: string }>;
      as_of: string;
      errors?: string[];
    }>("/api/funds/macro/indicators")
};

export function formatPct(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "暂无";
  return `${Number(value).toFixed(2)}%`;
}
