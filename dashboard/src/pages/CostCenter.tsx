import { useEffect, useState } from "react";
import { getCosts, type CostEntry } from "@/api";
import { Card, CardTitle, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { estimateCost, MODEL_RATES } from "@/lib/costs";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
} from "recharts";

const COLORS = ["#58a6ff", "#7ee787", "#d2a8ff", "#f0883e", "#f778ba", "#79c0ff", "#ffa657"];

function groupByDay(entries: CostEntry[]) {
  const map = new Map<string, number>();
  for (const e of entries) {
    const day = e.ts.slice(0, 10);
    const cost = estimateCost(e.model, e.prompt_tokens, e.completion_tokens);
    map.set(day, (map.get(day) ?? 0) + cost);
  }
  return Array.from(map.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, cost]) => ({ date, cost: +cost.toFixed(4) }));
}

function groupByAgent(entries: CostEntry[]) {
  const map = new Map<string, { cost: number; tokens: number }>();
  for (const e of entries) {
    const cost = estimateCost(e.model, e.prompt_tokens, e.completion_tokens);
    const prev = map.get(e.agent_id) ?? { cost: 0, tokens: 0 };
    map.set(e.agent_id, { cost: prev.cost + cost, tokens: prev.tokens + e.total_tokens });
  }
  return Array.from(map.entries())
    .sort(([, a], [, b]) => b.cost - a.cost)
    .map(([agent_id, v]) => ({ agent_id, cost: +v.cost.toFixed(4), tokens: v.tokens }));
}

function groupByModel(entries: CostEntry[]) {
  const map = new Map<string, number>();
  for (const e of entries) {
    const cost = estimateCost(e.model, e.prompt_tokens, e.completion_tokens);
    map.set(e.model, (map.get(e.model) ?? 0) + cost);
  }
  return Array.from(map.entries())
    .sort(([, a], [, b]) => b - a)
    .map(([model, cost]) => ({ model, cost: +cost.toFixed(4) }));
}

const chartTooltipStyle = {
  contentStyle: { background: "#161b22", border: "1px solid rgba(240,246,252,0.08)", borderRadius: 8, fontSize: 12 },
  labelStyle: { color: "#8b949e" },
};

export default function CostCenter() {
  const [entries, setEntries] = useState<CostEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [dbHint, setDbHint] = useState<string | null>(null);

  useEffect(() => {
    getCosts({ limit: 1000 })
      .then((r) => {
        setEntries(r.entries ?? []);
        if (!r.db_configured) setDbHint(r.message ?? "Database not configured");
      })
      .catch(() => setDbHint("Failed to load cost data"))
      .finally(() => setLoading(false));
  }, []);

  const totalCost = entries.reduce(
    (s, e) => s + estimateCost(e.model, e.prompt_tokens, e.completion_tokens),
    0,
  );
  const totalTokens = entries.reduce((s, e) => s + e.total_tokens, 0);

  const byDay = groupByDay(entries);
  const byAgent = groupByAgent(entries);
  const byModel = groupByModel(entries);

  if (loading) {
    return (
      <div className="space-y-6 animate-fade-in">
        <Skeleton className="h-8 w-48" />
        <div className="grid gap-4 lg:grid-cols-2">
          <Skeleton className="h-72" />
          <Skeleton className="h-72" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-fade-in">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Cost Center</h1>
        <p className="mt-1 text-sm text-gray-500">
          Total: <span className="text-white font-medium">${totalCost.toFixed(4)}</span>
          {" "}&middot;{" "}
          {totalTokens.toLocaleString()} tokens across {entries.length} calls
        </p>
      </div>

      {dbHint && (
        <div className="glass-card border-amber-500/20 bg-amber-500/5 p-4 text-sm text-amber-300">
          {dbHint}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Spend Over Time */}
        <Card>
          <CardTitle>Spend Over Time</CardTitle>
          <CardContent className="mt-4 h-64">
            {byDay.length === 0 ? (
              <div className="flex h-full items-center justify-center text-sm text-gray-600">No data</div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={byDay}>
                  <XAxis dataKey="date" stroke="#30363d" tick={{ fontSize: 11, fill: "#8b949e" }} />
                  <YAxis stroke="#30363d" tick={{ fontSize: 11, fill: "#8b949e" }} tickFormatter={(v) => `$${v}`} />
                  <Tooltip {...chartTooltipStyle} formatter={(v: unknown) => [`$${Number(v).toFixed(4)}`, "Cost"]} />
                  <Line type="monotone" dataKey="cost" stroke="#58a6ff" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        {/* By Model */}
        <Card>
          <CardTitle>By Model</CardTitle>
          <CardContent className="mt-4 h-64">
            {byModel.length === 0 ? (
              <div className="flex h-full items-center justify-center text-sm text-gray-600">No data</div>
            ) : (
              <div className="flex h-full items-center">
                <ResponsiveContainer width="50%" height="100%">
                  <PieChart>
                    <Pie data={byModel} dataKey="cost" nameKey="model" cx="50%" cy="50%" outerRadius={80} innerRadius={50}>
                      {byModel.map((_, i) => (
                        <Cell key={i} fill={COLORS[i % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip {...chartTooltipStyle} formatter={(v: unknown) => [`$${Number(v).toFixed(4)}`, "Cost"]} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="space-y-2">
                  {byModel.map((m, i) => (
                    <div key={m.model} className="flex items-center gap-2 text-xs">
                      <span className="h-2.5 w-2.5 rounded-full" style={{ background: COLORS[i % COLORS.length] }} />
                      <span className="text-gray-300">{m.model}</span>
                      <span className="text-gray-500">${m.cost.toFixed(4)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* By Agent */}
        <Card className="lg:col-span-2">
          <CardTitle>By Agent</CardTitle>
          <CardContent className="mt-4 h-64">
            {byAgent.length === 0 ? (
              <div className="flex h-full items-center justify-center text-sm text-gray-600">No data</div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={byAgent} layout="vertical" margin={{ left: 100 }}>
                  <XAxis type="number" stroke="#30363d" tick={{ fontSize: 11, fill: "#8b949e" }} tickFormatter={(v) => `$${v}`} />
                  <YAxis type="category" dataKey="agent_id" stroke="#30363d" tick={{ fontSize: 11, fill: "#8b949e" }} width={100} />
                  <Tooltip {...chartTooltipStyle} formatter={(v: unknown) => [`$${Number(v).toFixed(4)}`, "Cost"]} />
                  <Bar dataKey="cost" fill="#58a6ff" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Rate reference */}
      <details className="text-xs text-gray-600">
        <summary className="cursor-pointer hover:text-gray-400">Pricing reference ($/1K tokens)</summary>
        <div className="mt-2 grid gap-1 pl-4">
          {Object.entries(MODEL_RATES)
            .filter(([k]) => k !== "default")
            .map(([model, rate]) => (
              <span key={model}>{model}: prompt ${rate.prompt} / completion ${rate.completion}</span>
            ))}
        </div>
      </details>
    </div>
  );
}
