"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  Compass,
  LayoutDashboard,
  MessageSquareText,
  Wallet,
  Sparkles
} from "lucide-react";

const navItems = [
  { href: "/", label: "总览", icon: LayoutDashboard },
  { href: "/portfolio", label: "我的持仓", icon: Wallet },
  { href: "/funds", label: "基金雷达", icon: BarChart3 },
  { href: "/sectors", label: "板块风向", icon: Compass },
  { href: "/chat", label: "星图问策", icon: MessageSquareText }
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="app-sidebar sticky top-0 hidden h-screen w-60 shrink-0 lg:flex lg:flex-col">
      {/* Logo */}
      <div className="px-5 py-5">
        <div className="flex items-center gap-2.5">
          <div className="brand-mark flex h-9 w-9 items-center justify-center rounded-lg">
            <Sparkles size={18} />
          </div>
          <div>
            <div className="text-base font-semibold text-ink">星图智顾</div>
            <div className="text-[11px] text-ink-muted">A 股 / 公募基金投研</div>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-0.5 px-3 py-2">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`focus-ring nav-link group flex h-10 items-center gap-3 rounded-lg px-3 text-sm transition-all duration-200 ${
                active ? "nav-link-active" : ""
              }`}
              title={item.label}
            >
              <Icon
                size={18}
                className="transition-transform duration-200 group-hover:scale-110"
                aria-hidden
              />
              <span>{item.label}</span>
              {active && (
                <span className="status-dot ml-auto h-1.5 w-1.5 rounded-full" />
              )}
            </Link>
          );
        })}
      </nav>

      {/* Bottom status */}
      <div className="border-t border-line px-4 py-3">
        <div className="flex items-center gap-2 text-[11px] text-ink-muted">
          <span className="status-dot h-1.5 w-1.5 rounded-full" />
          AKShare 数据层在线
        </div>
      </div>
    </aside>
  );
}
