import { useEffect, useState } from "react";
import { getStatus, getTraces, getCosts, type ColonyStatus, type TraceEvent, type CostEntry } from "@/api";
import { MetricCard } from "@/components/MetricCard";
import { ActivityFeed } from "@/components/ActivityFeed";
import { AgentGrid } from "@/components/AgentGrid";
import { Skeleton } from "@/components/ui/skeleton";
import { Users, ListTodo, DollarSign, ShieldAlert } from "lucide-react";
import { estimateCost } from "@/lib/costs";

export default function Overview() {
  const [colony, setColony] = useState<ColonyStatus | null>(null);
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [costs, setCosts] = useState<CostEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.allSettled([
      getStatus("colony").then((d) => setColony(d as ColonyStatus)),
      getTraces({ limit: 20 }).then((r) => setEvents(r.events ?? [])),
      getCosts({ limit: 500 }).then((r) => setCosts(r.entries ?? [])),
    ]).finally(() => setLoading(false));
  }, []);

  const activeAgents = colony?.ants.filter((a) => a.lifecycle === "running").length ?? 0;
  const pendingTasks = colony?.ants.reduce((s, a) => s + a.pending_todos, 0) ?? 0;
  const approvals = colony?.ants.filter((a) => a.waiting_for_approval).length ?? 0;

  const todayCost = costs.reduce((total, c) => {
    return total + estimateCost(c.model, c.prompt_tokens, c.completion_tokens);
  }, 0);

  if (loading) {
    return (
      <div className="space-y-6 animate-fade-in">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
        <Skeleton className="h-64" />
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-fade-in">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Overview</h1>
        <p className="mt-1 text-sm text-gray-500">Colony status at a glance</p>
      </div>

      {/* Hero metrics */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="Active Agents"
          value={activeAgents}
          subtitle={`${colony?.ants.length ?? 0} total`}
          icon={Users}
        />
        <MetricCard
          title="Pending Tasks"
          value={pendingTasks}
          icon={ListTodo}
        />
        <MetricCard
          title="Today's Cost"
          value={todayCost < 0.01 ? "$0.00" : `$${todayCost.toFixed(2)}`}
          subtitle={`${costs.length} LLM calls`}
          icon={DollarSign}
        />
        <MetricCard
          title="Approvals"
          value={approvals}
          subtitle={approvals > 0 ? "Needs attention" : "All clear"}
          icon={ShieldAlert}
        />
      </div>

      {/* Activity Feed */}
      <div className="glass-card p-0 overflow-hidden">
        <div className="border-b border-border px-5 py-3">
          <h2 className="text-sm font-medium text-gray-300">Recent Activity</h2>
        </div>
        <div className="max-h-[400px] overflow-y-auto">
          <ActivityFeed events={events} />
        </div>
      </div>

      {/* Agent Grid */}
      {colony && (
        <div>
          <h2 className="mb-3 text-sm font-medium text-gray-300">Agents</h2>
          <AgentGrid agents={colony.ants} />
        </div>
      )}
    </div>
  );
}
