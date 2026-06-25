import { useState, useEffect } from "react";
import type { StatsDTO } from "@/types/stats";
import { apiGet } from "@/api/client";

interface WebSocketMessage {
  type: string;
  data: Record<string, unknown>;
  timestamp: string;
}

interface TrendPoint {
  time: string;
  count: number;
}

interface UseStatsReturn {
  stats: StatsDTO | null;
  isLoading: boolean;
  trendData: TrendPoint[];
}

/**
 * Manages statistics data from API and WebSocket.
 * - Fetches GET /api/stats on mount
 * - Listens for `stats_update` WS messages to update stats + push trend data point
 * - Keeps max 30 trend data points
 */
export function useStats(lastMessage: WebSocketMessage | null): UseStatsReturn {
  const [stats, setStats] = useState<StatsDTO | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [trendData, setTrendData] = useState<TrendPoint[]>([]);

  // Fetch initial stats on mount
  useEffect(() => {
    let cancelled = false;
    apiGet<StatsDTO>("/stats")
      .then((data) => {
        if (!cancelled) {
          setStats(data);
          setIsLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Handle WebSocket messages
  useEffect(() => {
    if (!lastMessage) return;

    if (lastMessage.type === "stats_update") {
      const newStats = lastMessage.data as unknown as StatsDTO;
      if (newStats && typeof newStats.total_comments === "number") {
        setStats(newStats);
        const timeStr = new Date().toLocaleTimeString("zh-CN", {
          minute: "2-digit",
          second: "2-digit",
        });
        setTrendData((prev) => {
          const next = [...prev, { time: timeStr, count: newStats.team_hot_count }];
          return next.slice(-30);
        });
      }
    }
  }, [lastMessage]);

  return { stats, isLoading, trendData };
}
