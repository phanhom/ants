import { useEffect, useState } from "react";
import { getStatus } from "./api";

interface ColonyStatus {
  ok: boolean;
  root_agent_id: string;
  timestamp: string;
  waiting_for_approval: boolean;
  ants: Array<{
    agent_id: string;
    role: string;
    ok: boolean;
    lifecycle?: string;
    pending_todos: number;
    container_state?: string;
    base_url?: string;
  }>;
}

export default function ColonyOverview() {
  const [data, setData] = useState<ColonyStatus | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    getStatus("colony")
      .then((d) => setData(d as ColonyStatus))
      .catch((e) => setErr(String(e)));
  }, []);

  if (err) return <div className="text-red-400">Error: {err}</div>;
  if (!data) return <div className="text-gray-500">Loading…</div>;

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-4">Colony</h1>
      <div className="mb-4 p-4 rounded-lg bg-gray-800/50 border border-gray-700">
        <p className="text-sm text-gray-400">Root</p>
        <p className="font-medium">{data.root_agent_id}</p>
        <p className="text-xs text-gray-500 mt-1">{new Date(data.timestamp).toLocaleString()}</p>
        {data.waiting_for_approval && (
          <p className="text-amber-400 text-sm mt-2">Waiting for approval</p>
        )}
      </div>
      <h2 className="text-lg font-medium mb-2">Agents</h2>
      <div className="grid gap-3">
        {data.ants.map((ant) => (
          <div
            key={ant.agent_id}
            className="p-4 rounded-lg bg-gray-800/50 border border-gray-700 flex items-center justify-between"
          >
            <div>
              <p className="font-medium">{ant.agent_id}</p>
              <p className="text-sm text-gray-500">{ant.role}</p>
              {ant.pending_todos > 0 && (
                <p className="text-xs text-amber-400 mt-1">{ant.pending_todos} pending todos</p>
              )}
            </div>
            <div className="text-right text-sm">
              <span className={ant.ok ? "text-green-500" : "text-red-400"}>
                {ant.ok ? "OK" : "Error"}
              </span>
              {ant.container_state && (
                <p className="text-gray-500">{ant.container_state}</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
