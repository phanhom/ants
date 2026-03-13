import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import {
  getStatus,
  postInstruction,
  getTraces,
  getReports,
  getCosts,
  getConversations,
  getAgentConfigs,
  type ColonyStatus,
  type SingleAntStatus,
  type AgentConfigEntry,
} from "@/api";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge, StatusDot } from "@/components/StatusBadge";
import { cn, formatRelativeTime } from "@/lib/utils";
import { estimateCost } from "@/lib/costs";
import { ArrowLeft, Send, Bot, User } from "lucide-react";

export default function AgentDetail() {
  const { agentId } = useParams<{ agentId: string }>();
  const { t } = useTranslation();
  const [instruction, setInstruction] = useState("");
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const { data: colony, isLoading } = useQuery({
    queryKey: ["status", "colony"],
    queryFn: () => getStatus("colony") as Promise<ColonyStatus>,
    refetchInterval: 15_000,
  });

  const { data: reportsData } = useQuery({
    queryKey: ["reports", agentId],
    queryFn: () => getReports({ agent_id: agentId, limit: 20 }),
    enabled: !!agentId,
  });

  const { data: costsData } = useQuery({
    queryKey: ["costs", agentId],
    queryFn: () => getCosts({ agent_id: agentId, limit: 200 }),
    enabled: !!agentId,
  });

  const { data: convData } = useQuery({
    queryKey: ["conversations", agentId],
    queryFn: () => getConversations(agentId!, 50),
    enabled: !!agentId,
  });

  const { data: tracesData } = useQuery({
    queryKey: ["traces", agentId],
    queryFn: () => getTraces({ agent_id: agentId, limit: 50 }),
    enabled: !!agentId,
  });

  const { data: configsData } = useQuery({
    queryKey: ["agent-configs"],
    queryFn: () => getAgentConfigs(),
  });

  const ant: SingleAntStatus | undefined = colony?.agents?.find((a) => a.agent_id === agentId);
  const config: AgentConfigEntry | undefined = configsData?.configs?.find((c) => c.agent_id === agentId);
  const reports = reportsData?.reports ?? [];
  const costs = costsData?.entries ?? [];
  const conversations = convData?.messages ?? [];
  const traces = tracesData?.events ?? [];

  const handleSend = async () => {
    if (!instruction.trim() || sending) return;
    setSending(true);
    setErr(null);
    setSent(null);
    try {
      await postInstruction(instruction);
      setSent(t("agent.instruction_sent"));
      setInstruction("");
    } catch (e) {
      setErr(String(e));
    } finally {
      setSending(false);
    }
  };

  if (!agentId) return null;

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64 rounded-md" />
        <Skeleton className="h-32 rounded-lg" />
        <Skeleton className="h-64 rounded-lg" />
      </div>
    );
  }

  const todos = ant?.work?.tasks ?? [];
  const completedTodos = todos.filter((t) => t.status === "completed").length;
  const todoProgress = todos.length > 0 ? Math.round((completedTodos / todos.length) * 100) : 0;
  const totalCost = costs.reduce((s, c) => s + estimateCost(c.model, c.prompt_tokens, c.completion_tokens), 0);

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link to="/" className="text-muted-foreground hover:text-foreground transition-colors">
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-semibold tracking-tight text-foreground">{agentId}</h1>
            {ant && <StatusBadge status={ant.lifecycle ?? "idle"} />}
          </div>
          {ant && <p className="text-sm text-muted-foreground mt-0.5">{ant.role}</p>}
        </div>
        {ant && <StatusDot ok={ant.ok} className="h-3 w-3" />}
      </div>

      {/* Properties + Metrics grid */}
      <div className="grid gap-6 lg:grid-cols-[1fr_280px]">
        {/* Main content */}
        <div className="space-y-6">
          {/* Metric cards */}
          <div className="grid gap-3 grid-cols-4">
            {[
              { label: t("agent.tasks"), value: String(ant?.pending_tasks ?? 0), sub: t("agent.pending") },
              { label: t("agent.reports"), value: String(reports.length) },
              { label: t("agent.cost"), value: `$${totalCost.toFixed(4)}`, sub: `${costs.length} ${t("agent.calls")}` },
              { label: t("agent.last_seen"), value: ant?.last_seen_at ? formatRelativeTime(ant.last_seen_at) : t("agent.never") },
            ].map((m) => (
              <div key={m.label} className="rounded-lg border border-border bg-surface p-3">
                <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">{m.label}</p>
                <p className="text-lg font-semibold text-foreground mt-1">{m.value}</p>
                {m.sub && <p className="text-[11px] text-muted-foreground mt-0.5">{m.sub}</p>}
              </div>
            ))}
          </div>

          {/* Tabs */}
          <Tabs defaultValue="tasks">
            <TabsList>
              <TabsTrigger value="tasks">{t("agent.tasks")}</TabsTrigger>
              <TabsTrigger value="reports">{t("agent.reports")}</TabsTrigger>
              <TabsTrigger value="conversations">{t("agent.chat")}</TabsTrigger>
              <TabsTrigger value="traces">{t("agent.activity")}</TabsTrigger>
              <TabsTrigger value="instruction">{t("agent.instruct")}</TabsTrigger>
            </TabsList>

            <TabsContent value="tasks">
              {todos.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">{t("agent.no_tasks")}</p>
              ) : (
                <div className="space-y-3">
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>{completedTodos}/{todos.length} {t("agent.completed")}</span>
                    <span>{todoProgress}%</span>
                  </div>
                  <Progress value={todoProgress} />
                  <div className="space-y-1">
                    {todos.slice(0, 30).map((td, i) => (
                      <div key={i} className="flex items-center gap-3 rounded-md px-3 py-2 hover:bg-surface-hover transition-colors">
                        <span className={cn(
                          "h-2 w-2 rounded-full shrink-0",
                          td.status === "completed" ? "bg-emerald-500" :
                          td.status === "in_progress" ? "bg-blue-500" :
                          "bg-muted-foreground/40",
                        )} />
                        <span className="flex-1 text-sm text-foreground truncate">{td.title || "Untitled"}</span>
                        <Badge variant={td.status === "completed" ? "success" : td.status === "in_progress" ? "default" : "muted"}>
                          {td.status || "pending"}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </TabsContent>

            <TabsContent value="reports">
              {reports.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">{t("agent.no_reports")}</p>
              ) : (
                <div className="space-y-3">
                  {reports.map((r, i) => (
                    <div key={i} className="rounded-lg border border-border bg-surface p-4">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <p className="text-sm font-medium text-foreground">{r.title}</p>
                          <Badge variant={r.status === "final" ? "success" : "default"} className="mt-1">{r.status}</Badge>
                        </div>
                        <span className="text-[11px] text-muted-foreground">{formatRelativeTime(r.ts)}</span>
                      </div>
                      {r.body && (
                        <p className="mt-3 text-sm text-muted-foreground whitespace-pre-wrap leading-relaxed">{r.body}</p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </TabsContent>

            <TabsContent value="conversations">
              {conversations.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">{t("agent.no_conversations")}</p>
              ) : (
                <div className="space-y-3 max-h-[500px] overflow-y-auto">
                  {conversations.map((m, i) => (
                    <div key={i} className={cn("flex gap-3", m.role === "assistant" ? "" : "flex-row-reverse")}>
                      <div className={cn("shrink-0 mt-1 rounded-md p-1.5", m.role === "assistant" ? "bg-muted" : "bg-muted")}>
                        {m.role === "assistant" ? <Bot className="h-3.5 w-3.5 text-foreground" /> : <User className="h-3.5 w-3.5 text-muted-foreground" />}
                      </div>
                      <div className="rounded-lg border border-border bg-surface max-w-[80%] p-3">
                        <p className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">{m.content}</p>
                        <p className="mt-1 text-[10px] text-muted-foreground">{formatRelativeTime(m.ts)}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </TabsContent>

            <TabsContent value="traces">
              {traces.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">{t("agent.no_activity")}</p>
              ) : (
                <div className="space-y-1">
                  {traces.map((e, i) => (
                    <div key={i} className="flex items-start gap-3 rounded-md px-3 py-2 text-xs hover:bg-surface-hover transition-colors">
                      <span className="shrink-0 w-20 text-muted-foreground font-mono text-[11px]">
                        {new Date(e.ts).toLocaleTimeString()}
                      </span>
                      <Badge variant="muted">{e.trace_type}</Badge>
                      <span className="text-muted-foreground truncate">
                        {JSON.stringify(e.payload).slice(0, 100)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </TabsContent>

            <TabsContent value="instruction">
              <div className="rounded-lg border border-border bg-surface p-4">
                <p className="text-xs text-muted-foreground mb-3">{t("agent.instruction_hint")}</p>
                <textarea
                  value={instruction}
                  onChange={(e) => setInstruction(e.target.value)}
                  placeholder={t("agent.instruction_placeholder")}
                  className="w-full h-28 rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground resize-none focus:outline-none focus:ring-1 focus:ring-border"
                />
                <div className="mt-3 flex items-center gap-3">
                  <button
                    onClick={handleSend}
                    disabled={sending || !instruction.trim()}
                    className="flex items-center gap-1.5 rounded-md bg-foreground px-4 py-2 text-sm font-medium text-background transition-colors hover:opacity-80 disabled:opacity-40"
                  >
                    <Send className="h-3.5 w-3.5" />
                    {sending ? t("agent.sending") : t("agent.send")}
                  </button>
                  {sent && <span className="text-sm text-emerald-500 font-medium">{sent}</span>}
                  {err && <span className="text-sm text-red-500">{err}</span>}
                </div>
              </div>
            </TabsContent>
          </Tabs>
        </div>

        {/* Properties sidebar */}
        <div className="space-y-4">
          <div className="rounded-lg border border-border bg-surface p-4 space-y-4">
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t("agent.properties")}</h3>

            {config?.description && (
              <div>
                <p className="text-[11px] text-muted-foreground mb-1">{t("agent.description")}</p>
                <p className="text-[13px] text-foreground leading-relaxed">{config.description}</p>
              </div>
            )}

            <div>
              <p className="text-[11px] text-muted-foreground mb-1">{t("agent.lifecycle")}</p>
              <StatusBadge status={ant?.lifecycle ?? "idle"} />
            </div>

            <div>
              <p className="text-[11px] text-muted-foreground mb-1">{t("agent.superior")}</p>
              {config?.superior ? (
                <Link to={`/agent/${config.superior}`} className="text-[13px] text-foreground hover:underline font-medium">
                  {config.superior}
                </Link>
              ) : (
                <span className="text-[13px] text-muted-foreground">{t("agent.root")}</span>
              )}
            </div>

            {config?.subordinates && config.subordinates.length > 0 && (
              <div>
                <p className="text-[11px] text-muted-foreground mb-1">{t("agent.subordinates")}</p>
                <div className="flex flex-wrap gap-1">
                  {config.subordinates.map((s) => (
                    <Link key={s} to={`/agent/${s}`} className="text-[12px] text-foreground hover:underline font-medium bg-muted rounded-md px-2 py-0.5">
                      {s}
                    </Link>
                  ))}
                </div>
              </div>
            )}

            {config?.tools && config.tools.length > 0 && (
              <div>
                <p className="text-[11px] text-muted-foreground mb-1">{t("agent.tools")}</p>
                <div className="flex flex-wrap gap-1">
                  {(config.tools as string[]).map((tool) => (
                    <span key={tool} className="text-[11px] text-muted-foreground bg-muted rounded px-1.5 py-0.5">
                      {tool}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
