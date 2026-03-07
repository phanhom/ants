import { Link, useLocation } from "react-router-dom";
import { ReactNode, useEffect, useState } from "react";
import { getStatus } from "./api";

interface RecursiveNode {
  self: { agent_id: string; role: string };
  subordinates: RecursiveNode[];
}

function SidebarTree({ node, depth = 0 }: { node: RecursiveNode; depth?: number }) {
  const loc = useLocation();
  const active = loc.pathname === `/agent/${node.self.agent_id}`;

  return (
    <div className="pl-2">
      <Link
        to={`/agent/${node.self.agent_id}`}
        className={`block py-1.5 px-2 rounded text-sm truncate ${active ? "bg-gray-700 text-white" : "text-gray-300 hover:bg-gray-800"}`}
      >
        <span className="font-medium">{node.self.agent_id}</span>
        <span className="text-gray-500 ml-1">{node.self.role}</span>
      </Link>
      {node.subordinates?.length > 0 && (
        <div className="ml-2 border-l border-gray-700">
          {node.subordinates.map((sub) => (
            <SidebarTree key={sub.self.agent_id} node={sub} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function Layout({ children }: { children: ReactNode }) {
  const loc = useLocation();
  const [tree, setTree] = useState<RecursiveNode | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getStatus("subtree")
      .then((data) => setTree(data as RecursiveNode))
      .catch((e) => setError(String(e)));
  }, []);

  return (
    <div className="flex h-screen">
      <aside className="w-64 shrink-0 border-r border-gray-800 bg-gray-900 flex flex-col">
        <div className="p-3 border-b border-gray-800">
          <Link to="/" className="text-lg font-semibold text-white">
            Ants
          </Link>
          <p className="text-xs text-gray-500 mt-0.5">Dashboard</p>
        </div>
        <nav className="p-2 flex-1 overflow-auto">
          <Link
            to="/"
            className={`block py-2 px-2 rounded text-sm mb-1 ${loc.pathname === "/" ? "bg-gray-700 text-white" : "text-gray-300 hover:bg-gray-800"}`}
          >
            Colony
          </Link>
          <Link
            to="/traces"
            className={`block py-2 px-2 rounded text-sm mb-2 ${loc.pathname === "/traces" ? "bg-gray-700 text-white" : "text-gray-300 hover:bg-gray-800"}`}
          >
          {error && <p className="text-red-400 text-xs px-2">{error}</p>}
          {tree && (
            <div className="mt-2">
              <p className="text-xs text-gray-500 px-2 mb-1">Agents</p>
              <SidebarTree node={tree} />
            </div>
          )}
        </nav>
      </aside>
      <main className="flex-1 overflow-auto p-6">{children}</main>
    </div>
  );
}
