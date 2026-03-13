import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  getStatus,
  postInstruction,
  getTraces,
  getReports,
  getCosts,
  getConversations,
  type ColonyStatus,
  type SingleAntStatus,
  type TraceEvent,
  type ReportEntry,
  type CostEntry,
  type ConversationMessage,
} from "@/api";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Card, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { cn, formatRelativeTime } from "@/lib/utils";
import { estimateCost } from "@/lib/costs";
import { ArrowLeft, Send, Bot, User } from "lucide-react";

export default function AgentDetail() {
  const { agentId } = useParams<{ agentId: string }>();
  const [ant, setAnt] = useState<SingleAntStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [instruction, setInstruction] = useState("");
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  // Tab data
  const [reports, setReports] = useState<ReportEntry[]>([]);
  const [costs, setCosts] = useState<CostEntry[]>([]);
  const [conversations, setConversations] = useState<ConversationMessage[]>([]);
  const [traces, setTraces] = useState<TraceEvent[]>([]);

  useEffect(() => {
    if (!agentId) return;
    setLoading(true);
    Promise.allSettled([
      getStatus("colony").then((d) => {
        const colony = d as ColonyStatus;
        const found = colony.ants?.find((a) => a.agent_id === agentId);
        if (found) setAnt(found);
      }),
      getReports({ agent_id: agentId, limit: 20 }).then((r) => setReports(r.reports ?? [])),
      getCosts({ agent_id: agentId, limit: 200 }).then((r) => setCosts(r.entries ?? [])),
      getConversations(agentId, 50).then((r) => setConversations(r.messages ?? [])),
      getTraces({ agent_id: agentId, limit: 50 }).then((r) => setTraces(r.events ?? [])),
    ]).finally(() => setLoading(false));
  }, [agentId]);

  const handleSend = async () => {
    if (!instruction.trim() || sending) return;
    setSending(true);
    setErr(null);
    setSent(null);
    try {
      await postInstruction(instruction);
      setSent("Instruction sent");
      setInstruction("");
    } catch (e) {
      setErr(String(e));
    } finally {
      setSending(false);
    }
  };

  if (!agentId) return null;

  if (loading) {
    return (
      <div className="space-y-6 animate-fade-in">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-32" />
        <Skeleton className="h-64" />
      </div>
    );
  }

  const todos = ant?.work?.todos ?? [];
  const completedTodos = todos.filter((t) => t.status === "completed").length;
  const todoProgress = todos.length > 0 ? Math.round((completedTodos / todos.length) * 100) : 0;

  const totalCost = costs.reduce(
    (s, c) => s + estimateCost(c.model, c.prompt_tokens, c.completion_tokens),
    0,
  );

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center gap-3">
        <Link to="/" className="text-gray-500 hover:text-gray-300 transition-colors">
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div>
          <h1 className="text-xl font-semibold tracking-tight">{agentId}</h1>
          {ant && <p className="text-sm text-gray-500">{ant.role}</p>}
        </div>
        {ant && (
          <div className="ml-auto flex items-center gap-2">
            <span className={cn("h-2 w-2 rounded-full", ant.ok ? "bg-emerald-500" : "bg-red-400")} />
            <Badge variant={ant.lifecycle === "running" ? "success" : "muted"}>
              {ant.lifecycle ?? "idle"}
            </Badge>
          </div>
        )}
      </div>

      {/* Status summary */}
      {ant && (
        <div className="grid gap-4 sm:grid-cols-4">
          <Card>
            <CardTitle>Tasks</CardTitle>
            <CardContent>
              <p className="metric-value mt-1">{ant.pending_todos}</p>
              <p className="text-xs text-gray-500 mt-1">pending</p>
            </CardContent>
          </Card>
          <Card>
            <CardTitle>Reports</CardTitle>
            <CardContent>
              <p className="metric-value mt-1">{reports.length}</p>
            </CardContent>
          </Card>
          <Card>
            <CardTitle>Cost</CardTitle>
            <CardContent>
              <p className="metric-value mt-1">${totalCost.toFixed(4)}</p>
              <p className="text-xs text-gray-500 mt-1">{costs.length} calls</p>
            </CardContent>
          </Card>
          <Card>
            <CardTitle>Last Seen</CardTitle>
            <CardContent>
              <p className="mt-1 text-sm text-gray-300">
                {ant.last_seen_at ? formatRelativeTime(ant.last_seen_at) : "Never"}
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      <Tabs defaultValue="tasks">
        <TabsList>
          <TabsTrigger value="tasks">Tasks</TabsTrigger>
          <TabsTrigger value="reports">Reports</TabsTrigger>
          <TabsTrigger value="conversations">Chat</TabsTrigger>
          <TabsTrigger value="traces">Activity</TabsTrigger>
          <TabsTrigger value="instruction">Instruct</TabsTrigger>
        </TabsList>

        {/* Tasks */}
        <TabsContent value="tasks">
          {todos.length === 0 ? (
            <p className="py-8 text-center text-sm text-gray-600">No tasks</p>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs text-gray-500">
                <span>{completedTodos}/{todos.length} completed</span>
                <span>{todoProgress}%</span>
              </div>
              <Progress value={todoProgress} />
              <div className="space-y-1">
                {todos.slice(0, 30).map((t, i) => (
                  <div key={i} className="flex items-center gap-3 rounded-lg px-3 py-2 hover:bg-white/[0.02]">
                    <span className={cn(
                      "h-2 w-2 rounded-full shrink-0",
                      t.status === "completed" ? "bg-emerald-500" :
                      t.status === "in_progress" ? "bg-accent" :
                      "bg-gray-600",
                    )} />
                    <span className="flex-1 text-sm text-gray-300 truncate">{t.title || "Untitled"}</span>
                    <Badge variant={
                      t.status === "completed" ? "success" :
                      t.status === "in_progress" ? "default" :
                      "muted"
                    }>
                      {t.status || "pending"}
                    </Badge>
                  </div>
                ))}
              </div>
            </div>
          )}
        </TabsContent>

        {/* Reports */}
        <TabsContent value="reports">
          {reports.length === 0 ? (
            <p className="py-8 text-center text-sm text-gray-600">No reports</p>
          ) : (
            <div className="space-y-3">
              {reports.map((r, i) => (
                <Card key={i}>
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="text-sm font-medium text-white">{r.title}</p>
                      <Badge variant={r.status === "final" ? "success" : "default"} className="mt-1">{r.status}</Badge>
                    </div>
                    <span className="text-[11px] text-gray-600">{formatRelativeTime(r.ts)}</span>
                  </div>
                  {r.body && (
                    <p className="mt-3 text-sm text-gray-400 whitespace-pre-wrap leading-relaxed">{r.body}</p>
                  )}
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        {/* Conversations */}
        <TabsContent value="conversations">
          {conversations.length === 0 ? (
            <p className="py-8 text-center text-sm text-gray-600">No conversations</p>
          ) : (
            <div className="space-y-3 max-h-[500px] overflow-y-auto">
              {conversations.map((m, i) => (
                <div key={i} className={cn("flex gap-3", m.role === "assistant" ? "" : "flex-row-reverse")}>
                  <div className={cn("shrink-0 mt-1 rounded-lg p-1.5", m.role === "assistant" ? "bg-accent/10" : "bg-gray-800")}>
                    {m.role === "assistant" ? <Bot className="h-3.5 w-3.5 text-accent" /> : <User className="h-3.5 w-3.5 text-gray-400" />}
                  </div>
                  <div className={cn(
                    "glass-card max-w-[80%] p-3",
                    m.role === "assistant" ? "border-accent/10" : "",
                  )}>
                    <p className="text-sm text-gray-300 whitespace-pre-wrap leading-relaxed">{m.content}</p>
                    <p className="mt-1 text-[10px] text-gray-600">{formatRelativeTime(m.ts)}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </TabsContent>

        {/* Activity Traces */}
        <TabsContent value="traces">
          {traces.length === 0 ? (
            <p className="py-8 text-center text-sm text-gray-600">No activity</p>
          ) : (
            <div className="space-y-1">
              {traces.map((e, i) => (
                <div key={i} className="flex items-start gap-3 rounded-lg px-3 py-2 text-xs hover:bg-white/[0.02]">
                  <span className="shrink-0 w-20 text-gray-600 font-mono text-[11px]">
                    {new Date(e.ts).toLocaleTimeString()}
                  </span>
                  <Badge variant="muted">{e.trace_type}</Badge>
                  <span className="text-gray-400 truncate">
                    {JSON.stringify(e.payload).slice(0, 100)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </TabsContent>

        {/* Instruction */}
        <TabsContent value="instruction">
          <Card>
            <p className="text-xs text-gray-500 mb-3">
              Send instruction to the queen. It will be decomposed and may be delegated to this or other agents.
            </p>
            <textarea
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              placeholder="Your instruction..."
              className="w-full h-28 rounded-lg border border-border bg-[#0d1117] px-3 py-2 text-sm text-gray-300 placeholder:text-gray-600 resize-none focus:outline-none focus:border-accent/50"
            />
            <div className="mt-3 flex items-center gap-3">
              <button
                onClick={handleSend}
                disabled={sending || !instruction.trim()}
                className="flex items-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent/80 disabled:opacity-50"
              >
                <Send className="h-3.5 w-3.5" />
                {sending ? "Sending..." : "Send"}
              </button>
              {sent && <span className="text-sm text-emerald-400">{sent}</span>}
              {err && <span className="text-sm text-red-400">{err}</span>}
            </div>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
