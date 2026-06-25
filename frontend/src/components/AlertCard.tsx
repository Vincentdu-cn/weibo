import { useState } from "react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import type { AlertDTO } from "@/types/alert";
import type { AccountDTO } from "@/types/account";

interface AlertCardProps {
  alert: AlertDTO;
  accounts?: AccountDTO[];
  onExecute?: (alertId: number, comment: string, accountIds: number[]) => Promise<void>;
}

function AlertCard({ alert, accounts = [], onExecute }: AlertCardProps) {
  const [commentText, setCommentText] = useState("");
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const canSubmit = commentText.trim() !== "" && selectedIds.length > 0 && !isSubmitting;

  const toggleAccount = (id: number) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  };

  const handleExecute = async () => {
    if (!canSubmit || !onExecute) return;
    setIsSubmitting(true);
    try {
      await onExecute(alert.id, commentText, selectedIds);
      toast.success("支援已执行");
      setCommentText("");
      setSelectedIds([]);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      toast.error(`执行失败: ${msg}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Card data-testid="alert-card" className="mt-2">
      <CardHeader>
        <CardTitle className="text-sm">
          {alert.message}
          <Badge variant="destructive" className="ml-2 text-xs">
            {alert.alert_type}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Comment input */}
        <div className="space-y-1">
          <Textarea
            data-testid="comment-input"
            placeholder="输入支援评论内容..."
            maxLength={140}
            value={commentText}
            onChange={(e) => setCommentText(e.target.value)}
          />
          <span className="text-muted-foreground text-xs">
            {commentText.length}/140
          </span>
        </div>

        {/* Account selection */}
        <div className="space-y-1">
          {accounts.map((account) => (
            <div key={account.id} className="flex items-center gap-2">
              <Checkbox
                data-testid={`account-checkbox-${account.id}`}
                checked={selectedIds.includes(account.id)}
                onCheckedChange={() => toggleAccount(account.id)}
              />
              <Avatar className="h-6 w-6">
                <AvatarImage src={account.avatar_url ?? undefined} alt={account.nickname} />
                <AvatarFallback className="text-xs">
                  {account.nickname?.charAt(0) ?? "?"}
                </AvatarFallback>
              </Avatar>
              <Label className="text-sm cursor-pointer">
                {account.nickname}
                <span
                  className={`inline-block w-2 h-2 rounded-full ml-2 ${
                    account.status === "active" ? "bg-success" : "bg-muted-foreground"
                  }`}
                />
              </Label>
            </div>
          ))}
        </div>

        {/* Action buttons */}
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            data-testid="like-support-btn"
            disabled={!canSubmit}
            onClick={handleExecute}
          >
            {isSubmitting ? "执行中..." : "点赞支援"}
          </Button>
          <Button
            variant="default"
            size="sm"
            data-testid="comment-support-btn"
            disabled={!canSubmit}
            onClick={handleExecute}
          >
            {isSubmitting ? "执行中..." : "评论支援"}
          </Button>
          <Button
            variant="default"
            size="sm"
            data-testid="both-support-btn"
            disabled={!canSubmit}
            onClick={handleExecute}
          >
            {isSubmitting ? "执行中..." : "两者都要"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export default AlertCard;
