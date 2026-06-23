"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Check, Monitor, Moon, Palette, Sun } from "lucide-react";
import { useTheme } from "@/components/ui/ThemeProvider";
import type { ThemeMode, VisualStyle } from "@/components/ui/ThemeProvider";

const styleOptions: Array<{
  value: VisualStyle;
  name: string;
  description: string;
  swatches: string[];
}> = [
  {
    value: "terminal-pro",
    name: "专业投研终端",
    description: "冷蓝灰、高密度、适合盘中盯盘和数据判断。",
    swatches: ["#08111f", "#101a2a", "#38bdf8", "#ef4444", "#22c55e"]
  },
  {
    value: "research-paper",
    name: "纸面研究简报",
    description: "纸白、墨黑、藏蓝，适合长时间阅读研报式结论。",
    swatches: ["#f7f3ea", "#fffaf0", "#274060", "#b42318", "#147d4f"]
  },
  {
    value: "ledger-east",
    name: "东方账册",
    description: "宣纸色、朱砂红、青黛色，偏持仓札记和策略记录。",
    swatches: ["#f6f1e4", "#fff8e8", "#1f4f5f", "#c2410c", "#15803d"]
  }
];

const modeOptions: Array<{
  value: ThemeMode;
  name: string;
  icon: typeof Monitor;
}> = [
  { value: "system", name: "跟随系统", icon: Monitor },
  { value: "light", name: "浅色", icon: Sun },
  { value: "dark", name: "深色", icon: Moon }
];

export function AppearancePanel() {
  const { visualStyle, mode, setVisualStyle, setMode, resetTheme } = useTheme();
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!open) return;
    function handlePointerDown(event: PointerEvent) {
      const target = event.target as Node;
      if (rootRef.current?.contains(target) || panelRef.current?.contains(target)) return;
      setOpen(false);
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  return (
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        className="focus-ring flex h-9 items-center gap-2 rounded-button border border-line bg-surface-2 px-3 text-xs text-ink-secondary transition-all hover:border-line-strong hover:text-ink"
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
        aria-haspopup="dialog"
      >
        <Palette size={14} className="text-[var(--accent)]" aria-hidden />
        外观
      </button>
      {open && mounted ? createPortal(
        <div
          ref={panelRef}
          className="fixed right-6 top-16 z-[2147483647] isolate w-[360px] rounded-card border border-line bg-panel-solid p-3 shadow-hover"
          role="dialog"
          aria-label="外观设置"
        >
          <div className="mb-3">
            <div className="text-sm font-semibold text-ink">外观设置</div>
            <div className="mt-1 text-xs text-ink-muted">选择视觉风格和明暗模式，立即生效。</div>
          </div>

          <div className="space-y-2">
            {styleOptions.map((option) => {
              const active = option.value === visualStyle;
              return (
                <button
                  key={option.value}
                  type="button"
                  className={`focus-ring w-full rounded-card border p-3 text-left transition-all ${
                    active
                      ? "border-line-strong bg-accent-soft text-ink shadow-card"
                      : "border-line bg-surface-2 text-ink-secondary hover:border-line-strong hover:bg-surface-3"
                  }`}
                  onClick={() => {
                    setVisualStyle(option.value);
                    setOpen(false);
                  }}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-medium text-ink">{option.name}</div>
                      <div className="mt-1 text-xs leading-5 text-ink-muted">{option.description}</div>
                    </div>
                    {active ? <Check size={16} className="mt-0.5 text-[var(--accent)]" aria-hidden /> : null}
                  </div>
                  <div className="mt-3 flex gap-1.5">
                    {option.swatches.map((color) => (
                      <span
                        key={color}
                        className="h-4 flex-1 rounded-sm border border-line"
                        style={{ backgroundColor: color }}
                      />
                    ))}
                  </div>
                </button>
              );
            })}
          </div>

          <div className="mt-3 grid grid-cols-3 gap-2">
            {modeOptions.map((option) => {
              const Icon = option.icon;
              const active = option.value === mode;
              return (
                <button
                  key={option.value}
                  type="button"
                  className={`focus-ring flex h-9 items-center justify-center gap-1.5 rounded-button border text-xs transition-all ${
                    active
                      ? "border-line-strong bg-accent-soft text-ink"
                      : "border-line bg-surface-2 text-ink-muted hover:border-line-strong hover:text-ink"
                  }`}
                  onClick={() => {
                    setMode(option.value);
                    setOpen(false);
                  }}
                >
                  <Icon size={14} aria-hidden />
                  {option.name}
                </button>
              );
            })}
          </div>
          <button
            type="button"
            className="focus-ring mt-3 h-9 w-full rounded-button border border-line bg-surface-2 text-xs text-ink-secondary transition-all hover:border-line-strong hover:text-ink"
            onClick={() => {
              resetTheme();
              setOpen(false);
            }}
          >
            恢复默认外观
          </button>
        </div>,
        document.body
      ) : null}
    </div>
  );
}
