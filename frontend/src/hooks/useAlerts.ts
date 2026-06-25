import { useState, useEffect, useCallback } from "react";
import type { AlertDTO } from "@/types/alert";
import { apiGet, apiPost } from "@/api/client";

interface WebSocketMessage {
  type: string;
  data: Record<string, unknown>;
  timestamp: string;
}

interface UseAlertsReturn {
  alerts: AlertDTO[];
  isLoading: boolean;
  executeAlert: (alertId: number, comment: string, accountIds: number[]) => Promise<void>;
}

/**
 * Manages alerts from WebSocket messages and API.
 * - Fetches pending alerts on mount via GET /api/alerts/pending
 * - Listens for `alert_new` WS messages to prepend new alerts
 * - Listens for `alert_resolved` WS messages to remove resolved alerts
 * - Provides executeAlert to POST /api/alerts/{id}/execute
 */
export function useAlerts(lastMessage: WebSocketMessage | null): UseAlertsReturn {
  const [alerts, setAlerts] = useState<AlertDTO[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Fetch pending alerts on mount
  useEffect(() => {
    let cancelled = false;
    apiGet<AlertDTO[]>("/alerts/pending")
      .then((data) => {
        if (!cancelled) {
          setAlerts(data);
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

    if (lastMessage.type === "alert_new") {
      const newAlert = lastMessage.data as unknown as AlertDTO;
      if (newAlert && typeof newAlert.id === "number") {
        setAlerts((prev) => [newAlert, ...prev]);
      }
    } else if (lastMessage.type === "alert_resolved") {
      const resolvedId = (lastMessage.data as unknown as { id: number }).id;
      if (typeof resolvedId === "number") {
        setAlerts((prev) => prev.filter((a) => a.id !== resolvedId));
      }
    }
  }, [lastMessage]);

  const executeAlert = useCallback(
    async (alertId: number, comment: string, accountIds: number[]) => {
      await apiPost(`/alerts/${alertId}/execute`, {
        comment,
        account_ids: accountIds,
      });
    },
    [],
  );

  return { alerts, isLoading, executeAlert };
}
