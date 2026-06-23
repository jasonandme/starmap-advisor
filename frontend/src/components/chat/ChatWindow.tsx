"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Bot, Copy, FileText, Send, UserRound } from "lucide-react";
import { API_BASE, FundRecord, LlmOption, api, formatPct } from "@/lib/api";
import { FundTable } from "@/components/fund/FundTable";

type Message = {
  role: "user" | "assistant";
  content: string;
  cards?: Array<{ type: string; title: string; data: any }>;
};

export function ChatWindow() {
  const suggestedPrompts = [
    "分析 012920 今天、短线、长线怎么操作",
    "QDII 受美股和汇率影响怎么看",
    "新能源电池主题现在利好利空各是什么",
    "我的组合主题仓位是不是过高，今天适合加仓吗"
  ];
  const defaultMessages: Message[] = [
    {
      role: "assistant",
      content: "可以问我基金现状、利好利空、当天/短线/长线操作，也可以让我推荐、对比、穿透持仓。"
    }
  ];
  const [messages, setMessages] = useState<Message[]>(defaultMessages);
  const [input, setInput] = useState("");
  const [deepMode, setDeepMode] = useState(true);
  const [modelProvider, setModelProvider] = useState("deepseek");
  const [modelOptions, setModelOptions] = useState<LlmOption[]>([
    { id: "deepseek", name: "DeepSeek", model: "deepseek-chat", reasoner_model: "deepseek-reasoner", configured: true },
    { id: "kimi", name: "Kimi", model: "moonshot-v1-32k", reasoner_model: "moonshot-v1-32k", configured: false },
    { id: "qwen", name: "通义千问", model: "qwen-plus", reasoner_model: "qwen-plus", configured: false }
  ]);
  const [modelOptionsStatus, setModelOptionsStatus] = useState<"loading" | "ready" | "error">("loading");
  const [hydrated, setHydrated] = useState(false);
  const [loading, setLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const saved = window.localStorage.getItem("starmap-chat-messages");
    const savedModel = window.localStorage.getItem("starmap-chat-model");
    const savedDeepMode = window.localStorage.getItem("starmap-chat-deep-mode");
    if (savedModel) setModelProvider(savedModel);
    if (savedDeepMode) setDeepMode(savedDeepMode === "true");
    api.llmOptions()
      .then((result) => {
        setModelOptions(result.options);
        setModelOptionsStatus("ready");
        if (!savedModel && result.active) setModelProvider(result.active);
      })
      .catch(() => {
        setModelOptionsStatus("error");
      });
    if (saved) {
      try {
        const parsed = JSON.parse(saved) as Message[];
        if (Array.isArray(parsed) && parsed.length) setMessages(parsed);
      } catch {
        window.localStorage.removeItem("starmap-chat-messages");
      }
    }
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    window.localStorage.setItem("starmap-chat-messages", JSON.stringify(messages.slice(-30)));
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [hydrated, messages]);

  useEffect(() => {
    window.localStorage.setItem("starmap-chat-model", modelProvider);
    window.localStorage.setItem("starmap-chat-deep-mode", String(deepMode));
  }, [modelProvider, deepMode]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    setLoading(true);
    setMessages((current) => [...current, { role: "user", content: text }, { role: "assistant", content: "" }]);
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const history = messages
        .filter((item) => item.content.trim())
        .slice(-8)
        .map((item) => ({ role: item.role, content: item.content }));
      const response = await fetch(`${API_BASE}/api/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, history, deep_mode: deepMode, model_provider: modelProvider }),
        signal: controller.signal
      });
      if (!response.body) throw new Error("没有收到流式响应");
      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      let assistantText = "";
      let cards: Message["cards"] = [];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const chunks = buffer.split("\n\n");
        buffer = chunks.pop() || "";
        for (const chunk of chunks) {
          const line = chunk.split("\n").find((item) => item.startsWith("data: "));
          if (!line) continue;
          const payload = JSON.parse(line.slice(6));
          if (payload.type === "text") assistantText += payload.content;
          if (payload.type === "cards") cards = payload.cards || [];
          setMessages((current) => {
            const copy = [...current];
            copy[copy.length - 1] = { role: "assistant", content: assistantText, cards };
            return copy;
          });
        }
      }
    } catch (error) {
      setMessages((current) => {
        const copy = [...current];
        copy[copy.length - 1] = {
          role: "assistant",
          content: error instanceof Error ? error.message : "请求失败"
        };
        return copy;
      });
    } finally {
      setLoading(false);
      abortRef.current = null;
    }
  }

  const disabled = useMemo(() => loading || input.trim().length === 0, [loading, input]);

  function modelOptionLabel(option: LlmOption) {
    if (modelOptionsStatus === "loading") return `${option.name}（检测中）`;
    if (modelOptionsStatus === "error") return `${option.name}（待验证）`;
    return `${option.name}${option.configured ? "" : "（未配置）"}`;
  }

  function clearConversation() {
    setMessages(defaultMessages);
    window.localStorage.removeItem("starmap-chat-messages");
  }

  return (
    <div className="grid h-[calc(100vh-120px)] grid-cols-[1fr_320px] gap-4">
      <section className="chat-shell flex min-h-0 flex-col">
        <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
          <div>
            <h1 className="flex items-center gap-2 text-lg font-semibold text-ink">
              <FileText size={18} className="text-[var(--accent)]" />
              星图问策
            </h1>
            <p className="mt-1 text-sm text-ink-muted">先查结构化数据，再由模型组织投研结论；会携带最近上下文。</p>
          </div>
          <button
            className="focus-ring h-8 rounded-button border border-line bg-surface-2 px-3 text-xs text-ink-secondary transition-all hover:border-line-strong hover:text-ink"
            onClick={clearConversation}
            type="button"
          >
            新会话
          </button>
        </div>
        <div ref={scrollRef} className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
          {messages.map((message, index) => (
            <div key={index} className="space-y-3 animate-fade-in">
              <div className={`flex gap-3 ${message.role === "user" ? "justify-end" : "justify-start"}`}>
                {message.role === "assistant" ? (
                  <span className="mt-1 flex h-8 w-8 items-center justify-center rounded-button border border-line bg-surface-2 text-[var(--accent)]">
                    <Bot size={17} aria-hidden />
                  </span>
                ) : null}
                <div
                  className={`group relative max-w-[78%] whitespace-pre-wrap px-4 py-3 pr-10 text-sm leading-6 ${
                    message.role === "user"
                      ? "user-bubble text-ink"
                      : "assistant-bubble text-ink"
                  }`}
                >
                  {message.content || (loading && index === messages.length - 1 ? (
                    <span className="inline-flex gap-1">
                      <span className="h-2 w-2 rounded-full bg-[var(--accent)] animate-bounce" style={{ animationDelay: "0ms" }} />
                      <span className="h-2 w-2 rounded-full bg-[var(--accent)] animate-bounce" style={{ animationDelay: "150ms" }} />
                      <span className="h-2 w-2 rounded-full bg-[var(--accent)] animate-bounce" style={{ animationDelay: "300ms" }} />
                    </span>
                  ) : "")}
                  {message.content ? (
                    <button
                      type="button"
                      className="focus-ring absolute right-2 top-2 inline-flex h-7 w-7 items-center justify-center rounded-button text-ink-muted opacity-0 transition-all hover:bg-surface-3 hover:text-[var(--accent)] group-hover:opacity-100"
                      title="复制这条内容"
                      onClick={() => navigator.clipboard?.writeText(message.content)}
                    >
                      <Copy size={14} aria-hidden />
                    </button>
                  ) : null}
                </div>
                {message.role === "user" ? (
                  <span className="mt-1 flex h-8 w-8 items-center justify-center rounded-lg bg-surface-2 text-ink-muted">
                    <UserRound size={17} aria-hidden />
                  </span>
                ) : null}
              </div>
              {message.cards?.map((card, cardIndex) => (
                <CardRenderer card={card} key={`${index}-${cardIndex}`} />
              ))}
            </div>
          ))}
        </div>
        <form onSubmit={submit} className="flex items-end gap-2 border-t border-line p-4">
          <div className="min-w-0 flex-1">
            <div className="mb-2 flex flex-wrap gap-2">
              {suggestedPrompts.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  className="prompt-chip focus-ring px-2.5 py-1 text-xs transition-all"
                  onClick={() => setInput(prompt)}
                >
                  {prompt}
                </button>
              ))}
            </div>
            <div className="mb-2 flex flex-wrap items-center gap-3 text-xs text-ink-muted">
              <label className="inline-flex items-center gap-2">
                <span>问策模型</span>
                <select
                  className="focus-ring h-8 rounded-lg border border-line bg-surface-2 px-2 text-xs text-ink"
                  value={modelProvider}
                  onChange={(event) => setModelProvider(event.target.value)}
                >
                  {modelOptions.map((option) => (
                    <option key={option.id} value={option.id}>
                      {modelOptionLabel(option)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="inline-flex items-center gap-2">
                <input
                  className="h-4 w-4 accent-[var(--accent)]"
                  type="checkbox"
                  checked={deepMode}
                  onChange={(event) => setDeepMode(event.target.checked)}
                />
                <span>深度问策</span>
              </label>
            </div>
            <input
              className="focus-ring h-11 w-full rounded-lg border border-line bg-surface-2 px-3 text-sm text-ink placeholder:text-ink-muted"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="输入基金问题，例如：分析 012920 今天、短线、长线怎么操作"
            />
          </div>
          <button
            className="focus-ring inline-flex h-11 w-11 items-center justify-center rounded-button bg-[var(--accent)] text-white shadow-card transition-all hover:shadow-hover disabled:cursor-not-allowed disabled:bg-surface-3 disabled:text-ink-muted disabled:shadow-none"
            disabled={disabled}
            title="发送"
          >
            <Send size={18} aria-hidden />
          </button>
        </form>
      </section>
      <aside className="chat-shell p-4">
        <h2 className="text-sm font-semibold text-ink">当前策略边界</h2>
        <div className="mt-3 space-y-3 text-sm text-ink-secondary">
          <p>主线先看公募基金，股票用于持仓穿透、行业归因和新闻校验。</p>
          <p>推荐是候选池，不是自动下单；实盘前仍需要你确认仓位、回撤和费率。</p>
          <p>当前后端会自动保存问策记录；本页也会在浏览器本地保留最近对话。</p>
          <p>若配置了 DeepSeek/Qwen key，会用模型润色结构化数据；否则回落到本地模板。</p>
        </div>
      </aside>
    </div>
  );
}

function CardRenderer({ card }: { card: { type: string; data: any; title: string } }) {
  if (card.type === "recommendations" || card.type === "rank") {
    const funds = (card.data?.funds || []) as FundRecord[];
    return (
      <div className="ml-11">
        <FundTable funds={funds.slice(0, 5)} />
      </div>
    );
  }
  if (card.type === "comparison") {
    const funds = card.data?.funds || [];
    return (
      <div className="ml-11 grid grid-cols-3 gap-3">
        {funds.map((fund: any) => (
          <div key={fund.code} className="chat-shell p-4 text-sm">
            <div className="font-medium text-ink">{fund.name}</div>
            <div className="mt-1 font-mono text-xs text-ink-muted">{fund.code}</div>
            <div className="mt-3 space-y-1 text-ink-secondary">
              <div>近3月：<span className={pctColor(fund.metrics?.three_month_return)}>{formatPct(fund.metrics?.three_month_return)}</span></div>
              <div>回撤：{formatPct(fund.metrics?.max_drawdown)}</div>
              <div>波动：{formatPct(fund.metrics?.volatility)}</div>
            </div>
          </div>
        ))}
      </div>
    );
  }
  if (card.type === "holdings") {
    const holdings = card.data?.holdings || [];
    return (
      <div className="ml-11 chat-shell p-4">
        <div className="mb-3 text-sm font-medium text-ink">前十大持仓</div>
        <div className="grid grid-cols-2 gap-2 text-sm">
          {holdings.slice(0, 10).map((item: any) => (
            <div key={`${item.stock_code}-${item.stock_name}`} className="flex justify-between rounded-lg bg-surface-2/60 px-3 py-2">
              <span className="text-ink">{item.stock_name || item.stock_code}</span>
              <span className="tabular-nums text-ink-muted">{formatPct(item.hold_ratio)}</span>
            </div>
          ))}
        </div>
      </div>
    );
  }
  if (card.type === "portfolio_context") {
    const data = card.data || {};
    const positions = data.top_positions || [];
    const pnlValue = data.estimated_daily_profit ?? data.snapshot_daily_profit ?? null;
    const returnValue = data.estimated_daily_return_pct ?? data.snapshot_daily_return_pct ?? null;
    const usesSnapshot = data.estimated_daily_profit == null && data.snapshot_daily_profit != null;
    return (
      <div className="ml-11 chat-shell p-4">
        <div className="mb-3 text-sm font-medium text-ink">我的组合快照</div>
        <div className="grid grid-cols-4 gap-2 text-sm">
          <MiniMetric label="持仓市值" value={formatMoney(data.total_amount)} />
          <MiniMetric label={usesSnapshot ? "快照日盈亏" : "当日盈亏"} value={formatSignedMoney(pnlValue)} pct={pnlValue} />
          <MiniMetric label={usesSnapshot ? "快照涨跌" : "净值涨跌"} value={formatPct(returnValue)} pct={returnValue} />
          <MiniMetric label="主题仓位" value={formatPct(data.theme_pct)} />
        </div>
        <div className="mt-3 space-y-2">
          {positions.slice(0, 5).map((item: any) => (
            <div key={item.fund_code || item.fund_name} className="grid grid-cols-[1fr_72px_80px_80px] gap-2 rounded-lg bg-surface-2/50 px-3 py-2 text-xs">
              <div className="min-w-0">
                <div className="truncate font-medium text-ink">{item.fund_name}</div>
                <div className="font-mono text-ink-muted">{item.fund_code}</div>
              </div>
              <div className="text-right tabular-nums text-ink-secondary">{formatPct(item.position_pct)}</div>
              <div className={`text-right tabular-nums ${pctColor(item.nav_daily_return)}`}>{formatPct(item.nav_daily_return)}</div>
              <div className={`text-right tabular-nums ${pctColor(item.estimated_daily_profit ?? item.snapshot_daily_profit)}`}>{formatSignedMoney(item.estimated_daily_profit ?? item.snapshot_daily_profit)}</div>
            </div>
          ))}
        </div>
      </div>
    );
  }
  if (card.type === "fund_detail") {
    const tech = card.data?.technical;
    const metrics = card.data?.metrics || {};
    return (
      <div className="ml-11 chat-shell p-4">
        <div className="mb-3 text-sm font-medium text-ink">
          {card.data?.name || card.data?.code} 详情
        </div>
        <div className="grid grid-cols-3 gap-3 text-sm">
          <div className="rounded-lg bg-surface-2/60 p-3">
            <div className="mb-1 text-xs text-ink-muted">最新净值</div>
            <div className="text-lg font-semibold tabular-nums text-[var(--accent)]">{card.data?.latest_nav ?? "暂无"}</div>
          </div>
          <div className="rounded-lg bg-surface-2/60 p-3">
            <div className="mb-1 text-xs text-ink-muted">最大回撤</div>
            <div className="tabular-nums text-ink-secondary">{formatPct(metrics.max_drawdown)}</div>
          </div>
          <div className="rounded-lg bg-surface-2/60 p-3">
            <div className="mb-1 text-xs text-ink-muted">年化波动</div>
            <div className="tabular-nums text-ink-secondary">{formatPct(metrics.volatility)}</div>
          </div>
        </div>
        {tech?.available ? (
          <div className="mt-3 grid grid-cols-3 gap-2 text-sm">
            {tech.rsi_14 != null && (
              <div className="rounded-lg bg-accent-soft border border-line p-2">
                <div className="text-xs text-ink-muted">RSI(14)</div>
                <div className="font-semibold tabular-nums text-ink">{Number(tech.rsi_14).toFixed(1)}</div>
              </div>
            )}
            {tech.macd_signal && (
              <div className="rounded-lg bg-surface-2/60 border border-line p-2">
                <div className="text-xs text-ink-muted">MACD</div>
                <div className="text-xs text-ink-secondary">{tech.macd_signal}</div>
              </div>
            )}
            {tech.bollinger_signal && (
              <div className="rounded-lg bg-surface-2/60 border border-line p-2">
                <div className="text-xs text-ink-muted">布林带</div>
                <div className="text-xs text-ink-secondary">{tech.bollinger_signal}</div>
              </div>
            )}
          </div>
        ) : null}
      </div>
    );
  }
  if (card.type === "market_context") {
    const news = card.data?.market_news?.news || [];
    const usItems = card.data?.us_market?.items || [];
    const tech = card.data?.fund_detail?.technical;
    return (
      <div className="ml-11 chat-shell p-4">
        <div className="mb-3 text-sm font-medium text-ink">市场环境证据</div>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div className="rounded-lg bg-surface-2/60 p-3">
            <div className="mb-2 text-xs text-ink-muted">市场快讯</div>
            <div className="text-ink-secondary">{news.length ? `${news.length} 条快讯已纳入分析` : "暂无快讯数据"}</div>
          </div>
          <div className="rounded-lg bg-surface-2/60 p-3">
            <div className="mb-2 text-xs text-ink-muted">海外市场</div>
            <div className="text-ink-secondary">{usItems.length ? `${usItems.length} 条美股快照已纳入分析` : "未触发海外市场快照"}</div>
          </div>
        </div>
        {tech?.available ? (
          <div className="mt-3 grid grid-cols-3 gap-2 text-sm">
            {tech.rsi_14 != null && (
              <div className="rounded-lg bg-accent-soft border border-line p-2 text-center">
                <div className="text-xs text-ink-muted">RSI(14)</div>
                <div className="font-semibold tabular-nums text-ink">{Number(tech.rsi_14).toFixed(1)}</div>
              </div>
            )}
            {tech.macd_signal && (
              <div className="rounded-lg bg-surface-2/60 border border-line p-2 text-center">
                <div className="text-xs text-ink-muted">MACD</div>
                <div className="text-xs text-ink-secondary">{tech.macd_signal}</div>
              </div>
            )}
            {tech.bollinger_signal && (
              <div className="rounded-lg bg-surface-2/60 border border-line p-2 text-center">
                <div className="text-xs text-ink-muted">布林带</div>
                <div className="text-xs text-ink-secondary">{tech.bollinger_signal}</div>
              </div>
            )}
          </div>
        ) : null}
      </div>
    );
  }
  return null;
}

function MiniMetric({ label, value, pct }: { label: string; value: string; pct?: number | null }) {
  return (
    <div className="rounded-lg bg-surface-2/60 p-3">
      <div className="mb-1 text-xs text-ink-muted">{label}</div>
      <div className={`tabular-nums text-sm font-semibold ${pctColor(pct)}`}>{value}</div>
    </div>
  );
}

function formatMoney(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "暂无";
  return Number(value).toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatSignedMoney(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "暂无";
  return `${Number(value) >= 0 ? "+" : ""}${Number(value).toFixed(2)}`;
}

function pctColor(value: number | null | undefined) {
  if (value === null || value === undefined) return "text-ink-muted";
  return value > 0 ? "price-up" : value < 0 ? "price-down" : "";
}

