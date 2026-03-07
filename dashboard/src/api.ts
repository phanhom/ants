const QUEEN_URL = (import.meta.env.VITE_QUEEN_URL as string) || "http://localhost:22000";

export async function getStatus(scope: "colony" | "self" | "subtree", root?: string): Promise<unknown> {
  const params = new URLSearchParams({ scope });
  if (root) params.set("root", root);
  const r = await fetch(`${QUEEN_URL}/status?${params}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function postInstruction(instruction: string, taskId?: string): Promise<unknown> {
  const r = await fetch(`${QUEEN_URL}/instruction`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ instruction, task_id: taskId ?? null }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function getTraces(params: { agent_id?: string; trace_type?: string; limit?: number; since?: string }): Promise<{
  ok: boolean;
  events: TraceEvent[];
  db_configured?: boolean;
  message?: string;
}> {
  const q = new URLSearchParams();
  if (params.agent_id) q.set("agent_id", params.agent_id);
  if (params.trace_type) q.set("trace_type", params.trace_type);
  q.set("limit", String(params.limit ?? 100));
  if (params.since) q.set("since", params.since);
  const r = await fetch(`/api/traces?${q}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export interface TraceEvent {
  agent_id: string;
  trace_type: string;
  ts: string;
  payload: Record<string, unknown>;
}
