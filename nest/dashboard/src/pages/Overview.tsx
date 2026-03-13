import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { getStatus, getTraces, getCosts, type ColonyStatus } from "@/api";
import { MetricCard } from "@/components/MetricCard";
import { ActiveAgentsPanel } from "@/components/ActiveAgentsPanel";
import { DailyActivityChart, CostTrendChart, ModelDistributionChart } from "@/components/ActivityCharts";
import { Skeleton } from "@/components/ui/skeleton";
import { Users, ListTodo, DollarSign, ShieldAlert } from "lucide-react";
import { estimateCost } from "@/lib/costs";

export default function Overview() {
  const { t } = useTranslation();

  const { data: colony, isLoading: colonyLoading } = useQuery({
    queryKey: ["status", "colony"],
    queryFn: () => getStatus("colony") as Promise<ColonyStatus>,
    refetchInterval: 15_000,
  });

  const { data: tracesData } = useQuery({
    queryKey: ["traces", "overview"],
    queryFn: () => getTraces({ limit: 200 }),
  });

  const { data: costsData } = useQuery({
    queryKey: ["costs", "overview"],
    queryFn: () => getCosts({ limit: 500 }),
  });

  const events = tracesData?.events ?? [];
  const costs = costsData?.entries ?? [];

  const activeAgents = colony?.agents?.filter((a) => a.lifecycle === "running").length ?? 0;
  const pendingTasks = colony?.agents?.reduce((s, a) => s + a.pending_tasks, 0) ?? 0;
  const approvals = colony?.agents?.filter((a) => a.waiting_for_approval).length ?? 0;

  const todayCost = costs.reduce((total, c) => {
    return total + estimateCost(c.model, c.prompt_tokens, c.completion_tokens);
  }, 0);

  if (colonyLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48 rounded-md" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28 rounded-lg" />
          ))}
        </div>
        <Skeleton className="h-64 rounded-lg" />
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-6xl mx-auto">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">{t("overview.title")}</h1>
        <p className="mt-1.5 text-sm text-muted-foreground font-medium">{t("overview.subtitle")}</p>
      </div>

      {/* Metric cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title={t("overview.active_agents")}
          value={activeAgents}
          subtitle={`${colony?.agents?.length ?? 0} ${t("overview.total")}`}
          icon={Users}
        />
        <MetricCard
          title={t("overview.pending_tasks")}
          value={pendingTasks}
          icon={ListTodo}
        />
        <MetricCard
          title={t("overview.todays_cost")}
          value={todayCost < 0.01 ? "$0.00" : `$${todayCost.toFixed(2)}`}
          subtitle={`${costs.length} ${t("overview.llm_calls")}`}
          icon={DollarSign}
        />
        <MetricCard
          title={t("overview.approvals")}
          value={approvals}
          subtitle={approvals > 0 ? t("overview.needs_attention") : t("overview.all_clear")}
          icon={ShieldAlert}
        />
      </div>

      {/* Active Agents */}
      {colony && (
        <div className="space-y-4">
          <h2 className="text-sm font-semibold text-foreground">{t("overview.active_agents_panel")}</h2>
          <ActiveAgentsPanel agents={colony.agents ?? []} />
        </div>
      )}

      {/* Charts */}
      {(events.length > 0 || costs.length > 0) && (
        <div className="space-y-4">
          <h2 className="text-sm font-semibold text-foreground">{t("overview.activity_charts")}</h2>
          <div className="grid gap-4 lg:grid-cols-3">
            <div className="rounded-lg border border-border bg-surface p-4">
              <p className="text-xs font-medium text-muted-foreground mb-3">{t("overview.activity_charts")}</p>
              <DailyActivityChart events={events} />
            </div>
            <div className="rounded-lg border border-border bg-surface p-4">
              <p className="text-xs font-medium text-muted-foreground mb-3">{t("costs.spend_over_time")}</p>
              <CostTrendChart costs={costs} />
            </div>
            <div className="rounded-lg border border-border bg-surface p-4">
              <p className="text-xs font-medium text-muted-foreground mb-3">{t("costs.by_model")}</p>
              <ModelDistributionChart costs={costs} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
