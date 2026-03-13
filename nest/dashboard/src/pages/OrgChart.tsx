import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { getStatus, type RecursiveNode } from "@/api";
import { StatusBadge, StatusDot } from "@/components/StatusBadge";
import { Skeleton } from "@/components/ui/skeleton";
import { ChevronRight, Search } from "lucide-react";
import { cn } from "@/lib/utils";

function OrgTreeNode({ node, depth }: { node: RecursiveNode; depth: number }) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(true);
  const hasSubs = node.subordinates?.length > 0;
  const isExplorer = node.self.agent_id === "explorer";

  return (
    <div>
      <Link
        to={`/agent/${node.self.agent_id}`}
        className="group flex items-center gap-3 rounded-lg border border-border bg-surface p-4 transition-all hover:border-muted-foreground/30"
        style={{ marginLeft: depth * 32 }}
      >
        {/* Expand toggle */}
        <div className="w-5 flex items-center justify-center shrink-0">
          {hasSubs ? (
            <button
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setExpanded(!expanded);
              }}
              className="text-muted-foreground hover:text-foreground transition-colors"
            >
              <ChevronRight className={cn("h-4 w-4 transition-transform", expanded && "rotate-90")} />
            </button>
          ) : (
            <span className="h-4 w-4" />
          )}
        </div>

        {/* Status dot */}
        <StatusDot ok={node.self.ok} />

        {/* Name and role */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-foreground">{node.self.agent_id}</span>
            {isExplorer && (
              <span className="inline-flex items-center gap-1 rounded-md bg-blue-500/10 border border-blue-500/20 px-1.5 py-0.5 text-[10px] font-semibold text-blue-600 dark:text-blue-400">
                <Search className="h-2.5 w-2.5" />
                {t("org.dispatcher")}
              </span>
            )}
          </div>
          <p className="text-[13px] text-muted-foreground truncate mt-0.5">{node.self.role}</p>
        </div>

        {/* Status badge */}
        <StatusBadge status={node.self.lifecycle ?? "idle"} />

        {/* Pending count */}
        {node.self.pending_tasks > 0 && (
          <span className="text-xs font-medium text-amber-600 dark:text-amber-400">
            {node.self.pending_tasks} {t("agent.pending")}
          </span>
        )}
      </Link>

      {/* Children */}
      {hasSubs && expanded && (
        <div className="mt-2 space-y-2">
          {node.subordinates.map((sub) => (
            <OrgTreeNode
              key={sub.self.agent_id}
              node={sub}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function OrgChart() {
  const { t } = useTranslation();

  const { data: tree, isLoading } = useQuery({
    queryKey: ["status", "subtree"],
    queryFn: () => getStatus("subtree") as Promise<RecursiveNode>,
    refetchInterval: 15_000,
  });

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48 rounded-md" />
        <div className="space-y-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-20 rounded-lg" style={{ marginLeft: i === 0 ? 0 : 32 }} />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-4xl mx-auto">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">{t("org.title")}</h1>
        <p className="mt-1.5 text-sm text-muted-foreground font-medium">{t("org.subtitle")}</p>
      </div>

      {tree ? (
        <div className="space-y-2">
          <OrgTreeNode node={tree} depth={0} />
        </div>
      ) : (
        <p className="text-sm text-muted-foreground py-12 text-center">{t("org.no_data")}</p>
      )}
    </div>
  );
}
