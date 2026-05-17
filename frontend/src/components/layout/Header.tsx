"use client";

import { useEffect, useState } from "react";
import { Activity, Database, ShieldCheck } from "lucide-react";
import { AppearancePanel } from "@/components/ui/AppearancePanel";

export function Header() {
  const [clock, setClock] = useState("");

  useEffect(() => {
    function tick() {
      setClock(
        new Date().toLocaleString("zh-CN", {
          month: "2-digit",
          day: "2-digit",
          weekday: "short",
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hour12: false
        })
      );
    }
    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="topbar transition-colors">
      <div className="mx-auto flex h-14 w-full max-w-[1480px] items-center justify-between px-6">
        <div className="min-w-0">
          <div className="text-sm font-medium text-ink">个人投研工作台</div>
          <div className="text-xs text-ink-muted">基金优先，股票用于持仓穿透与归因</div>
        </div>
        <div className="flex items-center gap-3">
          <span className="font-mono text-xs tabular-nums text-ink-muted">{clock}</span>
          <div className="h-4 w-px bg-line" />
          <div className="flex items-center gap-2 text-xs text-ink-secondary">
            <span className="badge">
              <Database size={12} className="text-[var(--accent)]" aria-hidden />
              AKShare
            </span>
            <span className="badge">
              <ShieldCheck size={12} className="text-[var(--accent)]" aria-hidden />
              人在回路
            </span>
            <span className="badge">
              <Activity size={12} className="text-[var(--accent)]" aria-hidden />
              Pandas TA
            </span>
          </div>
          <div className="h-4 w-px bg-line" />
          <AppearancePanel />
        </div>
      </div>
    </header>
  );
}
