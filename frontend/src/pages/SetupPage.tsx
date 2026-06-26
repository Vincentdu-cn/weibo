import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useNavigate, Link } from "react-router-dom";
import { toast } from "sonner";
import { Monitor, Users, Plus, Upload, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { useCompetitionStore } from "@/stores/competitionStore";
import {
  startCompetition,
  endCompetition,
  getCompetitionStatus,
} from "@/api/competition";
import { getAccounts } from "@/api/qr";
import {
  getTeamMembers,
  addTeamMember,
  batchAddTeamMembers,
  deleteTeamMember,
} from "@/api/teamMembers";
import type { TeamMember } from "@/api/teamMembers";
import type { AccountDTO } from "@/types/account";

// ── Form schema ───────────────────────────────────────────────────────────────

const setupSchema = z.object({
  weibo_url: z
    .string()
    .min(1, "URL is required")
    .url("Please enter a valid URL")
    .refine((val) => val.includes("weibo.com"), "URL must be a Weibo link"),
});

type SetupFormValues = z.infer<typeof setupSchema>;

// ── Component ─────────────────────────────────────────────────────────────────

function SetupPage() {
  const navigate = useNavigate();
  const { setWeiboUrl, setStatus, setSessionId } = useCompetitionStore();
  const [submitting, setSubmitting] = useState(false);
  const [endingCompetition, setEndingCompetition] = useState(false);
  const [accounts, setAccounts] = useState<AccountDTO[]>([]);
  const [selectedUids, setSelectedUids] = useState<string[]>([]);

  // ── Team member state ───────────────────────────────────────────────────────
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);
  const [newUid, setNewUid] = useState("");
  const [newNickname, setNewNickname] = useState("");
  const [batchText, setBatchText] = useState("");
  const [addingMember, setAddingMember] = useState(false);
  const [batchAdding, setBatchAdding] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const form = useForm<SetupFormValues>({
    resolver: zodResolver(setupSchema),
    defaultValues: { weibo_url: "" },
  });

  useEffect(() => {
    getAccounts()
      .then((data) => {
        setAccounts(data);
        setSelectedUids(data.map((a) => a.weibo_uid));
      })
      .catch(() => {
      });
    loadTeamMembers();
  }, []);

  // ── Team member handlers ────────────────────────────────────────────────────

  async function loadTeamMembers() {
    try {
      const data = await getTeamMembers();
      setTeamMembers(data);
    } catch {
    }
  }

  async function handleAddMember() {
    const uid = newUid.trim();
    const nickname = newNickname.trim();
    if (!uid || !nickname) return;
    setAddingMember(true);
    try {
      await addTeamMember(uid, nickname);
      toast.success("组员添加成功");
      setNewUid("");
      setNewNickname("");
      await loadTeamMembers();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "添加组员失败");
    } finally {
      setAddingMember(false);
    }
  }

  async function handleBatchAdd() {
    const lines = batchText
      .trim()
      .split("\n")
      .filter((l) => l.trim());
    const members: { weibo_uid: string; nickname: string }[] = [];
    for (const line of lines) {
      // Support "UID 昵称" or "UID,昵称" format
      const parts = line.includes(",")
        ? line.split(",")
        : line.split(/\s+/);
      if (parts.length >= 2) {
        const uid = parts[0].trim();
        const nickname = parts.slice(1).join(" ").trim();
        if (uid && nickname) {
          members.push({ weibo_uid: uid, nickname });
        }
      }
    }
    if (members.length === 0) {
      toast.error("未解析到有效数据，请检查格式");
      return;
    }
    setBatchAdding(true);
    try {
      const result = await batchAddTeamMembers(members);
      toast.success(`批量添加完成：新增 ${result.created}，跳过 ${result.skipped}`);
      setBatchText("");
      await loadTeamMembers();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "批量添加失败");
    } finally {
      setBatchAdding(false);
    }
  }

  async function handleDeleteMember(id: number) {
    setDeletingId(id);
    try {
      await deleteTeamMember(id);
      toast.success("组员已删除");
      await loadTeamMembers();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "删除组员失败");
    } finally {
      setDeletingId(null);
    }
  }

  // ── Start handler ───────────────────────────────────────────────────────────

  async function onSubmit(values: SetupFormValues) {
    setSubmitting(true);
    try {
      const result = await startCompetition(values.weibo_url, selectedUids);
      setWeiboUrl(values.weibo_url);
      setStatus("running");
      setSessionId(String(result.session_id));
      toast.success("比赛已开始！");
      navigate("/dashboard");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to start competition");
    } finally {
      setSubmitting(false);
    }
  }

  // ── End handler ─────────────────────────────────────────────────────────────

  async function handleEndCompetition() {
    setEndingCompetition(true);
    try {
      const status = await getCompetitionStatus();
      if (status.status === "idle") {
        toast.info("No active competition to end");
        return;
      }
      await endCompetition();
      setStatus("ended");
      toast.success("比赛已结束");
      navigate("/replay");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to end competition");
    } finally {
      setEndingCompetition(false);
    }
  }

  // ── Checkbox toggle ─────────────────────────────────────────────────────────

  function toggleUid(uid: string) {
    setSelectedUids((prev) =>
      prev.includes(uid) ? prev.filter((u) => u !== uid) : [...prev, uid],
    );
  }

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div data-testid="setup-page" className="max-w-2xl mx-auto space-y-6">
      {/* Team Member Management */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="h-5 w-5" />
            组员管理
          </CardTitle>
          <CardDescription>
            添加和管理参赛组员（仅需 UID 和昵称，无需登录）
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Add single member */}
          <div className="space-y-3">
            <Label className="text-sm font-medium">添加组员</Label>
            <div className="flex gap-3">
              <Input
                placeholder="微博 UID"
                value={newUid}
                onChange={(e) => setNewUid(e.target.value)}
                className="flex-1"
              />
              <Input
                placeholder="昵称"
                value={newNickname}
                onChange={(e) => setNewNickname(e.target.value)}
                className="flex-1"
              />
              <Button
                type="button"
                onClick={handleAddMember}
                disabled={
                  addingMember || !newUid.trim() || !newNickname.trim()
                }
              >
                <Plus className="h-4 w-4" />
                {addingMember ? "添加中..." : "添加"}
              </Button>
            </div>
          </div>

          {/* Batch add */}
          <div className="space-y-3">
            <Label className="text-sm font-medium">批量添加</Label>
            <Textarea
              placeholder={
                "每行一条，格式：UID 昵称 或 UID,昵称\n示例：\n1234567890 张三\n9876543210,李四"
              }
              value={batchText}
              onChange={(e) => setBatchText(e.target.value)}
              rows={5}
            />
            <Button
              type="button"
              variant="outline"
              onClick={handleBatchAdd}
              disabled={batchAdding || !batchText.trim()}
            >
              <Upload className="h-4 w-4" />
              {batchAdding ? "批量添加中..." : "批量添加"}
            </Button>
          </div>

          {/* Member list */}
          <div className="space-y-3">
            <Label className="text-sm font-medium">
              组员列表 ({teamMembers.length})
            </Label>
            {teamMembers.length === 0 ? (
              <p className="text-sm text-muted-foreground">暂无组员，请添加</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>UID</TableHead>
                    <TableHead>昵称</TableHead>
                    <TableHead className="w-[80px]">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {teamMembers.map((member) => (
                    <TableRow key={member.id}>
                      <TableCell className="font-mono text-sm">
                        {member.weibo_uid}
                      </TableCell>
                      <TableCell>{member.nickname}</TableCell>
                      <TableCell>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteMember(member.id)}
                          disabled={deletingId === member.id}
                        >
                          <Trash2 className="h-4 w-4" />
                          {deletingId === member.id ? "..." : "删除"}
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Competition Setup */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Monitor className="h-5 w-5" />
            Competition Setup
          </CardTitle>
          <CardDescription>
            Enter the Weibo post URL and select team members to start monitoring
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
              {/* Weibo URL Input */}
              <FormField
                control={form.control}
                name="weibo_url"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Weibo Post URL</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="https://weibo.com/..."
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Team Member Selection */}
              <div className="space-y-3">
                <Label className="text-sm font-medium">
                  Team Members ({selectedUids.length}/{accounts.length} selected)
                </Label>
                {accounts.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    请先在{" "}
                    <Link to="/login" className="underline hover:text-foreground">
                      Login
                    </Link>{" "}
                    页面扫码登录账号
                  </p>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {accounts.map((account) => (
                      <div
                        key={account.weibo_uid}
                        className="flex items-center space-x-3 rounded-lg border border-border p-3"
                      >
                        <Checkbox
                          id={`member-${account.weibo_uid}`}
                          checked={selectedUids.includes(account.weibo_uid)}
                          onCheckedChange={() => toggleUid(account.weibo_uid)}
                        />
                        <Label
                          htmlFor={`member-${account.weibo_uid}`}
                          className="cursor-pointer text-sm font-normal"
                        >
                          <span className="font-medium">{account.nickname}</span>
                          <span className="ml-2 text-muted-foreground">
                            UID: {account.weibo_uid}
                          </span>
                        </Label>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              <div className="flex gap-4">
                <Button
                  type="submit"
                  size="lg"
                  disabled={submitting}
                >
                  {submitting ? "开始中..." : "开始比赛"}
                </Button>
                <Button
                  type="button"
                  size="lg"
                  variant="outline"
                  disabled={endingCompetition}
                  onClick={handleEndCompetition}
                >
                  {endingCompetition ? "结束中..." : "结束比赛"}
                </Button>
              </div>
            </form>
          </Form>
        </CardContent>
      </Card>
    </div>
  );
}

export default SetupPage;
