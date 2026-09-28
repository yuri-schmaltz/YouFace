import { useCallback } from "react";
import { formatApiUrl } from "../utils/api";
import { useStudioState } from "./useStudioState";

/**
 * Preview hook. Encapsulates POST /api/preview and updates the Studio
 * state with the returned preview_url. Extracted from page.tsx
 * (handleGeneratePreview).
 *
 * The handler accepts a "silent" flag for auto-preview-on-change cases
 * where spamming toasts on every keystroke would be UX-hostile.
 */
export interface UsePreviewOptions {
  apiUrl: string;
  showToast: (type: "success" | "error" | "info", title: string, message?: string) => void;
  /** Extra fields to send (face_mask_blur, detection_threshold, etc.) */
  buildRequestBody?: () => Record<string, unknown>;
}

export interface UsePreviewReturn {
  handleGeneratePreview: (silent?: boolean) => Promise<void>;
  isPreviewLoading: boolean;
}

export function usePreview(options: UsePreviewOptions): UsePreviewReturn {
  const { apiUrl, showToast, buildRequestBody } = options;
  const studio = useStudioState();

  const handleGeneratePreview = useCallback(async (silent = false) => {
    if (!studio.state.targetMediaFullPath) {
      if (!silent) showToast("info", "Sem Destino", "Carregue uma mídia de destino primeiro.");
      return;
    }
    studio.set("isPreviewLoading", true);
    try {
      const url = formatApiUrl(apiUrl, "/api/preview");
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target_path: studio.state.targetMediaFullPath,
          ...(buildRequestBody ? buildRequestBody() : {}),
        }),
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const data = await res.json();
      if (data.preview_url) {
        studio.set("previewOutputUrl", formatApiUrl(apiUrl, data.preview_url));
        if (!silent) showToast("success", "Preview Atualizado", "Novo frame processado.");
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      if (!silent) showToast("error", "Erro no Preview", message || "Falha na pré-visualização.");
    } finally {
      studio.set("isPreviewLoading", false);
    }
  }, [apiUrl, studio, showToast, buildRequestBody]);

  return {
    handleGeneratePreview,
    isPreviewLoading: studio.state.isPreviewLoading,
  };
}
