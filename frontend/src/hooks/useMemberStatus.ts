import { useState, useEffect } from "react";

interface WebSocketMessage {
  type: string;
  data: Record<string, unknown>;
  timestamp: string;
}

export interface MemberGridItem {
  uid: string | null;
  nickname: string | null;
  avatar_url: string | null;
  current_rank: number | null;
  like_count: number | null;
  is_hot: boolean;
  comment_count: number;
  online_status: string;
}

interface UseMemberStatusReturn {
  members: MemberGridItem[];
  isLoading: boolean;
}

/**
 * Extracts member status data from WebSocket messages.
 * Listens for `member_status_update` — data IS the raw list of MemberGridItem (not wrapped in a dict).
 */
export function useMemberStatus(lastMessage: WebSocketMessage | null): UseMemberStatusReturn {
  const [members, setMembers] = useState<MemberGridItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!lastMessage) return;

    if (lastMessage.type === "member_status_update") {
      const raw = lastMessage.data;
      // Backend sends raw list as data — handle both array and object-with-list
      const list = Array.isArray(raw) ? raw : (raw as unknown as { grid_data?: MemberGridItem[] }).grid_data;
      if (Array.isArray(list)) {
        setMembers(list);
        setIsLoading(false);
      }
    }
  }, [lastMessage]);

  return { members, isLoading };
}
