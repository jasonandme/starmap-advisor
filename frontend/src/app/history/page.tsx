"use client";

import { useEffect, useState } from "react";
import { ChevronDown, ChevronRight, Clock, MessageSquare } from "lucide-react";
import { api } from "@/lib/api";

type HistoryItem = {
  id: number;
  title: string;
  query: string;
  response: string;
  created_at: string;
};

export default function HistoryPage() {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [message, setMessage] = useState("");
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  useEffect(() => {
    api.history()
      .then((data) => setItems(data.items || []))
      .catch((error) => setMessage(error instanceof Error ? error.message : "加载失败"));
  }, []);

  function toggle(id: number) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div className="space-y-5 animate-fade-in">
      <div>
        <h1 className="text-xl font-semibold text-ink">分析历史</h1>
        <p className="mt-1 text-sm text-ink-muted">保存后的分析会在这里回看。点击展开查看完整回答。</p>
      </div>
      {message ? <div className="rounded-lg border border-up/30 bg-up/8 px-4 py-3 text-sm text-up">{message}</div> : null}
      <section className="space-y-2">
        {items.length === 0 ? (
          <div className="glass-card flex flex-col items-center gap-3 p-12 text-sm text-ink-muted">
            <Clock size={32} className="opacity-30" />
            暂无历史记录。进入星图问策后的对话会自动保存在这里。
          </div>
        ) : null}
        {items.map((item, index) => {
          const isOpen = expanded.has(item.id);
          return (
            <article
              key={item.id}
              className="glass-card overflow-hidden transition-all animate-fade-in"
              style={{ animationDelay: `${index * 0.05}s` }}
            >
              <button
                className="flex w-full items-center gap-3 px-5 py-4 text-left transition-colors hover:bg-surface-2/50"
                onClick={() => toggle(item.id)}
                type="button"
              >
                <MessageSquare size={16} className="shrink-0 text-jade" />
                <div className="min-w-0 flex-1">
                  <div className="font-semibold text-ink">{item.title || item.query.slice(0, 60)}</div>
                  <div className="mt-1 truncate text-sm text-ink-muted">{item.query}</div>
                </div>
                <span className="shrink-0 text-xs text-ink-muted">{formatTime(item.created_at)}</span>
                {isOpen ? (
                  <ChevronDown size={16} className="shrink-0 text-ink-muted" />
                ) : (
                  <ChevronRight size={16} className="shrink-0 text-ink-muted" />
                )}
              </button>
              {isOpen && (
                <div className="border-t border-line bg-surface-2/30 px-5 py-4 animate-fade-in">
                  <div className="mb-3 flex items-center gap-2 text-xs text-ink-muted">
                    <span className="rounded-md bg-jade/10 px-2 py-0.5 text-jade">问</span>
                    {item.query}
                  </div>
                  <div className="whitespace-pre-wrap text-sm leading-7 text-ink-secondary">
                    {item.response}
                  </div>
                </div>
              )}
            </article>
          );
        })}
      </section>
    </div>
  );
}

function formatTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}
