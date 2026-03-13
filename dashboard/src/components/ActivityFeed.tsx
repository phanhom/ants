import {
  MessageSquare,
  CheckCircle2,
  AlertCircle,
  ArrowRightLeft,
  FileText,
  Zap,
  Clock,
} from "lucide-react";
import { formatRelativeTime, truncate } from "@/lib/utils";
import type { TraceEvent } from "@/api";

const EVENT_CONFIG: Record<string, { icon: React.ComponentType<{ className?: string }>; color: string; label: string }> = {
  aip: { icon: ArrowRightLeft, color: "text-blue-500", label: "AIP" },
  report: { icon: FileText, color: "text-emerald-500", label: "Report" },
  todo: { icon: CheckCircle2, color: "text-amber-500", label: "Todo" },
  conversation: { icon: MessageSquare, color: "text-purple-500", label: "Chat" },
  llm_usage: { icon: Zap, color: "text-yellow-500", label: "LLM" },
  log: { icon: AlertCircle, color: "text-muted-foreground", label: "Log" },
};

function eventSummary(e: TraceEvent): string {
  const p = e.payload;
  switch (e.trace_type) {
    case "aip": {
      const action = (p.action as string) || "";
      const intent = (p.intent as string) || "";
      return `${action} → ${truncate(intent, 60)}`;
    }
    case "report":
      return (p.title as string) || "Report submitted";
    case "todo":
      return `${(p.title as string) || "Task"} [${(p.status as string) || "pending"}]`;
    case "llm_usage": {
      const model = (p.model as string) || "unknown";
      const tokens = (p.total_tokens as number) || 0;
      return `${model} · ${tokens.toLocaleString()} tokens`;
    }
    case "conversation":
      return truncate((p.content as string) || "", 80);
    default:
      return truncate(JSON.stringify(p), 80);
  }
}

export function ActivityFeed({ events }: { events: TraceEvent[] }) {
  if (!events.length) {
    return (
      <div className="flex items-center justify-center py-12 text-sm text-muted-foreground">
        <Clock className="mr-2 h-4 w-4" />
        No recent activity
      </div>
    );
  }

  return (
    <div className="space-y-0.5">
      {events.map((e, i) => {
        const config = EVENT_CONFIG[e.trace_type] ?? EVENT_CONFIG.log;
        const Icon = config.icon;
        return (
          <div
            key={`${e.ts}-${i}`}
            className="flex items-start gap-3 rounded-md px-3 py-2.5 transition-colors hover:bg-surface-hover"
          >
            <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${config.color}`} />
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline justify-between gap-2">
                <span className="text-[13px] text-foreground font-medium truncate">
                  {eventSummary(e)}
                </span>
                <span className="shrink-0 text-[11px] text-muted-foreground">
                  {formatRelativeTime(e.ts)}
                </span>
              </div>
              <p className="mt-0.5 text-[11px] text-muted-foreground font-medium">
                {e.agent_id}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
