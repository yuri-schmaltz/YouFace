import { useCallback } from "react";
import { formatApiUrl } from "../utils/api";

/**
 * Diagnostic actions hook. Handles the download of diagnostic bundles
 * and output files from the API. Extracted from page.tsx
 * (handleExportDiagnostic, handleDownloadOutput).
 *
 * These actions only manipulate the DOM (create <a>, click, remove)
 * and trigger browser-native downloads. No state lives here.
 */
export interface UseDiagnosticActionsOptions {
  apiUrl: string;
  showToast: (type: "success" | "error" | "info", title: string, message?: string) => void;
}

export interface UseDiagnosticActionsReturn {
  handleExportDiagnostic: () => void;
  handleDownloadOutput: (previewOutputUrl: string | null) => void;
}

export function useDiagnosticActions(options: UseDiagnosticActionsOptions): UseDiagnosticActionsReturn {
  const { apiUrl, showToast } = options;

  const triggerDownload = useCallback((href: string, downloadName: string) => {
    const a = document.createElement("a");
    a.href = href;
    a.download = downloadName;
    document.body.appendChild(a);
    a.click();
    a.remove();
  }, []);

  const handleExportDiagnostic = useCallback(() => {
    const url = formatApiUrl(apiUrl, "/api/diagnostic/export");
    triggerDownload(url, "facefusion_diagnostic.zip");
    showToast("info", "Diagnóstico", "Download do pacote de logs iniciado.");
  }, [apiUrl, showToast, triggerDownload]);

  const handleDownloadOutput = useCallback(
    (previewOutputUrl: string | null) => {
      if (!previewOutputUrl) {
        showToast("error", "Sem saída", "Nenhum arquivo de saída disponível para download.");
        return;
      }
      triggerDownload(previewOutputUrl, "facefusion_output");
      showToast("info", "Download", "Arquivo sendo transferido.");
    },
    [showToast, triggerDownload],
  );

  return { handleExportDiagnostic, handleDownloadOutput };
}
