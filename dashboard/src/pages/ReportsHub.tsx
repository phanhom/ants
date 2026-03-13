import { useEffect, useState } from "react";
import { getReports, type ReportEntry } from "@/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { formatRelativeTime } from "@/lib/utils";
import { FileText, Clock } from "lucide-react";
import { cn } from "@/lib/utils";

function ReportCard({ report }: { report: ReportEntry }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <Card
      className={cn(
        "cursor-pointer transition-all hover:border-border-strong",
        expanded && "border-border-strong",
      )}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1">
            <FileText className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
            <span className="text-sm font-medium text-white truncate">{report.title}</span>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="muted">{report.agent_id}</Badge>
            <Badge variant={report.status === "final" ? "success" : "default"}>{report.status}</Badge>
          </div>
        </div>
        <span className="shrink-0 text-[11px] text-gray-600">{formatRelativeTime(report.ts)}</span>
      </div>

      {expanded && report.body && (
        <div className="mt-4 border-t border-border pt-3">
          <div className="prose prose-invert prose-sm max-w-none text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">
            {report.body}
          </div>
        </div>
      )}
    </Card>
  );
}

export default function ReportsHub() {
  const [reports, setReports] = useState<ReportEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("");
  const [dbHint, setDbHint] = useState<string | null>(null);

  useEffect(() => {
    getReports({ limit: 100 })
      .then((r) => {
        setReports(r.reports ?? []);
        if (!r.db_configured) setDbHint(r.message ?? "Database not configured");
      })
      .catch(() => setDbHint("Failed to load reports"))
      .finally(() => setLoading(false));
  }, []);

  const filtered = filter
    ? reports.filter((r) => r.agent_id.includes(filter) || r.title.toLowerCase().includes(filter.toLowerCase()))
    : reports;

  if (loading) {
    return (
      <div className="space-y-6 animate-fade-in">
        <Skeleton className="h-8 w-48" />
        <div className="grid gap-3 md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24" />)}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-fade-in">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Reports</h1>
          <p className="mt-1 text-sm text-gray-500">{reports.length} reports</p>
        </div>
        <input
          type="text"
          placeholder="Filter by agent or title..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-gray-300 placeholder:text-gray-600 w-64"
        />
      </div>

      {dbHint && (
        <div className="glass-card border-amber-500/20 bg-amber-500/5 p-4 text-sm text-amber-300">{dbHint}</div>
      )}

      {filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-gray-600">
          <Clock className="h-8 w-8 mb-3" />
          <p className="text-sm">{reports.length ? "No matches" : "No reports yet"}</p>
        </div>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {filtered.map((r, i) => (
            <ReportCard key={`${r.ts}-${i}`} report={r} />
          ))}
        </div>
      )}
    </div>
  );
}
