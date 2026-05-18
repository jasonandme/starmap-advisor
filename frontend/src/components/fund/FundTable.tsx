"use client";

import Link from "next/link";
import { Plus, TrendingDown, TrendingUp } from "lucide-react";
import { FundRecord, formatPct } from "@/lib/api";

type FundTableProps = {
  funds: FundRecord[];
  onAdd?: (fund: FundRecord) => void;
  onSelect?: (fund: FundRecord) => void;
  onPrefetch?: (fund: FundRecord) => void;
};

function priceColor(value: number | null | undefined) {
  if (value === null || value === undefined) return "text-ink-muted";
  return value > 0 ? "price-up" : value < 0 ? "price-down" : "price-flat";
}

export function FundTable({ funds, onAdd, onSelect, onPrefetch }: FundTableProps) {
  return (
    <div className="fund-table overflow-hidden">
      <table className="w-full table-fixed border-collapse text-sm">
        <thead>
          <tr className="text-left text-xs text-ink-muted">
            <th className="w-[19%] px-4 py-3 font-medium">基金</th>
            <th className="w-[9%] px-4 py-3 font-medium">类型</th>
            <th className="w-[9%] px-4 py-3 font-medium">当天</th>
            <th className="w-[9%] px-4 py-3 font-medium">本周</th>
            <th className="w-[9%] px-4 py-3 font-medium">近1月</th>
            <th className="w-[9%] px-4 py-3 font-medium">近3月</th>
            <th className="w-[9%] px-4 py-3 font-medium">近1年</th>
            <th className="w-[9%] px-4 py-3 font-medium">评分</th>
            <th className="w-[8%] px-4 py-3 font-medium">风险</th>
            <th className="w-[6%] px-4 py-3 text-right font-medium">操作</th>
          </tr>
        </thead>
        <tbody>
          {funds.map((fund, index) => {
            const positive = (fund.year_return || 0) >= 0;
            const TrendIcon = positive ? TrendingUp : TrendingDown;
            return (
              <tr
                key={fund.code}
                className={`transition-colors duration-150 ${onSelect ? "cursor-pointer" : ""}`}
                onClick={onSelect ? () => onSelect(fund) : undefined}
                onMouseEnter={onPrefetch ? () => onPrefetch(fund) : undefined}
              >
                <td className="px-4 py-3">
                  {onSelect ? (
                    <button
                      type="button"
                      className="focus-ring text-left font-medium text-ink transition-colors hover:text-[var(--accent)] hover:underline"
                      onClick={(event) => {
                        event.stopPropagation();
                        onSelect(fund);
                      }}
                    >
                      {fund.name || fund.code}
                    </button>
                  ) : (
                    <Link href={`/funds?code=${fund.code}`} className="font-medium text-ink transition-colors hover:text-[var(--accent)]">
                      {fund.name || fund.code}
                    </Link>
                  )}
                  <div className="mt-0.5 font-mono text-xs text-ink-muted">{fund.code}</div>
                </td>
                <td className="px-4 py-3">
                  <span className="inline-block rounded-md bg-surface-2 px-2 py-0.5 text-xs text-ink-secondary">
                    {fund.fund_type || "暂无"}
                  </span>
                </td>
                <td className={`px-4 py-3 tabular-nums font-medium ${priceColor(fund.daily_return)}`}>
                  {formatPct(fund.daily_return)}
                </td>
                <td className={`px-4 py-3 tabular-nums ${priceColor(fund.week_return)}`}>
                  {formatPct(fund.week_return)}
                </td>
                <td className={`px-4 py-3 tabular-nums ${priceColor(fund.month_return)}`}>
                  {formatPct(fund.month_return)}
                </td>
                <td className={`px-4 py-3 tabular-nums ${priceColor(fund.three_month_return)}`}>
                  {formatPct(fund.three_month_return)}
                </td>
                <td className={`px-4 py-3 tabular-nums font-medium ${priceColor(fund.year_return)}`}>
                  {formatPct(fund.year_return)}
                </td>
                <td className="px-4 py-3">
                  <span className="inline-flex items-center gap-1 tabular-nums">
                    <TrendIcon size={14} className={positive ? "text-up" : "text-down"} aria-hidden />
                    <span className="text-ink-secondary">{fund.score ?? "暂无"}</span>
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className={`text-xs ${
                    fund.risk_level === "偏高" ? "text-up" : fund.risk_level === "偏低" ? "text-[var(--accent)]" : "text-amberline"
                  }`}>
                    {fund.risk_level || "中等"}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  {onAdd ? (
                    <button
                      className="focus-ring inline-flex h-7 w-7 items-center justify-center rounded-button border border-line bg-surface-2 text-ink-muted transition-all hover:border-line-strong hover:bg-surface-3 hover:text-[var(--accent)]"
                      onClick={(event) => {
                        event.stopPropagation();
                        onAdd(fund);
                      }}
                      title="加入自选"
                    >
                      <Plus size={15} aria-hidden />
                    </button>
                  ) : null}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
