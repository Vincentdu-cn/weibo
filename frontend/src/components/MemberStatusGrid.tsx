import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
  TooltipProvider,
} from "@/components/ui/tooltip";
import type { MemberGridItem } from "@/hooks/useMemberStatus";

interface MemberStatusGridProps {
  members: MemberGridItem[];
  isLoading?: boolean;
}

function StatusDot({ member }: { member: MemberGridItem }) {
  if (member.is_hot) {
    return (
      <span
        className="inline-block w-2 h-2 rounded-full bg-success animate-pulse"
        title="热评中"
      />
    );
  }
  if (member.comment_count > 0) {
    return (
      <span
        className="inline-block w-2 h-2 rounded-full bg-destructive animate-pulse"
        title="掉出热评"
      />
    );
  }
  return (
    <span
      className="inline-block w-2 h-2 rounded-full bg-muted-foreground"
      title="未评论"
    />
  );
}

function MemberStatusGrid({ members, isLoading = false }: MemberStatusGridProps) {
  return (
    <Card data-testid="member-status-zone" className="h-full">
      <CardHeader>
        <CardTitle className="text-lg">组员状态</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="grid grid-cols-5 gap-2">
            {Array.from({ length: 20 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        ) : members.length === 0 ? (
          <div className="text-muted-foreground text-center py-8">暂无组员数据</div>
        ) : (
          <div className="grid grid-cols-5 gap-2">
            {members.map((member, idx) => {
              const cardClass = member.is_hot
                ? "p-2 text-center border-success"
                : member.comment_count > 0
                  ? "p-2 text-center border-destructive"
                  : "p-2 text-center";
              return (
                <TooltipProvider key={member.uid ?? `empty-${idx}`}>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Card data-testid="member-card" className={cardClass}>
                        <div className="flex flex-col items-center gap-1">
                          <Avatar className="h-8 w-8">
                            <AvatarImage src={member.avatar_url ?? undefined} alt={member.nickname ?? ""} />
                            <AvatarFallback className="text-xs">
                              {member.nickname?.charAt(0) ?? "?"}
                            </AvatarFallback>
                          </Avatar>
                          <div className="text-xs truncate w-full text-center">
                            {member.nickname ?? "未登录"}
                          </div>
                          {member.current_rank !== null ? (
                            <Badge
                              variant={member.is_hot ? "destructive" : "outline"}
                              className="text-xs"
                            >
                              #{member.current_rank}
                            </Badge>
                          ) : null}
                          <div className="flex items-center gap-1">
                            <span className="font-mono tabular-nums text-xs">
                              {member.like_count ?? "-"}
                            </span>
                            <span className="text-xs text-muted-foreground">
                              {member.comment_count}条
                            </span>
                          </div>
                          <StatusDot member={member} />
                        </div>
                      </Card>
                    </TooltipTrigger>
                    <TooltipContent>
                      UID: {member.uid ?? "N/A"} | 点赞: {member.like_count ?? "N/A"}
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default MemberStatusGrid;
