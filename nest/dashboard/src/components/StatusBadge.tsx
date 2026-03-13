import { cn } from "@/lib/utils";

const statusColors: Record<string, string> = {
  running: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
  idle: "bg-muted text-muted-foreground border-border",
  failed: "bg-red-500/15 text-red-600 dark:text-red-400 border-red-500/20",
  degraded: "bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/20",
  blocked: "bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/20",
  starting: "bg-blue-500/15 text-blue-600 dark:text-blue-400 border-blue-500/20",
};

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  const colors = statusColors[status] || statusColors.idle;
  return (
    <span className={cn("inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium", colors, className)}>
      {status.replace("_", " ")}
    </span>
  );
}

export function StatusDot({ ok, className }: { ok: boolean; className?: string }) {
  return (
    <span className={cn("inline-block h-2 w-2 rounded-full shrink-0", ok ? "bg-emerald-500" : "bg-red-500", className)} />
  );
}
