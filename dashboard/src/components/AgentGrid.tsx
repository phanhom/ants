import { Link } from "react-router-dom";
import { cn, formatRelativeTime } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import type { SingleAntStatus } from "@/api";

function lifecycleBadge(lc?: string) {
  switch (lc) {
    case "running": return <Badge variant="success">running</Badge>;
    case "failed": return <Badge variant="danger">failed</Badge>;
    case "degraded": return <Badge variant="warning">degraded</Badge>;
    case "blocked": return <Badge variant="warning">blocked</Badge>;
    case "starting": return <Badge variant="default">starting</Badge>;
    default: return <Badge variant="muted">{lc ?? "idle"}</Badge>;
  }
}

export function AgentGrid({ agents }: { agents: SingleAntStatus[] }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {agents.map((a) => (
        <Link
          key={a.agent_id}
          to={`/agent/${a.agent_id}`}
          className={cn(
            "glass-card group flex flex-col gap-3 p-4 transition-all hover:border-border-strong",
          )}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className={cn("h-2 w-2 rounded-full", a.ok ? "bg-emerald-500" : "bg-red-400")} />
              <span className="text-sm font-medium text-white truncate">{a.agent_id}</span>
            </div>
            {lifecycleBadge(a.lifecycle)}
          </div>
          <p className="text-xs text-gray-500">{a.role}</p>
          <div className="flex items-center justify-between text-[11px] text-gray-600">
            {a.pending_todos > 0 ? (
              <span className="text-amber-400">{a.pending_todos} pending</span>
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
