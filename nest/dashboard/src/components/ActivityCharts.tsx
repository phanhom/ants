import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, AreaChart, Area } from "recharts";
import type { CostEntry, TraceEvent } from "@/api";
import { estimateCost } from "@/lib/costs";

const COLORS = [
  "var(--foreground)",
  "var(--muted-foreground)",
  "#10b981",
  "#f59e0b",
  "#ef4444",
  "#8b5cf6",
];

export function DailyActivityChart({ events }: { events: TraceEvent[] }) {
  const data = useMemo(() => {
    const byDay: Record<string, number> = {};
    for (const e of events) {
      const day = e.ts.slice(0, 10);
      byDay[day] = (byDay[day] || 0) + 1;
    }
    return Object.entries(byDay)
      .sort(([a], [b]) => a.localeCompare(b))
      .slice(-14)
      .map(([day, count]) => ({ day: day.slice(5), count }));
  }, [events]);

  if (data.length === 0) return null;

  return (
    <ResponsiveContainer width="100%" height={180}>
      <BarChart data={data}>
        <XAxis dataKey="day" tick={{ fontSize: 11 }} stroke="var(--muted-foreground)" />
        <YAxis tick={{ fontSize: 11 }} stroke="var(--muted-foreground)" width={30} />
        <Tooltip
          contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }}
        />
        <Bar dataKey="count" fill="var(--foreground)" radius={[3, 3, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function CostTrendChart({ costs }: { costs: CostEntry[] }) {
  const data = useMemo(() => {
    const byDay: Record<string, number> = {};
    for (const c of costs) {
      const day = c.ts.slice(0, 10);
      const cost = estimateCost(c.model, c.prompt_tokens, c.completion_tokens);
      byDay[day] = (byDay[day] || 0) + cost;
    }
    return Object.entries(byDay)
      .sort(([a], [b]) => a.localeCompare(b))
      .slice(-14)
      .map(([day, cost]) => ({ day: day.slice(5), cost: +cost.toFixed(4) }));
  }, [costs]);

  if (data.length === 0) return null;

  return (
    <ResponsiveContainer width="100%" height={180}>
      <AreaChart data={data}>
        <XAxis dataKey="day" tick={{ fontSize: 11 }} stroke="var(--muted-foreground)" />
        <YAxis tick={{ fontSize: 11 }} stroke="var(--muted-foreground)" width={40} tickFormatter={(v: number) => `$${v}`} />
        <Tooltip
          contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }}
          formatter={((value: unknown) => [`$${Number(value).toFixed(4)}`, "Cost"]) as never}
        />
        <Area type="monotone" dataKey="cost" stroke="var(--foreground)" fill="var(--muted)" strokeWidth={1.5} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function ModelDistributionChart({ costs }: { costs: CostEntry[] }) {
  const { t } = useTranslation();
  const data = useMemo(() => {
    const byModel: Record<string, number> = {};
    for (const c of costs) {
      const model = c.model || "unknown";
      byModel[model] = (byModel[model] || 0) + c.total_tokens;
    }
    return Object.entries(byModel)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 6)
      .map(([name, value]) => ({ name, value }));
  }, [costs]);

  if (data.length === 0) return null;

  return (
    <ResponsiveContainer width="100%" height={180}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={70} innerRadius={40} strokeWidth={1} stroke="var(--border)">
          {data.map((_, i) => (
            <Cell key={i} fill={COLORS[i % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }}
          formatter={((value: unknown) => [Number(value).toLocaleString() + ` ${t("costs.tokens")}`, ""]) as never}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
