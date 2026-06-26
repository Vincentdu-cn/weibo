import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useHotComments } from "@/hooks/useHotComments";
import { useMemberStatus } from "@/hooks/useMemberStatus";
import { useStats } from "@/hooks/useStats";
import { useCompetitionStore } from "@/stores/competitionStore";
import { apiPost } from "@/api/client";
import {
  Flame,
  TrendingUp,
  Users,
  Activity,
  Clock,
  MessageSquare,
  ThumbsUp,
  CheckCircle2,
  Loader2,
} from "lucide-react";
import { useState, useCallback, useEffect } from "react";

interface BatchLikeProgress {
  current: number;
  total: number;
  current_comment_id: string;
  success: boolean;
  error: string | null;
  status: "running" | "done";
}

function DashboardPage() {
  const wsUrl = `ws://${window.location.host}/ws`;
  const { lastMessage, isConnected } = useWebSocket(wsUrl);
  const { comments, isLoading: commentsLoading } = useHotComments(lastMessage);
  const { members, isLoading: membersLoading } = useMemberStatus(lastMessage);
  const { stats, isLoading: statsLoading, trendData } = useStats(lastMessage);
  const { status } = useCompetitionStore();

  const [batchLikeRunning, setBatchLikeRunning] = useState(false);
  const [batchLikeProgress, setBatchLikeProgress] = useState<BatchLikeProgress | null>(null);
  const [batchLikeSuccessCount, setBatchLikeSuccessCount] = useState(0);
  const [batchLikeError, setBatchLikeError] = useState<string | null>(null);

  // Collect all comment IDs from all team members
  const allCommentIds = members.flatMap((m) => m.comments.map((c) => c.comment_id));
  const totalCommentCount = allCommentIds.length;

  // Listen for batch_like_progress WebSocket events
  useEffect(() => {
    if (!lastMessage) return;
    if (lastMessage.type === "batch_like_progress") {
      const data = lastMessage.data as unknown as BatchLikeProgress;
      setBatchLikeProgress(data);
      if (data.success) {
        setBatchLikeSuccessCount((prev) => prev + 1);
      }
      if (data.status === "done") {
        setBatchLikeRunning(false);
      }
    }
  }, [lastMessage]);

  const handleBatchLike = useCallback(async () => {
    if (allCommentIds.length === 0) return;

    setBatchLikeRunning(true);
    setBatchLikeSuccessCount(0);
    setBatchLikeProgress(null);
    setBatchLikeError(null);

    try {
      await apiPost("/actions/batch-like", { comment_ids: allCommentIds });
    } catch (err) {
      setBatchLikeRunning(false);
      setBatchLikeError(err instanceof Error ? err.message : "Batch like failed");
    }
  }, [allCommentIds]);

  const failCount = batchLikeProgress
    ? batchLikeProgress.current - batchLikeSuccessCount
    : 0;

  return (
    <div data-testid="dashboard-root" className="h-full flex flex-col">
      {/* Header bar */}
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <div className="flex items-center gap-3">
          <Badge variant={isConnected ? "default" : "destructive"}>
            {isConnected ? "WS Connected" : "WS Disconnected"}
          </Badge>
          <Badge variant={status === "running" ? "default" : "secondary"}>
            {status}
          </Badge>
        </div>
      </div>

      <div className="grid grid-cols-[2fr_1fr] grid-rows-2 gap-4 h-[calc(100vh-8rem)]">
        {/* ── Left-top: Hot Comments Leaderboard ── */}
        <Card data-testid="hot-comments-zone" className="row-start-1 col-start-1 overflow-hidden flex flex-col">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg flex items-center gap-2">
              <Flame className="h-5 w-5 text-orange-500" />
              Hot Comments Leaderboard
            </CardTitle>
          </CardHeader>
          <CardContent className="flex-1 overflow-hidden p-0">
            <ScrollArea className="h-full px-6 pb-4">
              {commentsLoading ? (
                <div className="space-y-2">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <Skeleton key={i} className="h-14 w-full" />
                  ))}
                </div>
              ) : comments.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">
                  No comments yet. Start a competition to see live data.
                </p>
              ) : (
                <div className="space-y-2">
                  {comments.slice(0, 20).map((comment) => (
                    <div
                      key={comment.weibo_comment_id}
                      className="flex items-start gap-3 rounded-lg border border-border/50 p-3 hover:bg-accent/50 transition-colors"
                    >
                      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-orange-400 to-red-500 flex items-center justify-center text-white text-sm font-bold">
                        {comment.rank}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-sm font-medium truncate">
                            {comment.user_name || "Unknown"}
                          </span>
                          {comment.is_team_member && (
                            <Badge variant="secondary" className="text-xs py-0 px-1.5">
                              Team
                            </Badge>
                          )}
                          {comment.is_hot && (
                            <Badge variant="destructive" className="text-xs py-0 px-1.5">
                              Hot
                            </Badge>
                          )}
                        </div>
                        <p className="text-sm text-muted-foreground line-clamp-2">
                          {comment.content || "(no content)"}
                        </p>
                      </div>
                      <div className="flex-shrink-0 text-right">
                        <div className="flex items-center gap-1 text-sm text-muted-foreground">
                          <TrendingUp className="h-3 w-3" />
                          {comment.like_count}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </ScrollArea>
          </CardContent>
        </Card>

        {/* ── Right-top: Statistics ── */}
        <Card data-testid="stats-zone" className="row-start-1 col-start-2">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg flex items-center gap-2">
              <Activity className="h-5 w-5 text-blue-500" />
              Statistics
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {statsLoading || !stats ? (
              <>
                <Skeleton className="h-16 w-full" />
                <Skeleton className="h-4 w-[60%]" />
                <Skeleton className="h-4 w-[80%]" />
              </>
            ) : (
              <>
                {/* Total Comments */}
                <div className="space-y-1">
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <MessageSquare className="h-4 w-4" />
                    <span className="text-xs">Total Comments</span>
                  </div>
                  <p className="text-2xl font-bold">{stats.total_comments}</p>
                </div>

                {/* Team Hot Count */}
                <div className="space-y-1">
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <Flame className="h-4 w-4" />
                    <span className="text-xs">Team in Hot</span>
                  </div>
                  <p className="text-2xl font-bold text-orange-500">
                    {stats.team_hot_count}
                    <span className="text-sm text-muted-foreground ml-1">
                      / {stats.team_online_count}
                    </span>
                  </p>
                </div>

                {/* Remaining Quota */}
                <div className="space-y-1">
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <span className="text-xs">Remaining Quota</span>
                  </div>
                  <p className="text-2xl font-bold text-green-500">
                    {stats.remaining_quota}
                  </p>
                </div>

                {/* Elapsed Time */}
                <div className="space-y-1">
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <Clock className="h-4 w-4" />
                    <span className="text-xs">Elapsed</span>
                  </div>
                  <p className="text-lg font-medium">{stats.elapsed_time}</p>
                </div>

                {/* Hot Ratio Progress */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground">Hot Ratio</span>
                    <span className="text-xs font-medium">
                      {(stats.hot_ratio * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div className="w-full bg-secondary rounded-full h-2 overflow-hidden">
                    <div
                      className="bg-orange-500 h-full transition-all duration-500"
                      style={{ width: `${Math.min(stats.hot_ratio * 100, 100)}%` }}
                    />
                  </div>
                </div>

                {/* Pending Alerts & Executed Actions */}
                <div className="grid grid-cols-2 gap-2 pt-2 border-t">
                  <div className="text-center">
                    <p className="text-xs text-muted-foreground">Pending Alerts</p>
                    <p className="text-lg font-bold text-yellow-500">{stats.pending_alerts}</p>
                  </div>
                  <div className="text-center">
                    <p className="text-xs text-muted-foreground">Actions Done</p>
                    <p className="text-lg font-bold text-green-500">{stats.executed_actions}</p>
                  </div>
                </div>

                {/* Trend mini chart */}
                {trendData.length > 1 && (
                  <div className="pt-2 border-t">
                    <p className="text-xs text-muted-foreground mb-1">Team Hot Trend</p>
                    <div className="flex items-end gap-0.5 h-8">
                      {trendData.map((pt, i) => (
                        <div
                          key={i}
                          className="flex-1 bg-blue-400/60 rounded-sm min-w-[2px]"
                          style={{
                            height: `${Math.min((pt.count / Math.max(...trendData.map(p => p.count), 1)) * 100, 100)}%`,
                          }}
                          title={`${pt.time}: ${pt.count}`}
                        />
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>

        {/* ── Left-bottom: Team Member Status ── */}
        <Card data-testid="member-status-zone" className="row-start-2 col-start-1 overflow-hidden flex flex-col">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg flex items-center gap-2">
              <Users className="h-5 w-5 text-indigo-500" />
              Team Member Status
            </CardTitle>
          </CardHeader>
          <CardContent className="flex-1 overflow-hidden p-0">
            <ScrollArea className="h-full px-6 pb-4">
              {membersLoading ? (
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                  {Array.from({ length: 8 }).map((_, i) => (
                    <Skeleton key={i} className="h-32 w-full" />
                  ))}
                </div>
              ) : members.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">
                  No team members yet. Start a competition to see live data.
                </p>
              ) : (
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                  {members.map((member, i) => (
                    <div
                      key={member.uid ?? i}
                      className={`rounded-lg border p-3 transition-all ${
                        member.in_hot
                          ? "border-green-400 bg-green-50 dark:bg-green-950/20"
                          : "border-border bg-card"
                      }`}
                    >
                      {/* Member header */}
                      <div className="flex items-center gap-2 mb-2">
                        <Avatar className="h-8 w-8 flex-shrink-0">
                          {member.avatar_url && (
                            <AvatarImage src={member.avatar_url} alt={member.nickname} />
                          )}
                          <AvatarFallback className="text-xs">
                            {member.nickname?.[0] ?? "?"}
                          </AvatarFallback>
                        </Avatar>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">
                            {member.nickname || "—"}
                          </p>
                          {member.in_hot && (
                            <Badge
                              variant="outline"
                              className="text-xs py-0 px-1.5 text-green-600 border-green-400"
                            >
                              Hot
                            </Badge>
                          )}
                        </div>
                      </div>

                      {/* Member stats */}
                      <div className="grid grid-cols-3 gap-1 mb-2 text-center">
                        <div>
                          <p className="text-xs text-muted-foreground">Comments</p>
                          <p className="text-sm font-semibold">{member.total_comments}</p>
                        </div>
                        <div>
                          <p className="text-xs text-muted-foreground">Likes</p>
                          <p className="text-sm font-semibold">{member.total_likes}</p>
                        </div>
                        <div>
                          <p className="text-xs text-muted-foreground">Best Rank</p>
                          <p className="text-sm font-semibold">
                            {member.best_rank !== null ? `#${member.best_rank}` : "—"}
                          </p>
                        </div>
                      </div>

                      {/* Comments list */}
                      {member.comments.length > 0 && (
                        <div className="space-y-1 pt-2 border-t">
                          {member.comments.slice(0, 3).map((comment) => (
                            <div
                              key={comment.comment_id}
                              className={`flex items-center gap-2 text-xs rounded px-1.5 py-1 ${
                                comment.is_hot
                                  ? "bg-green-100/50 dark:bg-green-950/30"
                                  : ""
                              }`}
                            >
                              <span className="flex-shrink-0 w-5 text-center font-medium text-muted-foreground">
                                #{comment.rank}
                              </span>
                              <p className="flex-1 truncate text-muted-foreground">
                                {comment.content || "(no content)"}
                              </p>
                              <span className="flex-shrink-0 flex items-center gap-0.5">
                                <TrendingUp className="h-3 w-3" />
                                {comment.like_count}
                              </span>
                            </div>
                          ))}
                          {member.comments.length > 3 && (
                            <p className="text-xs text-muted-foreground text-center pt-1">
                              +{member.comments.length - 3} more
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </ScrollArea>
          </CardContent>
        </Card>

        {/* ── Right-bottom: Batch Like Control ── */}
        <Card
          data-testid="batch-like-zone"
          className="row-start-2 col-start-2 overflow-hidden flex flex-col"
        >
          <CardHeader className="pb-3">
            <CardTitle className="text-lg flex items-center gap-2">
              <ThumbsUp className="h-5 w-5 text-blue-500" />
              Batch Like
            </CardTitle>
          </CardHeader>
          <CardContent className="flex-1 flex flex-col gap-4">
            {/* Batch Like Button */}
            <Button
              size="lg"
              className="w-full text-base font-semibold"
              disabled={batchLikeRunning || totalCommentCount === 0}
              onClick={handleBatchLike}
            >
              {batchLikeRunning ? (
                <>
                  <Loader2 className="h-5 w-5 mr-2 animate-spin" />
                  批量点赞中...
                </>
              ) : (
                <>
                  <ThumbsUp className="h-5 w-5 mr-2" />
                  批量点赞 ({totalCommentCount} 条评论)
                </>
              )}
            </Button>

            {/* Progress display */}
            {batchLikeProgress && (
              <div className="space-y-2">
                {batchLikeProgress.status === "running" ? (
                  <>
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-medium">
                        点赞中 {batchLikeProgress.current}/{batchLikeProgress.total}...
                      </span>
                      <span className="text-muted-foreground">
                        <span className="text-green-500">✓ {batchLikeSuccessCount}</span>
                        {"  "}
                        <span className="text-red-500">✗ {failCount}</span>
                      </span>
                    </div>
                    <Progress
                      value={
                        batchLikeProgress.total > 0
                          ? (batchLikeProgress.current / batchLikeProgress.total) * 100
                          : 0
                      }
                    />
                  </>
                ) : (
                  <div className="flex items-center gap-2 rounded-lg border border-green-400/50 bg-green-50 dark:bg-green-950/20 p-3">
                    <CheckCircle2 className="h-5 w-5 text-green-500 flex-shrink-0" />
                    <div>
                      <p className="text-sm font-medium text-green-700 dark:text-green-400">
                        完成 {batchLikeSuccessCount}/{batchLikeProgress.total} 成功
                      </p>
                      {failCount > 0 && (
                        <p className="text-xs text-muted-foreground">
                          {failCount} 失败
                        </p>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Error display */}
            {batchLikeError && (
              <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3">
                <p className="text-sm text-destructive">{batchLikeError}</p>
              </div>
            )}

            {/* Connection info */}
            <div className="mt-auto pt-2 border-t text-xs text-muted-foreground space-y-1">
              <div className="flex justify-between">
                <span>WebSocket:</span>
                <span>{isConnected ? "Connected" : "Disconnected"}</span>
              </div>
              <div className="flex justify-between">
                <span>Hot Comments:</span>
                <span>{comments.length}</span>
              </div>
              <div className="flex justify-between">
                <span>Team Members:</span>
                <span>{members.length}</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default DashboardPage;
