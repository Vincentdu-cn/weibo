import { useState, useCallback, useEffect, useRef } from "react";
import { generateQr, getQrStatus } from "@/api/qr";

type QrStatus = "idle" | "waiting" | "scanned" | "success" | "expired";

interface UseQrLoginReturn {
  qrUrl: string | null;
  status: QrStatus;
  sessionId: string | null;
  generate: () => Promise<void>;
  checkStatus: () => Promise<void>;
  reset: () => void;
}

const POLL_INTERVAL_MS = 2000;

export function useQrLogin(): UseQrLoginReturn {
  const [qrUrl, setQrUrl] = useState<string | null>(null);
  const [status, setStatus] = useState<QrStatus>("idle");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const sessionIdRef = useRef<string | null>(null);

  // Keep ref in sync with state to avoid stale closures in interval
  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);

  const clearPollTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const checkStatus = useCallback(async () => {
    const sid = sessionIdRef.current;
    if (!sid) return;
    try {
      const data = await getQrStatus(sid);
      const newStatus = data.status as QrStatus;
      setStatus(() => {
        if (newStatus === "success" || newStatus === "expired") {
          clearPollTimer();
        }
        return newStatus;
      });
    } catch {
      // On error, don't change status
    }
  }, [clearPollTimer]);

  const reset = useCallback(() => {
    clearPollTimer();
    setQrUrl(null);
    setStatus("idle");
    setSessionId(null);
    sessionIdRef.current = null;
  }, [clearPollTimer]);

  const generate = useCallback(async () => {
    clearPollTimer();
    try {
      const data = await generateQr();
      setQrUrl(data.qr_url);
      setSessionId(data.session_id);
      sessionIdRef.current = data.session_id;
      setStatus("waiting");
    } catch {
      setStatus("idle");
    }
  }, [clearPollTimer]);

  // Polling effect: check status every 2s when waiting or scanned
  useEffect(() => {
    if (status === "waiting" || status === "scanned") {
      timerRef.current = setInterval(() => {
        checkStatus();
      }, POLL_INTERVAL_MS);
    }
    return () => {
      clearPollTimer();
    };
  }, [status, checkStatus, clearPollTimer]);

  // Auto-generate QR on mount
  useEffect(() => {
    generate();
    return () => {
      clearPollTimer();
    };
  }, [generate, clearPollTimer]);

  return { qrUrl, status, sessionId, generate, checkStatus, reset };
}
