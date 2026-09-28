import { useState, useEffect, useCallback, useRef } from "react";
import { Job } from "../types";
import { formatApiUrl } from "../utils/api";

/**
 * Hook para consumir a lista de jobs do backend.
 *
 * Estratégia de comunicação (em ordem de preferência):
 *  1. SSE (`/api/jobs/stream`) — push instantâneo, sem polling
 *  2. Fallback polling (`/api/jobs` a cada 2.5s) — se SSE falhar
 *
 * Polimentos em relação à versão anterior:
 *  - `connectionMode` exposto para a UI mostrar status (SSE/Polling/Connecting)
 *  - `fetchJobs()` chamado no mount mesmo se SSE estiver OK (data imediata)
 *  - Polling pausa quando a aba está oculta (visibility API) — economiza
 *    CPU/bateria quando usuário não está olhando
 *  - SSE tem timeout: se nenhum evento chegar em 30s, força fallback
 *  - Cleanup completo: SSE close + interval clear + listener remove
 */
export type ConnectionMode = "connecting" | "sse" | "polling" | "offline";

export interface UseJobsReturn {
  jobs: Job[];
  activeJob: Job | null;
  isLoading: boolean;
  connectionMode: ConnectionMode;
  fetchJobs: () => Promise<void>;
  cancelJob: (jobId: string) => Promise<boolean>;
  deleteJob: (jobId: string) => Promise<{ success: boolean; message?: string }>;
}

const POLL_INTERVAL_MS = 2500;
const SSE_INACTIVITY_TIMEOUT_MS = 30_000;

export function useJobs(apiUrl: string): UseJobsReturn {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [activeJob, setActiveJob] = useState<Job | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [connectionMode, setConnectionMode] = useState<ConnectionMode>("connecting");
  const eventSourceRef = useRef<EventSource | null>(null);
  const sseTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const applyJobs = useCallback((data: Job[]) => {
    setJobs(data);
    const running = data.find(j => j.status === "processing" || j.status === "queued") ?? null;
    setActiveJob(running);
  }, []);

  const fetchJobs = useCallback(async () => {
    if (!apiUrl && apiUrl !== "") return;
    try {
      const url = formatApiUrl(apiUrl, "/api/jobs");
      const res = await fetch(url);
      if (res.ok) {
        const data: Job[] = await res.json();
        applyJobs(data);
      }
    } catch (err) {
      console.error("Erro ao buscar jobs via polling:", err);
    } finally {
      setIsLoading(false);
    }
  }, [apiUrl, applyJobs]);

  const startPolling = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    if (sseTimeoutRef.current) {
      clearTimeout(sseTimeoutRef.current);
      sseTimeoutRef.current = null;
    }
    setConnectionMode("polling");
    // Fetch imediatamente, depois em intervalo
    fetchJobs();
    return setInterval(() => {
      // Só poll se a aba estiver visível
      if (typeof document === "undefined" || document.visibilityState === "visible") {
        fetchJobs();
      }
    }, POLL_INTERVAL_MS);
  }, [fetchJobs]);

  // Connect to SSE stream, with graceful fallback to interval polling
  useEffect(() => {
    if (!apiUrl && apiUrl !== "") return;
    let fallbackInterval: ReturnType<typeof setInterval> | null = null;

    const armSseTimeout = () => {
      if (sseTimeoutRef.current) clearTimeout(sseTimeoutRef.current);
      sseTimeoutRef.current = setTimeout(() => {
        // Nenhum evento SSE em 30s — considerar conexão morta
        if (eventSourceRef.current) {
          eventSourceRef.current.close();
          eventSourceRef.current = null;
        }
        fallbackInterval = startPolling();
      }, SSE_INACTIVITY_TIMEOUT_MS);
    };

    const streamUrl = formatApiUrl(apiUrl, "/api/jobs/stream");
    setConnectionMode("connecting");

    // Fetch inicial para ter dados imediatamente, mesmo antes do SSE
    fetchJobs();

    try {
      const es = new EventSource(streamUrl);
      eventSourceRef.current = es;
      armSseTimeout();

      es.onopen = () => {
        // Conexão estabelecida — resetar o timer
        armSseTimeout();
        setConnectionMode("sse");
      };

      es.onmessage = (event) => {
        armSseTimeout();
        try {
          const data: Job[] = JSON.parse(event.data);
          applyJobs(data);
          setIsLoading(false);
        } catch {
          // heartbeat or unparseable — ignore
        }
      };

      es.onerror = () => {
        // Close broken SSE and fallback to polling
        if (eventSourceRef.current) {
          eventSourceRef.current.close();
          eventSourceRef.current = null;
        }
        if (!fallbackInterval) {
          fallbackInterval = startPolling();
        }
      };
    } catch {
      fallbackInterval = startPolling();
    }

    // Pausar polling quando aba fica oculta (visibility API)
    const onVisibilityChange = () => {
      if (document.visibilityState === "visible" && connectionMode === "polling") {
        fetchJobs();
      }
    };
    document.addEventListener("visibilitychange", onVisibilityChange);

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      if (sseTimeoutRef.current) {
        clearTimeout(sseTimeoutRef.current);
        sseTimeoutRef.current = null;
      }
      if (fallbackInterval) {
        clearInterval(fallbackInterval);
      }
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
    // connectionMode intencionalmente fora do dep array — só queremos
    // reconectar quando apiUrl muda, não quando o mode muda.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiUrl]);

  const cancelJob = useCallback(async (jobId: string): Promise<boolean> => {
    try {
      const url = formatApiUrl(apiUrl, `/api/jobs/${jobId}/cancel`);
      const res = await fetch(url, { method: "POST" });
      if (res.ok) {
        await fetchJobs();
        return true;
      }
      return false;
    } catch (err) {
      console.error("Erro ao cancelar job:", err);
      return false;
    }
  }, [apiUrl, fetchJobs]);

  const deleteJob = useCallback(async (jobId: string): Promise<{ success: boolean; message?: string }> => {
    try {
      const url = formatApiUrl(apiUrl, `/api/jobs/${jobId}`);
      const res = await fetch(url, { method: "DELETE" });
      const data = await res.json();
      if (res.ok) {
        setJobs(prev => prev.filter(j => j.id !== jobId));
        return { success: true };
      }
      return { success: false, message: data.detail || "Erro ao excluir job." };
    } catch (err) {
      return { success: false, message: "Erro de conexão ao excluir job." };
    }
  }, [apiUrl]);

  return {
    jobs,
    activeJob,
    isLoading,
    connectionMode,
    fetchJobs,
    cancelJob,
    deleteJob,
  };
}
