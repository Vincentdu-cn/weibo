import { create } from "zustand";

export type CompetitionStatus = "idle" | "running" | "paused" | "ended";

interface CompetitionState {
  status: CompetitionStatus;
  weibo_url: string | null;
  session_id: string | null;
  setStatus: (status: CompetitionStatus) => void;
  setWeiboUrl: (url: string | null) => void;
  setSessionId: (id: string | null) => void;
  reset: () => void;
}

export const useCompetitionStore = create<CompetitionState>((set) => ({
  status: "idle",
  weibo_url: null,
  session_id: null,
  setStatus: (status) => set({ status }),
  setWeiboUrl: (weibo_url) => set({ weibo_url }),
  setSessionId: (session_id) => set({ session_id }),
  reset: () => set({ status: "idle", weibo_url: null, session_id: null }),
}));
