import { useState, useEffect } from "react";
import type { CommentDTO } from "@/types/comment";

interface WebSocketMessage {
  type: string;
  data: Record<string, unknown>;
  timestamp: string;
}

interface UseHotCommentsReturn {
  comments: CommentDTO[];
  isLoading: boolean;
}

/**
 * Extracts hot comment data from WebSocket messages.
 * Listens for `hot_comments_update` messages containing a comments array.
 */
export function useHotComments(lastMessage: WebSocketMessage | null): UseHotCommentsReturn {
  const [comments, setComments] = useState<CommentDTO[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!lastMessage) return;

    if (lastMessage.type === "hot_comments_update") {
      const data = lastMessage.data;
      const rawComments = (data.comments ?? data) as CommentDTO[];
      if (Array.isArray(rawComments)) {
        setComments(rawComments);
        setIsLoading(false);
      }
    }
  }, [lastMessage]);

  return { comments, isLoading };
}
