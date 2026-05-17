import { LucideIcon } from "lucide-react";

type MetricCardProps = {
  label: string;
  value: string;
  subtitle?: string;
  tone?: "neutral" | "good" | "warn" | "bad";
  icon?: LucideIcon;
};

const toneStyles = {
  neutral: "",
  good: "",
  warn: "",
  bad: ""
};

const iconTone = {
  neutral: "text-ink-muted",
  good: "text-[var(--accent)]",
  warn: "text-amberline",
  bad: "text-up"
};

export function MetricCard({ label, value, subtitle, tone = "neutral", icon: Icon }: MetricCardProps) {
  return (
    <div
      data-tone={tone}
      className={`metric-card relative overflow-hidden p-4 transition-all duration-200 ${toneStyles[tone]}`}
    >
      <div className="flex items-center gap-2 text-xs text-ink-muted">
        {Icon ? <Icon size={15} className={iconTone[tone]} aria-hidden /> : null}
        {label}
      </div>
      <div className="mt-2 text-2xl font-semibold tabular-nums text-ink">{value}</div>
      {subtitle ? <div className="mt-1 text-xs text-ink-muted">{subtitle}</div> : null}
    </div>
  );
}
