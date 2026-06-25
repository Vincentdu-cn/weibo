/**
 * Competition API client — wraps the /api/competition endpoints.
 * Uses the shared apiPost/apiGet helpers from client.ts.
 */

import { apiPost, apiGet } from "./client";

export interface CompetitionStatus {
  status: "idle" | "running" | "paused" | "ended";
  session_id?: number;
  total_comments?: number;
  remaining_quota?: number;
  started_at?: string | null;
  target_weibo_url?: string;
}

export interface StartCompetitionResult {
  status: string;
  session_id: number;
}

/**
 * Start a new competition session.
 * @param weibo_url The target Weibo post URL
 * @param team_uids Optional list of team member UIDs to track
 */
export async function startCompetition(
  weibo_url: string,
  team_uids?: string[],
): Promise<StartCompetitionResult> {
  return apiPost<StartCompetitionResult>("/competition/start", {
    weibo_url,
    team_uids: team_uids ?? null,
  });
}

/**
 * Pause the active competition.
 */
export async function pauseCompetition(): Promise<{ status: string }> {
  return apiPost<{ status: string }>("/competition/pause", {});
}

/**
 * Resume a paused competition.
 */
export async function resumeCompetition(): Promise<{ status: string }> {
  return apiPost<{ status: string }>("/competition/resume", {});
}

/**
 * End the active competition.
 */
export async function endCompetition(): Promise<{
  status: string;
  total_comments: number;
}> {
  return apiPost<{ status: string; total_comments: number }>(
    "/competition/end",
    {},
  );
}

/**
 * Get the current competition status.
 */
export async function getCompetitionStatus(): Promise<CompetitionStatus> {
  return apiGet<CompetitionStatus>("/competition/status");
}
