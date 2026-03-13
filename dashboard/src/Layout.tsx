import { Link, useLocation } from "react-router-dom";
import { type ReactNode, useEffect, useState } from "react";
import { getStatus, type RecursiveNode } from "./api";
import {
  LayoutDashboard,
  DollarSign,
  GitBranch,
  FileText,
  Activity,
  HardDrive,
  ChevronRight,
  Bot,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { to: "/", icon: LayoutDashboard, label: "Overview" },
  { to: "/costs", icon: DollarSign, label: "Costs" },
  { to: "/tasks", icon: GitBranch, label: "Tasks" },
  { to: "/reports", icon: FileText, label: "Reports" },
  { to: "/traces", icon: Activity, label: "Traces" },
  { to: "/artifacts", icon: HardDrive, label: "Artifacts" },
];

function NavLink({ to, icon: Icon, label }: { to: string; icon: React.ComponentType<{ className?: string }>; label: string }) {
  const loc = useLocation();
  const active = to === "/" ? loc.pathname === "/" : loc.pathname.startsWith(to);
  return (
    <Link
      to={to}
      className={cn(
        "flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] font-medium transition-colors",
        active
          ? "bg-white/[0.08] text-white"
          : "text-gray-400 hover:bg-white/[0.04] hover:text-gray-200",
      )}
    >
      <Icon className="h-4 w-4 shrink-0" />
      {label}
    </Link>
  );
}

function AgentNode({ node, depth = 0 }: { node: RecursiveNode; depth?: number }) {
  const loc = useLocation();
  const active = loc.pathname === `/agent/${node.self.agent_id}`;
  const [open, setOpen] = useState(depth < 1);
  const hasSubs = node.subordinates?.length > 0;

  return (
    <div>
      <div className="flex items-center">
        {hasSubs && (
          <button
            onClick={() => setOpen(!open)}
            className="p-0.5 text-gray-600 hover:text-gray-400 transition-colors"
          >
            <ChevronRight className={cn("h-3 w-3 transition-transform", open && "rotate-90")} />
          </button>
        )}
        {!hasSubs && <span className="w-4" />}
        <Link
          to={`/agent/${node.self.agent_id}`}
          className={cn(
            "flex-1 truncate rounded-md px-2 py-1 text-[12px] transition-colors",
            active
              ? "bg-white/[0.08] text-white"
              : "text-gray-500 hover:bg-white/[0.04] hover:text-gray-300",
          )}
        >
          <span className={cn("inline-block h-1.5 w-1.5 rounded-full mr-1.5", node.self.ok ? "bg-emerald-500" : "bg-red-400")} />
          {node.self.agent_id}
        </Link>
      </div>
      {hasSubs && open && (
        <div className="ml-3 border-l border-border pl-1">
          {node.subordinates.map((sub) => (
            <AgentNode key={sub.self.agent_id} node={sub} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function Layout({ children }: { children: ReactNode }) {
  const [tree, setTree] = useState<RecursiveNode | null>(null);

  useEffect(() => {
    getStatus("subtree")
      .then((data) => setTree(data as RecursiveNode))
      .catch(() => {});
  }, []);

  return (
    <div className="flex h-screen overflow-hidden">
      <aside className="w-56 shrink-0 flex flex-col border-r border-border bg-[#010409]">
        {/* Brand */}
        <div className="px-4 pt-5 pb-4">
          <Link to="/" className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent/20">
              <Bot className="h-4 w-4 text-accent" />
            </div>
            <span className="text-[15px] font-semibold text-white tracking-tight">Ants</span>
          </Link>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto px-2 pb-4 space-y-0.5">
          <p className="section-title px-3 mb-2">Navigation</p>
          {NAV_ITEMS.map((item) => (
            <NavLink key={item.to} {...item} />
          ))}

          {tree && (
            <div className="mt-6">
              <p className="section-title px-3 mb-2">Agents</p>
              <AgentNode node={tree} />
            </div>
          )}
        </nav>

        {/* Footer */}
        <div className="border-t border-border px-4 py-3">
          <p className="text-[11px] text-gray-600">Ants Colony Dashboard</p>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto bg-[#0d1117]">
        <div className="mx-auto max-w-6xl px-6 py-6">
          {children}
        </div>
      </main>
    </div>
  );
}
