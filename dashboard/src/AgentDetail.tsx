import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getStatus, postInstruction } from "./api";

interface WorkSnapshot {
  todos?: Array<{ title?: string; status?: string }>;
  reports?: unknown[];
  recent_aip?: unknown[];
}

interface SingleAntStatus {
  agent_id: string;
  role: string;
  ok: boolean;
  pending_todos: number;
  container_state?: string;
  last_seen_at?: string;
  work?: WorkSnapshot;
  base_url?: string;
}

export default function AgentDetail() {
  const { agentId } = useParams<{ agentId: string }>();
  const [status, setStatus] = useState<SingleAntStatus | null>(null);
  const [colony, setColony] = useState<{ ants: SingleAntStatus[] } | null>(null);
  const [instruction, setInstruction] = useState("");
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!agentId) return;
    getStatus("colony")
      .then((d) => {
        setColony(d as { ants: SingleAntStatus[] });
        const ant = (d as { ants: SingleAntStatus[] }).ants?.find((a) => a.agent_id === agentId);
        if (ant) setStatus(ant);
      })
      .catch((e) => setErr(String(e)));
  }, [agentId]);

  const handleSend = async () => {
    if (!instruction.trim() || sending) return;
    setSending(true);
    setErr(null);
    setSent(null);
    try {
      await postInstruction(instruction);
      setSent("Sent.");
      setInstruction("");
    } catch (e) {
      setErr(String(e));
    } finally {
      setSending(false);
    }
  };

  if (!agentId) return <div>No agent</div>;
  if (err && !status) return <div className="text-red-400">Error: {err}</div>;
  if (!status && !colony?.ants?.length) return <div className="text-gray-500">Loading…</div>;

  const ant = status ?? colony!.ants.find((a) => a.agent_id === agentId);

  return (
    <div>
      <div className="mb-4">
        <Link to="/" className="text-sm text-gray-500 hover:text-gray-300">← Colony</Link>
      </div>
      <h1 className="text-2xl font-semibold mb-4">{ant?.agent_id ?? agentId}</h1>
      {!ant && <div className="text-gray-500">Agent not in colony status.</div>}
      {ant && (
        <>
          <div className="mb-6 p-4 rounded-lg bg-gray-800/50 border border-gray-700">
            <p className="text-sm text-gray-500">Role</p>
            <p className="font-medium">{ant.role}</p>
            <p className="text-sm mt-2">
              <span className={ant.ok ? "text-green-500" : "text-red-400"}>{ant.ok ? "OK" : "Error"}</span>
              {ant.container_state && ` · ${ant.container_state}`}
              {ant.last_seen_at && ` · Last seen ${new Date(ant.last_seen_at).toLocaleString()}`}
            </p>
            {ant.pending_todos > 0 && (
              <p className="text-amber-400 text-sm mt-1">{ant.pending_todos} pending todos</p>
            )}
          </div>
          {ant.work && (
            <div className="mb-6">
              <h2 className="text-lg font-medium mb-2">Work</h2>
              {ant.work.todos?.length ? (
                <ul className="list-disc pl-5 space-y-1 text-sm">
                  {ant.work.todos.slice(0, 10).map((t, i) => (
                    <li key={i}>{t.title ?? JSON.stringify(t)} — {t.status ?? "—"}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-gray-500 text-sm">No todos</p>
              )}
            </div>
          )}
          <div className="p-4 rounded-lg bg-gray-800/50 border border-gray-700">
            <h2 className="text-lg font-medium mb-2">Send instruction</h2>
            <p className="text-sm text-gray-500 mb-2">Instruction is sent to the queen as user_instruction (queen may delegate).</p>
            <textarea
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              placeholder="Your instruction…”
              className="w-full h-24 px-3 py-2 rounded bg-gray-900 border border-gray-700 text-sm resize-none"
            />
            <div className="mt-2 flex items-center gap-2">
              <button
                onClick={handleSend}
                disabled={sending || !instruction.trim()}
                className="px-4 py-2 rounded bg-blue-600 text-white text-sm disabled:opacity-50"
              >
                {sending ? "Sending…" : "Send"}
              </button>
              {sent && <span className="text-green-400 text-sm">{sent}</span>}
            </div>
            {err && <p className="text-red-400 text-sm mt-2">{err}</p>}
          </div>
        </>
      )}
    </div>
  );
}
