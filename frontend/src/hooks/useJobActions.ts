import { useCallback } from "react";
import { formatApiUrl } from "../utils/api";

/**
 * Job actions hook. Encapsulates cancel + delete + fetch of jobs.
 * Extracted from page.tsx (handleCancelJob, handleConfirmDelete, the
 * useJobs hook already handles fetchJobs).
 *
 * These actions are pure HTTP wrappers — no state in the hook itself.
 * Toast feedback is delegated to the caller via showToast.
 */
export interface UseJobActionsOptions {
  apiUrl: string;
  showToast: (type: "success" | "error" | "info", title: string, message?: string) => void;
  onSuccess?: () => void;
}

export interface UseJobActionsReturn {
  cancelJob: (jobId: string) => Promise<boolean>;
  deleteJob: (jobId: string) => Promise<{ success: boolean; message?: string }>;
}

export function useJobActions(options: UseJobActionsOptions): UseJobActionsReturn {
  const { apiUrl, showToast, onSuccess } = options;

  const cancelJob = useCallback(async (jobId: string): Promise<boolean> => {
    try {
      const url = formatApiUrl(apiUrl, `/api/jobs/${jobId}/cancel`);
      const res = await fetch(url, { method: "POST" });
      if (res.ok) {
        showToast("success", "Job Cancelado", `Tarefa ${jobId} foi cancelada.`);
        onSuccess?.();
        return true;
      }
      const data = await res.json().catch(() => ({}));
      showToast("error", "Erro ao Cancelar", data.detail || "Falha no cancelamento.");
      return false;
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      showToast("error", "Erro de Conexão", message);
      return false;
    }
  }, [apiUrl, showToast, onSuccess]);

  const deleteJob = useCallback(async (jobId: string) => {
    try {
      const url = formatApiUrl(apiUrl, `/api/jobs/${jobId}`);
      const res = await fetch(url, { method: "DELETE" });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        showToast("success", "Job Removido", `Tarefa ${jobId} foi excluída.`);
        onSuccess?.();
        return { success: true };
      }
      return { success: false, message: data.detail || "Erro ao excluir." };
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      return { success: false, message };
    }
  }, [apiUrl, showToast, onSuccess]);

  return { cancelJob, deleteJob };
}
