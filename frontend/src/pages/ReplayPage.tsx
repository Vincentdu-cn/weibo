import { useEffect, useState, useCallback } from "react";
import { Play, Pause, SkipForward } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Skeleton } from "@/components/ui/skeleton";
import { Slider } from "@/components/ui/slider";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { apiGet } from "@/api/client";

// ── Types ────────────────────────────────────────────────────────────────────

interface SessionInfo {
  id: number;
  target_weibo_url: string;
  target_weibo_mid: string;
  started_at: string | null;
  ended_at: string | null;
  total_comments: number;
  status: string;
}

interface TimelineComment {
  comment_id: number;
  rank: number | null;
  user_uid: string;
  user_name: string;
  like_count: number;
  is_hot: boolean;
  is_team_member: boolean;
}

interface TimelineEntry {
  timestamp: string | null;
  comments: TimelineComment[];
}

interface AlertInfo {
  id: number;
  alert_type: string;
  message: string | null;
  status: string;
  account_uid: string | null;
  comment_id: number | null;
  created_at: string | null;
}

interface ActionInfo {
  id: number;
  account_uid: string;
  action_type: string;
  target_comment_id: string | null;
  content: string | null;
  status: string;
  created_at: string | null;
}

interface MemberPerformance {
  uid: string;
  name: string;
  like_count: number;
  comment_count: number;
  best_rank: number | null;
}

interface SessionSummary {
  total_comments: number;
  peak_hot_count: number;
  hot_ratio: number;
  action_success_rate: number;
  member_performance: MemberPerformance[];
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatTime(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return iso;
  }
}

function alertTypeLabel(t: string): string {
  const labels: Record<string, string> = {
    dropped_out: "掉出热评",
    rank_drop: "排名下降",
    low_likes: "点赞不足",
  };
  return labels[t] ?? t;
}

function actionTypeLabel(t: string): string {
  const labels: Record<string, string> = {
    like: "点赞",
    comment: "评论",
    reply: "回复",
  };
  return labels[t] ?? t;
}

// ── Component ────────────────────────────────────────────────────────────────

