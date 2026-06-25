import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { MessageSquare, Users, Bell, CheckCircle } from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { StatsDTO } from "@/types/stats";

interface StatsDashboardProps {
  stats: StatsDTO | null;
  isLoading?: boolean;
  trendData?: { time: string; count: number }[];
}

interface TrendTooltipProps {
  active?: boolean;
  payload?: Array<{ value: number }>;
  label?: string;
}

function TrendTooltip({ active, payload, label }: TrendTooltipProps) {
  if (active && payload && payload.length > 0) {
    return (
      <div
        style={{
          background: "hsl(222.2 47.4% 11.2%)",
          border: "1px solid hsl(217.2 32.6% 17.5%)",
          borderRadius: "0.5rem",
          padding: "4px 8px",
          fontSize: "12px",
        }}
      >
        <span style={{ color: "hsl(210 40% 98%)" }}>{label}: </span>
        <span style={{ color: "hsl(217.2 91.5% 59.8%)" }}>{payload[0].value}</span>
      </div>
    );
  }
  return null;
}

function StatsDashboard({ stats, isLoading = false, trendData = [] }: StatsDashboardProps) {
  if (isLoading) {
    return (
      <Card data-testid="stats-zone" className="h-full">
        <CardHeader>
          <CardTitle className="text-lg">统计仪表盘</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-12 w-32" />
          <Skeleton className="h-6 w-full" />
          <Skeleton className="h-8 w-24" />
          <div className="grid grid-cols-4 gap-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
          <Skeleton className="h-[120px] w-full" />
        </CardContent>
      </Card>
    );
  }

  if (!stats) {
    return (
      <Card data-testid="stats-zone" className="h-full">
        <CardHeader>
          <CardTitle className="text-lg">统计仪表盘</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-muted-foreground text-center py-8">暂无统计数据</div>
        </CardContent>
      </Card>
    );
  }

  const progressValue = (stats.total_comments / 500) * 100;
  const progressColorClass =
    stats.total_comments < 300
      ? "text-success"
      : stats.total_comments < 400
        ? "text-warning"
        : "text-destructive";

  const miniCards = [
    { icon: MessageSquare, value: stats.total_comments, label: "总评论" },
    { icon: Users, value: stats.team_online_count, label: "在线组员" },
    { icon: Bell, value: stats.pending_alerts, label: "待处理告警" },
    { icon: CheckCircle, value: stats.executed_actions, label: "已执行操作" },
  ];

  return (
    <Card data-testid="stats-zone" className="h-full">
      <CardHeader>
        <CardTitle className="text-lg">统计仪表盘</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Big number */}
        <div className="flex items-baseline gap-2">
          <div className="text-4xl font-bold tabular-nums text-foreground">
            {stats.team_hot_count}
          </div>
          <span className="text-muted-foreground text-sm">
            热评 ({(stats.hot_ratio * 100).toFixed(1)}%)
          </span>
        </div>

        {/* Progress bar */}
        <div className="space-y-1">
          <div className="flex justify-between text-sm">
            <span>评论配额</span>
            <span className="font-mono tabular-nums">
              {stats.total_comments}/500
            </span>
          </div>
          <div className={progressColorClass}>
            <Progress value={progressValue} className="w-full" />
          </div>
        </div>

        {/* Timer */}
        <div className="font-mono text-2xl tabular-nums">
          {stats.elapsed_time}
        </div>

        {/* Mini stat cards */}
        <div className="grid grid-cols-4 gap-2">
          {miniCards.map((card) => {
            const Icon = card.icon;
            return (
              <Card key={card.label} className="p-3">
                <div className="flex flex-col items-center gap-1">
                  <Icon className="h-4 w-4 text-muted-foreground" />
                  <div className="text-2xl font-bold tabular-nums">{card.value}</div>
                  <div className="text-muted-foreground text-xs">{card.label}</div>
                </div>
              </Card>
            );
          })}
        </div>

        {/* Trend chart */}
        {trendData.length > 0 ? (
          <ResponsiveContainer width="100%" height={120}>
            <LineChart data={trendData}>
              <XAxis dataKey="time" hide />
              <YAxis hide />
              <Tooltip content={<TrendTooltip />} />
              <Line
                type="monotone"
                dataKey="count"
                stroke="hsl(217.2 91.5% 59.8%)"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <Skeleton className="h-[120px] w-full" />
        )}
      </CardContent>
    </Card>
  );
}

export default StatsDashboard;
