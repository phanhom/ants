import { useEffect, useState, useMemo } from "react";
import { getTraces, type TraceEvent } from "@/api";
import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { formatRelativeTime, truncate } from "@/lib/utils";
import { Activity, Clock, ArrowRightLeft, FileText, CheckCircle2, MessageSquare, Zap } from "lucide-react";

const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  aip: ArrowRightLeft,
  report: FileText,
  todo: CheckCircle2,
  conversation: MessageSquare,
  llm_usage: Zap,
};

function eventLine(e: TraceEvent): string {
  const p = e.payload;
  switch (e.trace_type) {
    case "aip":
      return `${p.action ?? "aip"} → ${truncate((p.intent as string) || "", 50)}`;
    case "report":
      return (p.title as string) || "Report";
    case "todo":
      return `${(p.title as string) || "Todo"} [${p.status || "pending"}]`;
    case "llm_usage":
      return `${p.model || "model"} · ${((p.total_tokens as number) || 0).toLocaleString()} tok`;
    case "conversation":
      return truncate((p.content as string) || "", 70);
    default:
      return truncate(JSON.stringify(p), 70);
  }
}

export default function Traces() {
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [agentId, setAgentId] = useState("");
  const [traceType, setTraceType] = useState("");
  const [dbHint, setDbHint] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    setDbHint(null);
    getTraces({ agent_id: agentId || undefined, trace_type: traceType || undefined, limit: 200 })
      .then((r) => {
        setEvents(r.events ?? []);
        if (!r.db_configured) setDbHint(r.message ?? "Database not configured");
      })
      .catch(() => setDbHint("Failed to load traces"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const grouped = useMemo(() => {
    const map = new Map<string, TraceEvent[]>();
    for (const e of events) {
      const traceId = (e.payload?.trace_id as string) || "ungrouped";
      const arr = map.get(traceId) ?? [];
      arr.push(e);
      map.set(traceId, arr);
    }
    return Array.from(map.entries()).map(([traceId, evts]) => ({
      traceId,
      events: evts.sort((a, b) => a.ts.localeCompare(b.ts)),
      agents: [...new Set(evts.map((e) => e.agent_id))],
      ts: evts[0]?.ts ?? "",
    }));
  }, [events]);

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Traces</h1>
        <p className="mt-1 text-sm text-gray-500">Events grouped by trace</p>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2 flex-wrap">
        <input
          type="text"
          placeholder="agent_id"
          value={agentId}
          onChange={(e) => setAgentId(e.target.value)}
          className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-gray-300 placeholder:text-gray-600 w-40"
        />
        <input
          type="text"
          placeholder="trace_type"
          value={traceType}
          onChange={(e) => setTraceType(e.target.value)}
          className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-gray-300 placeholder:text-gray-600 w-40"
        />
        <button
          onClick={load}
          disabled={loading}
          className="rounded-lg bg-white/[0.06] px-4 py-2 text-sm font-medium text-gray-300 transition-colors hover:bg-white/[0.1] disabled:opacity-50"
        >
          Refresh
        </button>
      </div>

      {dbHint && (
        <div className="glass-card border-amber-500/20 bg-amber-500/5 p-4 text-sm text-amber-300">{dbHint}</div>
      )}

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-12" />)}
        </div>
      ) : grouped.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-gray-600">
          <Clock className="h-8 w-8 mb-3" />
          <p className="text-sm">No events</p>
        </div>
      ) : (
        <Accordion type="multiple" className="space-y-1">
          {grouped.map((g) => (
            <AccordionItem key={g.traceId} value={g.traceId} className="glass-card overflow-hidden border">
              <AccordionTrigger className="px-4">
                <div className="flex items-center gap-2 min-w-0 flex-1">
                  <Activity className="h-3.5 w-3.5 text-accent shrink-0" />
                  <span className="font-mono text-xs text-gray-400 shrink-0">
                    {g.traceId === "ungrouped" ? "ungrouped" : g.traceId.slice(0, 10)}
                  </span>
                  <span className="text-xs text-gray-600">{g.events.length} events</span>
                  <div className="flex gap-1 ml-auto">
                    {g.agents.map((a) => (
                      <Badge key={a} variant="muted">{a}</Badge>
                    ))}
                  </div>
                  <span className="text-[11px] text-gray-600 shrink-0">{formatRelativeTime(g.ts)}</span>
                </div>
              </AccordionTrigger>
              <AccordionContent className="px-4 pb-3">
                <div className="space-y-1.5">
                  {g.events.map((e, i) => {
                    const Icon = ICON_MAP[e.trace_type] ?? Activity;
                    return (
                      <div key={i} className="flex items-start gap-3 py-1 text-xs">
                        <span className="shrink-0 w-20 text-gray-600 font-mono text-[11px]">
                          {new Date(e.ts).toLocaleTimeString()}
                        </span>
                        <Icon className="h-3.5 w-3.5 mt-0.5 text-gray-500 shrink-0" />
                        <span className="text-gray-500 w-16 shrink-0">{e.agent_id}</span>
                        <Badge variant="muted" className="shrink-0">{e.trace_type}</Badge>
                        <span className="text-gray-400 truncate">{eventLine(e)}</span>
                      </div>
                    );
                  })}
                </div>
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      )}
    </div>
  );
}
