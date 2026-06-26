import { apiGet, apiPost, apiDelete } from "./client";

export interface TeamMember {
  id: number;
  weibo_uid: string;
  nickname: string;
}

export async function getTeamMembers(): Promise<TeamMember[]> {
  return apiGet<TeamMember[]>("/team-members");
}

export async function addTeamMember(
  weibo_uid: string,
  nickname: string,
): Promise<TeamMember> {
  return apiPost<TeamMember>("/team-members", { weibo_uid, nickname });
}

export async function batchAddTeamMembers(
  members: { weibo_uid: string; nickname: string }[],
): Promise<{ created: number; skipped: number }> {
  return apiPost<{ created: number; skipped: number }>(
    "/team-members/batch",
    members,
  );
}

export async function deleteTeamMember(id: number): Promise<void> {
  await apiDelete<void>(`/team-members/${id}`);
}
