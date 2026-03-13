import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { getCosts, getCostsByAgent } from "@/api";
import { Skeleton } from "@/components/ui/skeleton";
import { CostTrendChart, ModelDistributionChart } from "@/components/ActivityCharts";
import { estimateCost } from "@/lib/costs";
import { cn } from "@/lib/utils";

type DatePreset = "mtd" | "7d" | "30d" | "all";

function computeSince(preset: DatePreset): string | undefined {
  const now = new Date();
  switch (preset) {
    case "mtd": return new Date(now.getFullYear(), now.getMonth(), 1).toISOString();
    case "7d": return new Date(now.getTime() - 7 * 86_400_000).toISOString();
    case "30d": return new Date(now.getTime() - 30 * 86_400_000).toISOString();
    case "all": return undefined;
  }
}

export default function CostCenter() {
  const { t } = useTranslation();
  const [preset, setPreset] = useState<DatePreset>("mtd");

  const since = useMemo(() => computeSince(preset), [preset]);

  const { data: costsData, isLoading } = useQuery({
    queryKey: ["costs", "all", preset],
    queryFn: () => getCosts({ since, limit: 2000 }),
  });

  const { data: byAgentData } = useQuery({
    queryKey: ["costs-by-agent", preset],
    queryFn: () => getCostsByAgent({ since }),
  });

  const costs = costsData?.entries ?? [];
  const byAgent = byAgentData?.agents ?? [];

  const totalSpend = costs.reduce((s, c) => s + estimateCost(c.model, c.prompt_tokens, c.completion_tokens), 0);
  const totalTokens = costs.reduce((s, c) => s + c.total_tokens, 0);

  const presets: { key: DatePreset; label: string }[] = [
    { key: "mtd", label: t("costs.mtd") },
    { key: "7d", label: t("costs.7d") },
    { key: "30d", label: t("costs.30d") },
    { key: "all", label: t("costs.all") },
  ];

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48 rounded-md" />
        <Skeleton className="h-10 w-96 rounded-md" />
        <Skeleton className="h-64 rounded-lg" />
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">{t("costs.title")}</h1>
        <p className="mt-1.5 text-sm text-muted-foreground font-medium">{t("costs.subtitle")}</p>
      </div>

      {/* Date presets */}
      <div className="flex items-center gap-1">
        {presets.map((p) => (
          <button
            key={p.key}
            onClick={() => setPreset(p.key)}
            className={cn(
              "rounded-md px-3 py-1.5 text-[13px] font-medium transition-colors",
              preset === p.key
                ? "bg-foreground text-background"
                : "text-muted-foreground hover:bg-surface-hover hover:text-foreground",
            )}
          >
            {p.label}
          </button>
        ))}
      </div>

      {costs.length === 0 ? (
        <p className="text-sm text-muted-foreground py-12 text-center">{t("costs.no_data")}</p>
      ) : (
        <>
          {/* Summary cards */}
          <div className="grid gap-4 grid-cols-3">
            <div className="rounded-lg border border-border bg-surface p-4">
              <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">{t("costs.total_spend")}</p>
              <p className="text-2xl font-semibold text-foreground mt-2">${totalSpend.toFixed(4)}</p>
            </div>
            <div className="rounded-lg border border-border bg-surface p-4">
              <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">{t("costs.total_tokens")}</p>
              <p className="text-2xl font-semibold text-foreground mt-2">{totalTokens.toLocaleString()}</p>
            </div>
            <div className="rounded-lg border border-border bg-surface p-4">
              <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">{t("costs.api_calls")}</p>
              <p className="text-2xl font-semibold text-foreground mt-2">{costs.length}</p>
            </div>
          </div>

          {/* Charts */}
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-lg border border-border bg-surface p-4">
              <p className="text-xs font-medium text-muted-foreground mb-3">{t("costs.spend_over_time")}</p>
              <CostTrendChart costs={costs} />
            </div>
            <div className="rounded-lg border border-border bg-surface p-4">
              <p className="text-xs font-medium text-muted-foreground mb-3">{t("costs.by_model")}</p>
              <ModelDistributionChart costs={costs} />
            </div>
          </div>

          {/* By Agent table */}
          {byAgent.length > 0 && (
            <div className="rounded-lg border border-border bg-surface overflow-hidden">
              <div className="px-4 py-3 border-b border-border">
                <h2 className="text-sm font-semibold text-foreground">{t("costs.by_agent")}</h2>
              </div>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                    <th className="text-left px-4 py-2.5">Agent</th>
                    <th className="text-right px-4 py-2.5">{t("costs.api_calls")}</th>
                    <th className="text-right px-4 py-2.5">Prompt Tokens</th>
                    <th className="text-right px-4 py-2.5">Completion Tokens</th>
                    <th className="text-right px-4 py-2.5">{t("costs.total_tokens")}</th>
                  </tr>
                </thead>
                <tbody>
                  {byAgent.map((row) => (
                    <tr key={row.agent_id} className="border-b border-border last:border-0 hover:bg-surface-hover transition-colors">
                      <td className="px-4 py-2.5 font-medium text-foreground">{row.agent_id}</td>
                      <td className="px-4 py-2.5 text-right text-muted-foreground">{row.calls}</td>
                      <td className="px-4 py-2.5 text-right text-muted-foreground">{row.prompt_tokens.toLocaleString()}</td>
                      <td className="px-4 py-2.5 text-right text-muted-foreground">{row.completion_tokens.toLocaleString()}</td>
                      <td className="px-4 py-2.5 text-right font-medium text-foreground">{row.total_tokens.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
