import { Link } from "react-router-dom";
import { cn, formatRelativeTime } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import type { SingleAntStatus } from "@/api";

function lifecycleBadge(lc?: string) {
  switch (lc) {
    case "running": return <Badge variant="outline" className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20 font-medium">running</Badge>;
    case "failed": return <Badge variant="outline" className="bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20 font-medium">failed</Badge>;
    case "degraded": return <Badge variant="outline" className="bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20 font-medium">degraded</Badge>;
    case "blocked": return <Badge variant="outline" className="bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20 font-medium">blocked</Badge>;
    case "starting": return <Badge variant="outline" className="bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20 font-medium">starting</Badge>;
    default: return <Badge variant="outline" className="text-muted-foreground font-medium">{lc ?? "idle"}</Badge>;
  }
}

export function AgentGrid({ agents }: { agents: SingleAntStatus[] }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {agents.map((a) => (
        <Link
          key={a.agent_id}
          to={`/agent/${a.agent_id}`}
          className={cn(
            "group flex flex-col gap-3 p-4 rounded-lg border border-border bg-surface transition-all hover:border-muted-foreground/30 hover:shadow-sm"
          )}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <span className={cn("h-2 w-2 rounded-full", a.ok ? "bg-emerald-500" : "bg-red-500")} />
              <span className="text-sm font-semibold text-foreground truncate">{a.agent_id}</span>
            </div>
            {lifecycleBadge(a.lifecycle)}
          </div>
          <p className="text-[13px] text-muted-foreground leading-relaxed">{a.role}</p>
          <div className="mt-1 flex items-center justify-between text-[11px] font-medium text-muted-foreground">
            {a.pending_tasks > 0 ? (
              <span className="text-amber-600 dark:text-amber-400">{a.pending_tasks} pending</span>
            ) : (
              <span>No pending tasks</span>
            )}
            {a.last_seen_at && (
              <span>{formatRelativeTime(a.last_seen_at)}</span>
            )}
          </div>
        </Link>
      ))}
    </div>
  );
}
