import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { formatRelativeTime } from "@/lib/utils";
import { StatusBadge, StatusDot } from "@/components/StatusBadge";
import type { SingleAntStatus } from "@/api";

export function ActiveAgentsPanel({ agents }: { agents: SingleAntStatus[] }) {
  const { t } = useTranslation();

  if (!agents.length) {
    return (
      <div className="flex items-center justify-center py-12 text-sm text-muted-foreground">
        {t("overview.no_agents")}
      </div>
    );
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {agents.map((a) => (
        <Link
          key={a.agent_id}
          to={`/agent/${a.agent_id}`}
          className="group flex flex-col gap-3 p-4 rounded-lg border border-border bg-surface transition-all hover:border-muted-foreground/30"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <StatusDot ok={a.ok} />
              <span className="text-sm font-semibold text-foreground truncate">{a.agent_id}</span>
            </div>
            <StatusBadge status={a.lifecycle ?? "idle"} />
          </div>

          <p className="text-[13px] text-muted-foreground leading-relaxed line-clamp-1">{a.role}</p>

          <div className="mt-auto flex items-center justify-between text-[11px] font-medium text-muted-foreground">
            {a.pending_tasks > 0 ? (
              <span className="text-amber-600 dark:text-amber-400">{a.pending_tasks} {t("agent.pending")}</span>
            ) : (
              <span>{t("agent.no_tasks")}</span>
            )}
            {a.last_seen_at && (
              <span>{formatRelativeTime(a.last_seen_at)}</span>
            )}
          </div>
        </Link>
      ))}
    </div>
  );
}
