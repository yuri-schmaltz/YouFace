import { useCallback } from "react";
import { formatApiUrl } from "../utils/api";
import type { Job } from "../types";

/**
 * Comparator actions hook. Loads a completed job's output into the
 * studio preview/compare view. Extracted from page.tsx
 * (handleLoadToComparator).
 */
export interface UseComparatorActionsOptions {
  apiUrl: string;
  showToast: (type: "success" | "error" | "info", title: string, message?: string) => void;
  setPreviewOutputUrl: (url: string | null) => void;
  setActiveTab: (tab: string) => void;
}

export interface UseComparatorActionsReturn {
  handleLoadToComparator: (job: Job) => void;
}

export function useComparatorActions(options: UseComparatorActionsOptions): UseComparatorActionsReturn {
  const { apiUrl, showToast, setPreviewOutputUrl, setActiveTab } = options;

  const handleLoadToComparator = useCallback(
    (job: Job) => {
      if (!job.outputUrl) {
        showToast("error", "Sem saída", "Este job ainda não tem arquivo de saída.");
        return;
      }
      setPreviewOutputUrl(formatApiUrl(apiUrl, job.outputUrl));
      setActiveTab("create_new");
      showToast("info", "Job Carregado", `Visualizando resultado de ${job.id}`);
    },
    [apiUrl, showToast, setPreviewOutputUrl, setActiveTab],
  );

  return { handleLoadToComparator };
}
