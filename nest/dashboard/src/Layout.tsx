import { Link, useLocation } from "react-router-dom";
import { type ReactNode, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
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
  Network,
  SquarePen,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { ThemeLangSwitcher } from "./components/ThemeLangSwitcher";
import { StatusDot } from "./components/StatusBadge";

function NavLink({ to, icon: Icon, label, badge }: { to: string; icon: React.ComponentType<{ className?: string }>; label: string; badge?: number }) {
  const loc = useLocation();
  const active = to === "/" ? loc.pathname === "/" : loc.pathname.startsWith(to);
  return (
    <Link
      to={to}
      className={cn(
        "flex items-center gap-2.5 rounded-md px-3 py-2 text-[13px] font-medium transition-colors",
        active
          ? "bg-muted text-foreground"
          : "text-muted-foreground hover:bg-surface-hover hover:text-foreground",
      )}
    >
      <Icon className="h-4 w-4 shrink-0" />
      <span className="flex-1">{label}</span>
      {badge !== undefined && badge > 0 && (
        <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-red-500/15 px-1.5 text-[11px] font-semibold text-red-600 dark:text-red-400">
          {badge}
        </span>
      )}
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
            className="p-0.5 text-muted-foreground hover:text-foreground transition-colors"
          >
            <ChevronRight className={cn("h-3 w-3 transition-transform", open && "rotate-90")} />
          </button>
        )}
        {!hasSubs && <span className="w-4" />}
        <Link
          to={`/agent/${node.self.agent_id}`}
          className={cn(
            "flex-1 flex items-center gap-2 truncate rounded-md px-2 py-1.5 text-[13px] font-medium transition-colors",
            active
              ? "bg-muted text-foreground"
              : "text-muted-foreground hover:bg-surface-hover hover:text-foreground",
          )}
        >
          <StatusDot ok={node.self.ok} className="h-1.5 w-1.5" />
          <span className="truncate">{node.self.agent_id}</span>
        </Link>
      </div>
      {hasSubs && open && (
        <div className="ml-3 border-l border-border pl-1 mt-0.5 space-y-0.5">
          {node.subordinates.map((sub) => (
            <AgentNode key={sub.self.agent_id} node={sub} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function Layout({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const [showInstruct, setShowInstruct] = useState(false);

  const { data: tree } = useQuery({
    queryKey: ["status", "subtree"],
    queryFn: () => getStatus("subtree") as Promise<RecursiveNode>,
    refetchInterval: 15_000,
  });

  const navItems = [
    { to: "/", icon: LayoutDashboard, label: t("nav.overview") },
    { to: "/org", icon: Network, label: t("nav.org") },
    { to: "/tasks", icon: GitBranch, label: t("nav.tasks"), badge: undefined as number | undefined },
    { to: "/costs", icon: DollarSign, label: t("nav.costs") },
    { to: "/reports", icon: FileText, label: t("nav.reports") },
    { to: "/traces", icon: Activity, label: t("nav.traces") },
    { to: "/artifacts", icon: HardDrive, label: t("nav.artifacts") },
  ];

  return (
    <div className="flex h-screen overflow-hidden bg-background text-foreground">
      <aside className="w-64 shrink-0 flex flex-col border-r border-border bg-surface">
        {/* Brand */}
        <div className="px-5 pt-6 pb-2 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2.5">
            <div className="flex h-6 w-6 items-center justify-center rounded-md bg-foreground">
              <Bot className="h-3.5 w-3.5 text-background" />
            </div>
            <div>
              <span className="text-sm font-semibold tracking-tight block leading-tight">{t("brand.title")}</span>
            </div>
          </Link>
        </div>

        {/* New Instruction */}
        <div className="px-3 py-2">
          <button
            onClick={() => setShowInstruct(!showInstruct)}
            className="flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-[13px] font-medium text-muted-foreground hover:bg-surface-hover hover:text-foreground transition-colors"
          >
            <SquarePen className="h-4 w-4" />
            {t("nav.new_instruction")}
          </button>
          {showInstruct && <InstructionInput onClose={() => setShowInstruct(false)} />}
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto px-3 pb-4 space-y-1">
          <p className="section-title px-2 mb-2 mt-2">{t("nav.navigation")}</p>
          {navItems.map((item) => (
            <NavLink key={item.to} {...item} />
          ))}

          {tree && (
            <div className="mt-6">
              <p className="section-title px-2 mb-2">{t("nav.agents")}</p>
              <AgentNode node={tree} />
            </div>
          )}
        </nav>

        {/* Footer */}
        <div className="border-t border-border p-4 flex items-center justify-between">
          <p className="text-[11px] text-muted-foreground font-medium">{t("brand.subtitle")}</p>
          <ThemeLangSwitcher />
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-5xl px-8 py-8">
          {children}
        </div>
      </main>
    </div>
  );
}

function InstructionInput({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const [value, setValue] = useState("");
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);

  const handleSend = async () => {
    if (!value.trim() || sending) return;
    setSending(true);
    try {
      const { postInstruction } = await import("./api");
      await postInstruction(value);
      setSent(true);
      setValue("");
      setTimeout(() => { setSent(false); onClose(); }, 1500);
    } catch {
      /* noop */
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="mt-2 px-1">
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={t("agent.instruction_placeholder")}
        className="w-full h-20 rounded-md border border-border bg-background px-3 py-2 text-[13px] text-foreground placeholder:text-muted-foreground resize-none focus:outline-none focus:ring-1 focus:ring-border"
        onKeyDown={(e) => { if (e.key === "Enter" && e.metaKey) handleSend(); }}
      />
      <div className="flex items-center gap-2 mt-1.5">
        <button
          onClick={handleSend}
          disabled={sending || !value.trim()}
          className="rounded-md bg-foreground px-3 py-1.5 text-xs font-medium text-background transition-colors hover:opacity-80 disabled:opacity-40"
        >
          {sending ? t("agent.sending") : t("agent.send")}
        </button>
        {sent && <span className="text-xs text-emerald-500 font-medium">{t("agent.instruction_sent")}</span>}
      </div>
    </div>
  );
}
