import { useEffect, useState } from "react";
import { getTasks, type TaskGroup } from "@/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { formatRelativeTime, truncate } from "@/lib/utils";
import { GitBranch, ArrowRight, Clock } from "lucide-react";
import { cn } from "@/lib/utils";

function statusVariant(s: string) {
  switch (s) {
    case "completed": return "success" as const;
    case "failed": return "danger" as const;
    case "working": return "default" as const;
    default: return "muted" as const;
  }
}

function TaskCard({ task }: { task: TaskGroup }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <Card
      className={cn("cursor-pointer transition-all hover:border-border-strong", expanded && "border-border-strong")}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-2">
            <GitBranch className="h-3.5 w-3.5 text-gray-500 shrink-0" />
            <span className="text-xs text-gray-500 font-mono truncate">{task.trace_id.slice(0, 12)}</span>
            <Badge variant={statusVariant(task.status)}>{task.status}</Badge>
          </div>
          {task.instruction && (
            <p className="text-sm text-gray-200 mb-2">
              {truncate(task.instruction, 120)}
            </p>
          )}
          <Progress value={task.progress} className="mb-2" />
          <div className="flex items-center gap-1 flex-wrap">
            {task.agents.map((a, i) => (
              <span key={a} className="flex items-center gap-1">
                {i > 0 && <ArrowRight className="h-3 w-3 text-gray-700" />}
                <Badge variant="muted">{a}</Badge>
              </span>
            ))}
          </div>
        </div>
        <span className="shrink-0 text-[11px] text-gray-600">{formatRelativeTime(task.ts)}</span>
      </div>

      {expanded && task.events.length > 0 && (
        <div className="mt-4 border-t border-border pt-3 space-y-2">
          <p className="section-title">Timeline</p>
          {task.events.map((e, i) => (
            <div key={i} className="flex items-start gap-3 text-xs">
              <span className="shrink-0 w-16 text-gray-600 font-mono">
                {new Date(e.ts).toLocaleTimeString()}
              </span>
              <div className="flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-accent" />
                <span className="text-gray-400">{e.agent_id}</span>
                <span className="text-gray-500">{e.trace_type}</span>
                <span className="text-gray-600 truncate max-w-xs">
                  {truncate(
                    (e.payload?.action as string) ||
                    (e.payload?.title as string) ||
                    (e.payload?.event as string) ||
                    "",
                    60,
                  )}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

export default function TaskFlow() {
  const [tasks, setTasks] = useState<TaskGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [dbHint, setDbHint] = useState<string | null>(null);

  useEffect(() => {
    getTasks({ limit: 200 })
      .then((r) => {
        setTasks(r.tasks ?? []);
        if (!r.db_configured) setDbHint(r.message ?? "Database not configured");
      })
      .catch(() => setDbHint("Failed to load tasks"))
      .finally(() => setLoading(false));
  }, []);

  const active = tasks.filter((t) => t.status === "working");
  const completed = tasks.filter((t) => t.status !== "working");

  if (loading) {
    return (
      <div className="space-y-6 animate-fade-in">
        <Skeleton className="h-8 w-48" />
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-32" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-fade-in">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Task Flow</h1>
        <p className="mt-1 text-sm text-gray-500">
          {active.length} active &middot; {completed.length} completed
        </p>
      </div>

      {dbHint && (
        <div className="glass-card border-amber-500/20 bg-amber-500/5 p-4 text-sm text-amber-300">{dbHint}</div>
      )}

      {tasks.length === 0 && !dbHint && (
        <div className="flex flex-col items-center justify-center py-16 text-gray-600">
          <Clock className="h-8 w-8 mb-3" />
          <p className="text-sm">No tasks yet</p>
        </div>
      )}

      {active.length > 0 && (
        <div>
          <p className="section-title mb-3">Active</p>
          <div className="space-y-3">
            {active.map((t) => <TaskCard key={t.trace_id} task={t} />)}
          </div>
        </div>
      )}

      {completed.length > 0 && (
        <div>
          <p className="section-title mb-3">History</p>
          <div className="space-y-3">
            {completed.map((t) => <TaskCard key={t.trace_id} task={t} />)}
          </div>
        </div>
      )}
    </div>
  );
}
