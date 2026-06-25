import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
} from "@/components/ui/table";
import type { CommentDTO } from "@/types/comment";

interface HotCommentLeaderboardProps {
  comments: CommentDTO[];
  teamUids: string[];
  isLoading?: boolean;
}

function getRankBadgeClass(rank: number): string {
  if (rank === 1) return "bg-yellow-500/20 text-yellow-400 border-yellow-500/40";
  if (rank === 2) return "bg-gray-300/20 text-gray-300 border-gray-300/40";
  if (rank === 3) return "bg-orange-700/20 text-orange-600 border-orange-700/40";
  return "";
}

function HotCommentLeaderboard({ comments, teamUids, isLoading = false }: HotCommentLeaderboardProps) {
  return (
    <Card data-testid="hot-comments-zone" className="h-full">
      <CardHeader>
        <CardTitle className="text-lg">热评排行榜</CardTitle>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[calc(100%-3rem)]">
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : comments.length === 0 ? (
            <div className="text-muted-foreground text-center py-8">暂无热评数据</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-16">排名</TableHead>
                  <TableHead className="w-10">头像</TableHead>
                  <TableHead>用户</TableHead>
                  <TableHead>评论</TableHead>
                  <TableHead className="text-right">点赞</TableHead>
                  <TableHead className="text-center">状态</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {comments.map((comment) => {
                  const isTeam = teamUids.includes(comment.user_uid) || comment.is_team_member;
                  return (
                    <TableRow
                      key={comment.id || comment.weibo_comment_id}
                      data-testid="comment-row"
                      className={isTeam ? "bg-success/10 border-l-2 border-success" : ""}
                    >
                      <TableCell>
                        <Badge
                          variant={comment.rank <= 3 ? "default" : "outline"}
                          className={getRankBadgeClass(comment.rank)}
                        >
                          #{comment.rank}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Avatar className="h-8 w-8">
                          <AvatarImage src={undefined} alt={comment.user_name} />
                          <AvatarFallback className="text-xs">
                            {comment.user_name?.charAt(0) ?? "?"}
                          </AvatarFallback>
                        </Avatar>
                      </TableCell>
                      <TableCell className="font-medium text-sm">
                        {comment.user_name}
                        {isTeam && (
                          <Badge variant="destructive" className="ml-1 text-xs">
                            组员
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell className="max-w-[200px] truncate text-sm text-muted-foreground">
                        {comment.content}
                      </TableCell>
                      <TableCell className="text-right">
                        <span className="font-mono tabular-nums">{comment.like_count}</span>
                      </TableCell>
                      <TableCell className="text-center">
                        {comment.is_hot ? (
                          <Badge variant="destructive">🔥热评</Badge>
                        ) : (
                          <Badge variant="secondary">正常</Badge>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  );
}

export default HotCommentLeaderboard;
