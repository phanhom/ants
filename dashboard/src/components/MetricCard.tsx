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
    <Card className={cn("group transition-all hover:border-border-strong", className)}>
      <div className="flex items-start justify-between">
        <div>
          <CardTitle>{title}</CardTitle>
          <CardContent>
            <p className="metric-value mt-1">{value}</p>
            {subtitle && (
              <p className="mt-1 text-xs text-gray-500">{subtitle}</p>
            )}
          </CardContent>
        </div>
        <div className="rounded-lg bg-white/[0.04] p-2">
          <Icon className="h-4 w-4 text-gray-500 transition-colors group-hover:text-accent" />
        </div>
      </div>
    </Card>
  );
}
