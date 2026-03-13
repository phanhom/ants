const QUEEN = (import.meta.env.VITE_QUEEN_URL as string) || "http://localhost:22000";

async function json<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init);
  if (!r.ok) throw new Error(await r.text());
  return r.json() as Promise<T>;
}

// ── Queen API ────────────────────────────────────────────────────────────────

export interface SingleAntStatus {
  agent_id: string;
  role: string;
  superior?: string;
  authority_weight?: number;
  lifecycle?: string;
  port?: number;
  ok: boolean;
  base_url?: string;
  pending_todos: number;
  recent_errors: number;
  waiting_for_approval: boolean;
  last_report_at?: string;
  last_aip_at?: string;
  last_seen_at?: string;
  container_name?: string;
  container_state?: string;
  work?: WorkSnapshot;
}

export interface WorkSnapshot {
  todos: Array<{ title?: string; status?: string; ts?: string }>;
  reports: Array<Record<string, unknown>>;
  recent_aip: Array<Record<string, unknown>>;
  last_seen?: string;
  pending_todos: number;
}

export interface ColonyStatus {
  ok: boolean;
  root_agent_id: string;
  timestamp: string;
  topology: Record<string, string[]>;
  waiting_for_approval: boolean;
  ants: SingleAntStatus[];
}

export interface RecursiveNode {
  self: SingleAntStatus;
  subordinates: RecursiveNode[];
}

export function getStatus(scope: "colony" | "self" | "subtree", root?: string) {
  const p = new URLSearchParams({ scope });
  if (root) p.set("root", root);
  return json<ColonyStatus | RecursiveNode>(`${QUEEN}/status?${p}`);
}

export function postInstruction(instruction: string, taskId?: string) {
  return json(`${QUEEN}/instruction`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ instruction, task_id: taskId ?? null }),
  });
}

// ── Dashboard Backend API ────────────────────────────────────────────────────

export interface TraceEvent {
  agent_id: string;
  trace_type: string;
  ts: string;
  payload: Record<string, unknown>;
}

export interface TracesResponse {
  ok: boolean;
  events: TraceEvent[];
  db_configured?: boolean;
  message?: string;
}

export function getTraces(params: {
  agent_id?: string;
  trace_type?: string;
  limit?: number;
  since?: string;
}) {
  const q = new URLSearchParams();
  if (params.agent_id) q.set("agent_id", params.agent_id);
  if (params.trace_type) q.set("trace_type", params.trace_type);
  q.set("limit", String(params.limit ?? 100));
  if (params.since) q.set("since", params.since);
  return json<TracesResponse>(`/api/traces?${q}`);
}

// ── Cost API ─────────────────────────────────────────────────────────────────

export interface CostEntry {
  ts: string;
  agent_id: string;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  request_duration_ms?: number;
}

export interface CostsResponse {
  ok: boolean;
  entries: CostEntry[];
  db_configured?: boolean;
  message?: string;
}

export function getCosts(params?: { agent_id?: string; since?: string; limit?: number }) {
  const q = new URLSearchParams();
  if (params?.agent_id) q.set("agent_id", params.agent_id);
  if (params?.since) q.set("since", params.since);
  q.set("limit", String(params?.limit ?? 500));
  return json<CostsResponse>(`/api/costs?${q}`);
}

// ── Reports API ──────────────────────────────────────────────────────────────

export interface ReportEntry {
  agent_id: string;
  ts: string;
  title: string;
  body: string;
  status: string;
}

export interface ReportsResponse {
  ok: boolean;
  reports: ReportEntry[];
  db_configured?: boolean;
  message?: string;
}

export function getReports(params?: { agent_id?: string; limit?: number }) {
  const q = new URLSearchParams();
  if (params?.agent_id) q.set("agent_id", params.agent_id);
  q.set("limit", String(params?.limit ?? 50));
  return json<ReportsResponse>(`/api/reports?${q}`);
}

// ── Tasks API ────────────────────────────────────────────────────────────────

export interface TaskGroup {
  trace_id: string;
  instruction?: string;
  ts: string;
  events: TraceEvent[];
  agents: string[];
  status: "working" | "completed" | "failed" | "unknown";
  progress: number;
}

export interface TasksResponse {
  ok: boolean;
  tasks: TaskGroup[];
  db_configured?: boolean;
  message?: string;
}

export function getTasks(params?: { limit?: number }) {
  const q = new URLSearchParams();
  q.set("limit", String(params?.limit ?? 200));
  return json<TasksResponse>(`/api/tasks?${q}`);
}

// ── Conversations API ────────────────────────────────────────────────────────

export interface ConversationMessage {
  ts: string;
  agent_id: string;
  role: string;
  content: string;
}

export interface ConversationsResponse {
  ok: boolean;
  messages: ConversationMessage[];
  db_configured?: boolean;
}

export function getConversations(agentId: string, limit = 100) {
  const q = new URLSearchParams({ agent_id: agentId, limit: String(limit) });
  return json<ConversationsResponse>(`/api/conversations?${q}`);
}

// ── Files (MinIO) API ────────────────────────────────────────────────────────

export interface FileObject {
  name: string;
  key: string;
  size: number;
  lastModified: string;
  isDirectory: boolean;
}

export interface FilesResponse {
  ok: boolean;
  files: FileObject[];
  prefix: string;
  configured?: boolean;
  message?: string;
}

export function getFiles(prefix = "") {
  const q = new URLSearchParams({ prefix, delimiter: "/" });
  return json<FilesResponse>(`/api/files?${q}`);
}

export function getFileDownloadUrl(key: string): string {
  return `/api/files/download?key=${encodeURIComponent(key)}`;
}

export async function uploadFile(file: File, prefix: string) {
  const form = new FormData();
  form.append("file", file);
  form.append("prefix", prefix);
  return json(`/api/files/upload`, { method: "POST", body: form });
}

export async function deleteFile(key: string) {
  return json(`/api/files?key=${encodeURIComponent(key)}`, { method: "DELETE" });
}