function ReplayPage() {
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string>("");
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [alerts, setAlerts] = useState<AlertInfo[]>([]);
  const [actions, setActions] = useState<ActionInfo[]>([]);
  const [summary, setSummary] = useState<SessionSummary | null>(null);

  const [loading, setLoading] = useState(true);
  const [dataLoading, setDataLoading] = useState(false);

  // Timeline playback
  const [sliderIndex, setSliderIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);

  // ── Fetch sessions on mount ──────────────────────────────────────────────

  const fetchSessions = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiGet<{ sessions: SessionInfo[] }>("/replay/sessions");
      setSessions(data.sessions);
    } catch {
      setSessions([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  // ── Fetch all data when a session is selected ────────────────────────────

  useEffect(() => {
    if (!selectedSessionId) return;

    setDataLoading(true);
    Promise.all([
      apiGet<{ timeline: TimelineEntry[] }>(
        `/replay/${selectedSessionId}/timeline`,
      ).catch(() => ({ timeline: [] })),
      apiGet<{ alerts: AlertInfo[] }>(
        `/replay/${selectedSessionId}/alerts`,
      ).catch(() => ({ alerts: [] })),
      apiGet<{ actions: ActionInfo[] }>(
        `/replay/${selectedSessionId}/actions`,
      ).catch(() => ({ actions: [] })),
      apiGet<SessionSummary>(
        `/replay/${selectedSessionId}/summary`,
      ).catch(() => null),
    ]).then(([tl, al, ac, sm]) => {
      setTimeline(tl.timeline);
      setAlerts(al.alerts);
      setActions(ac.actions);
      setSummary(sm);
      setSliderIndex(0);
      setIsPlaying(false);
      setDataLoading(false);
    });
  }, [selectedSessionId]);

  // ── Auto-play timeline ──────────────────────────────────────────────────

  useEffect(() => {
    if (!isPlaying || timeline.length === 0) return;

    const interval = setInterval(() => {
      setSliderIndex((prev) => {
        if (prev >= timeline.length - 1) {
          setIsPlaying(false);
          return prev;
        }
        return prev + 1;
      });
    }, 1500);

    return () => clearInterval(interval);
  }, [isPlaying, timeline.length]);

  // ── Derived data ─────────────────────────────────────────────────────────

  const currentTimelineEntry =
    timeline.length > 0 ? timeline[Math.min(sliderIndex, timeline.length - 1)] : null;

  const hasData = sessions.length > 0;
  const showEmpty = !loading && !hasData;

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div data-testid="replay-page" className="max-w-5xl mx-auto space-y-6">
      {/* Session Selector + Timeline Controls */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Play className="h-5 w-5" />
            Session Replay
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Session Selector */}
          <div className="space-y-2">
            <label className="text-sm font-medium">选择比赛场次</label>
            {loading ? (
              <Skeleton className="h-10 w-full" />
            ) : (
              <Select
                value={selectedSessionId}
                onValueChange={(v) => setSelectedSessionId(v)}
              >
                <SelectTrigger data-testid="session-select" className="w-full">
                  <SelectValue placeholder="选择比赛场次..." />
                </SelectTrigger>
                <SelectContent>
                  {sessions.map((s) => (
                    <SelectItem key={s.id} value={String(s.id)}>
                      {`Session #${s.id} — ${s.target_weibo_mid} (${s.status})`}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>

          {/* Timeline Slider + Controls */}
          {selectedSessionId && timeline.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-muted-foreground">
                  {currentTimelineEntry
                    ? `时间点 ${sliderIndex + 1}/${timeline.length} — ${formatTime(currentTimelineEntry.timestamp)}`
                    : "时间线"}
                </span>
                <div className="flex items-center gap-1">
                  <Button
                    data-testid="play-pause-btn"
                    variant="ghost"
                    size="icon"
                    onClick={() => setIsPlaying((p) => !p)}
                  >
                    {isPlaying ? (
                      <Pause className="h-4 w-4" />
                    ) : (
                      <Play className="h-4 w-4" />
                    )}
                  </Button>
                  <Button
                    data-testid="forward-btn"
                    variant="ghost"
                    size="icon"
                    onClick={() =>
                      setSliderIndex((prev) =>
                        Math.min(prev + 1, timeline.length - 1),
                      )
                    }
                    disabled={sliderIndex >= timeline.length - 1}
                  >
                    <SkipForward className="h-4 w-4" />
                  </Button>
                </div>
              </div>
              <Slider
                data-testid="timeline-slider"
                value={[sliderIndex]}
                onValueChange={(v) => setSliderIndex(v[0])}
                min={0}
                max={Math.max(0, timeline.length - 1)}
                step={1}
              />
            </div>
          )}
        </CardContent>
      </Card>

      {/* Empty state */}
      {showEmpty && (
        <div className="text-center py-16 text-muted-foreground">
          暂无回放数据
        </div>
      )}

      {/* Loading state */}
      {dataLoading && (
        <Card>
          <CardContent className="space-y-3 pt-6">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-[90%]" />
            <Skeleton className="h-8 w-[80%]" />
          </CardContent>
        </Card>
      )}

      {/* Tabs + Summary */}
      {selectedSessionId && !dataLoading && (
        <>
          {/* Summary Card */}
          {summary && (
            <Card data-testid="summary-card">
              <CardHeader>
                <CardTitle>比赛汇总</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mb-6">
                  <div className="space-y-1">
                    <p className="text-sm text-muted-foreground">总评论数</p>
                    <p className="text-2xl font-bold tabular-nums">
                      {summary.total_comments}
                    </p>
                  </div>
                  <div className="space-y-1">
                    <p className="text-sm text-muted-foreground">热评峰值</p>
                    <p className="text-2xl font-bold tabular-nums">
                      {summary.peak_hot_count}
                    </p>
                  </div>
                  <div className="space-y-1">
                    <p className="text-sm text-muted-foreground">热评占比</p>
                    <p className="text-2xl font-bold tabular-nums">
                      {(summary.hot_ratio * 100).toFixed(1)}%
                    </p>
                  </div>
                  <div className="space-y-1">
                    <p className="text-sm text-muted-foreground">操作成功率</p>
                    <p className="text-2xl font-bold tabular-nums">
                      {(summary.action_success_rate * 100).toFixed(1)}%
                    </p>
                  </div>
                </div>

                {/* Member Performance */}
                {summary.member_performance.length > 0 && (
                  <div className="space-y-3">
                    <p className="text-sm font-medium">组员表现</p>
                    <div className="flex flex-wrap gap-4">
                      {summary.member_performance.map((m) => (
                        <div
                          key={m.uid}
                          className="flex items-center gap-3 rounded-lg border border-border p-3"
                        >
                          <Avatar className="h-10 w-10">
                            <AvatarFallback>
                              {m.name?.slice(0, 2) ?? m.uid.slice(0, 2)}
                            </AvatarFallback>
                          </Avatar>
                          <div className="space-y-1">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium">{m.name}</span>
                              {m.best_rank !== null && (
                                <Badge variant="secondary">
                                  #{m.best_rank}
                                </Badge>
                              )}
                            </div>
                            <span className="text-xs text-muted-foreground">
                              {m.like_count} 赞 · {m.comment_count} 条评论
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Tabs */}
          <Tabs defaultValue="timeline">
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="timeline">时间线回放</TabsTrigger>
              <TabsTrigger value="alerts">告警历史</TabsTrigger>
              <TabsTrigger value="actions">操作日志</TabsTrigger>
            </TabsList>

            {/* Tab 1: Timeline */}
            <TabsContent value="timeline" className="mt-4">
              <Card>
                <CardContent className="pt-6">
                  {currentTimelineEntry && currentTimelineEntry.comments.length > 0 ? (
                    <Table data-testid="timeline-table">
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-16">排名</TableHead>
                          <TableHead className="w-12">头像</TableHead>
                          <TableHead>用户名</TableHead>
                          <TableHead className="text-right">点赞数</TableHead>
                          <TableHead className="text-center">是否热评</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {currentTimelineEntry.comments.map((c) => (
                          <TableRow key={c.comment_id}>
                            <TableCell className="font-mono">
                              {c.rank ?? "—"}
                            </TableCell>
                            <TableCell>
                              <Avatar className="h-8 w-8">
                                <AvatarFallback>
                                  {c.user_name?.slice(0, 2) ?? "??"}
                                </AvatarFallback>
                              </Avatar>
                            </TableCell>
                            <TableCell>
                              <div className="flex items-center gap-2">
                                {c.user_name}
                                {c.is_team_member && (
                                  <Badge variant="outline">组员</Badge>
                                )}
                              </div>
                            </TableCell>
                            <TableCell className="text-right tabular-nums">
                              {c.like_count}
                            </TableCell>
                            <TableCell className="text-center">
                              {c.is_hot ? (
                                <Badge>热评</Badge>
                              ) : (
                                <span className="text-muted-foreground">—</span>
                              )}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  ) : (
                    <div className="text-center py-8 text-muted-foreground">
                      暂无时间线数据
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            {/* Tab 2: Alerts */}
            <TabsContent value="alerts" className="mt-4">
              <Card>
                <CardContent className="pt-6">
                  {alerts.length > 0 ? (
                    <Table data-testid="alerts-table">
                      <TableHeader>
                        <TableRow>
                          <TableHead>时间</TableHead>
                          <TableHead>组员</TableHead>
                          <TableHead>告警类型</TableHead>
                          <TableHead>操作</TableHead>
                          <TableHead>结果</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {alerts.map((a) => (
                          <TableRow key={a.id}>
                            <TableCell className="text-sm text-muted-foreground">
                              {formatTime(a.created_at)}
                            </TableCell>
                            <TableCell className="font-mono text-sm">
                              {a.account_uid ?? "—"}
                            </TableCell>
                            <TableCell>
                              <Badge variant="destructive">
                                {alertTypeLabel(a.alert_type)}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-sm">
                              {a.message ?? "—"}
                            </TableCell>
                            <TableCell>
                              <Badge
                                variant={
                                  a.status === "confirmed"
                                    ? "default"
                                    : a.status === "dismissed"
                                      ? "outline"
                                      : "secondary"
                                }
                              >
                                {a.status}
                              </Badge>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  ) : (
                    <div className="text-center py-8 text-muted-foreground">
                      暂无告警记录
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            {/* Tab 3: Actions */}
            <TabsContent value="actions" className="mt-4">
              <Card>
                <CardContent className="pt-6">
                  {actions.length > 0 ? (
                    <Table data-testid="actions-table">
                      <TableHeader>
                        <TableRow>
                          <TableHead>时间</TableHead>
                          <TableHead>账号</TableHead>
                          <TableHead>操作类型</TableHead>
                          <TableHead>目标</TableHead>
                          <TableHead>结果</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {actions.map((a) => (
                          <TableRow key={a.id}>
                            <TableCell className="text-sm text-muted-foreground">
                              {formatTime(a.created_at)}
                            </TableCell>
                            <TableCell className="font-mono text-sm">
                              {a.account_uid}
                            </TableCell>
                            <TableCell>
                              <Badge variant="secondary">
                                {actionTypeLabel(a.action_type)}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-sm">
                              {a.content ?? a.target_comment_id ?? "—"}
                            </TableCell>
                            <TableCell>
                              <Badge
                                variant={
                                  a.status === "success"
                                    ? "default"
                                    : a.status === "failed"
                                      ? "destructive"
                                      : "outline"
                                }
                              >
                                {a.status === "success"
                                  ? "成功"
                                  : a.status === "failed"
                                    ? "失败"
                                    : a.status}
                              </Badge>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  ) : (
                    <div className="text-center py-8 text-muted-foreground">
                      暂无操作记录
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </>
      )}
    </div>
  );
}

export default ReplayPage;
