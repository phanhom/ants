import { useEffect, useState } from "react";
import { getTraces, type TraceEvent } from "./api";

export default function Traces() {
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [agentId, setAgentId] = useState("");
  const [traceType, setTraceType] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [dbHint, setDbHint] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    setErr(null);
    setDbHint(null);
    getTraces({
      agent_id: agentId || undefined,
      trace_type: traceType || undefined,
      limit: 100,
    })
      .then((r) => {
        setEvents(r.events ?? []);
        if (r.db_configured === false || r.message) {
          setDbHint(r.message || "Database not configured. Set MYSQL_* environment variables for the dashboard backend to see traces.");
        }
      })
      .catch((e) => setErr(String(e)))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-4">Traces</h1>
      <p className="text-sm text-gray-500 mb-4">Trace events from the database (read by dashboard backend).</p>
      <div className="flex gap-2 mb-4 flex-wrap">
        <input
          type="text"
          placeholder="agent_id"
          value={agentId}
          onChange={(e) => setAgentId(e.target.value)}
          className="px-3 py-2 rounded bg-gray-800 border border-gray-700 text-sm w-40"
        />
        <input
          type="text"
          placeholder="trace_type"
          value={traceType}
          onChange={(e) => setTraceType(e.target.value)}
          className="px-3 py-2 rounded bg-gray-800 border border-gray-700 text-sm w-40"
        />
        <button
          onClick={load}
          disabled={loading}
          className="px-4 py-2 rounded bg-gray-700 text-sm hover:bg-gray-600 disabled:opacity-50"
        >
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>
      {err && <p className="text-red-400 text-sm mb-2">{err}</p>}
      {dbHint && (
        <p className="mb-4 p-3 rounded bg-amber-900/50 border border-amber-700 text-amber-200 text-sm">
          {dbHint}
        </p>
      )}
      <div className="overflow-x-auto rounded border border-gray-700">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-800 text-left">
              <th className="p-2">ts</th>
              <th className="p-2">agent_id</th>
              <th className="p-2">trace_type</th>
              <th className="p-2">payload</th>
            </tr>
          </thead>
          <tbody>
            {events.length === 0 && !loading && (
              <tr><td colSpan={4} className="p-4 text-gray-500">No events (or DB not connected).</td></tr>
            )}
            {events.map((e, i) => (
              <tr key={i} className="border-t border-gray-700">
                <td className="p-2 text-gray-400">{e.ts}</td>
                <td className="p-2">{e.agent_id}</td>
                <td className="p-2">{e.trace_type}</td>
                <td className="p-2 max-w-md truncate" title={JSON.stringify(e.payload)}>
                  {typeof e.payload === "object" ? JSON.stringify(e.payload).slice(0, 120) + "…" : String(e.payload)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
