import { cn } from "@/lib/utils";
import { Card, CardTitle, CardContent } from "@/components/ui/card";
import type { LucideIcon } from "lucide-react";

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  trend?: "up" | "down" | "neutral";
  className?: string;
}

export function MetricCard({ title, value, subtitle, icon: Icon, className }: MetricCardProps) {
  return (
    <Card className={cn("group transition-all hover:border-border", "shadow-none border border-border bg-surface", className)}>
      <div className="flex items-start justify-between">
        <div>
          <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wider">{title}</CardTitle>
          <CardContent className="p-0 mt-3">
            <p className="text-3xl font-semibold tracking-tight text-foreground">{value}</p>
            {subtitle && (
              <p className="mt-1.5 text-xs text-muted-foreground font-medium">{subtitle}</p>
            )}
          </CardContent>
        </div>
        <div className="rounded-md bg-muted p-2">
          <Icon className="h-4 w-4 text-muted-foreground transition-colors group-hover:text-foreground" />
        </div>
      </div>
    </Card>
  );
}
