import { useState, useEffect } from "react";

interface WebSocketMessage {
  type: string;
  data: Record<string, unknown>;
  timestamp: string;
}

export interface MemberComment {
  comment_id: string;
  content: string;
  like_count: number;
  rank: number;
  is_hot: boolean;
  created_at: string;
}

export interface MemberCard {
  uid: string;
  nickname: string;
  avatar_url: string | null;
  total_comments: number;
  total_likes: number;
  best_rank: number | null;
  in_hot: boolean;
  comments: MemberComment[];
}

interface UseMemberStatusReturn {
  members: MemberCard[];
  isLoading: boolean;
}

/**
 * Extracts member status data from WebSocket messages.
 * Listens for `member_status_update` — data is the raw list of MemberCard.
 */
export function useMemberStatus(lastMessage: WebSocketMessage | null): UseMemberStatusReturn {
  const [members, setMembers] = useState<MemberCard[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!lastMessage) return;

    if (lastMessage.type === "member_status_update") {
      const raw = lastMessage.data;
      // Backend sends raw list as data — handle both array and object-with-list
      const list = Array.isArray(raw) ? raw : (raw as unknown as { grid_data?: MemberCard[] }).grid_data;
      if (Array.isArray(list)) {
        setMembers(list);
        setIsLoading(false);
      }
    }
  }, [lastMessage]);

  return { members, isLoading };
}
