import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Monitor } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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

// ── Mock team members (placeholder until account API is wired) ────────────────

interface TeamMember {
  uid: string;
  nickname: string;
}

const MOCK_TEAM: TeamMember[] = [
  { uid: "1001", nickname: "Player Alpha" },
  { uid: "1002", nickname: "Player Bravo" },
  { uid: "1003", nickname: "Player Charlie" },
  { uid: "1004", nickname: "Player Delta" },
  { uid: "1005", nickname: "Player Echo" },
];

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
  const [selectedUids, setSelectedUids] = useState<string[]>([]);

  const form = useForm<SetupFormValues>({
    resolver: zodResolver(setupSchema),
    defaultValues: { weibo_url: "" },
  });

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
    <div data-testid="setup-page" className="max-w-2xl mx-auto">
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
                  Team Members ({selectedUids.length}/{MOCK_TEAM.length} selected)
                </Label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {MOCK_TEAM.map((member) => (
                    <div
                      key={member.uid}
                      className="flex items-center space-x-3 rounded-lg border border-border p-3"
                    >
                      <Checkbox
                        id={`member-${member.uid}`}
                        checked={selectedUids.includes(member.uid)}
                        onCheckedChange={() => toggleUid(member.uid)}
                      />
                      <Label
                        htmlFor={`member-${member.uid}`}
                        className="cursor-pointer text-sm font-normal"
                      >
                        <span className="font-medium">{member.nickname}</span>
                        <span className="ml-2 text-muted-foreground">
                          UID: {member.uid}
                        </span>
                      </Label>
                    </div>
                  ))}
                </div>
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
