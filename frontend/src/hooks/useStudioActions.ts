import { useCallback } from "react";
import { formatApiUrl } from "../utils/api";
import { useStudioState } from "./useStudioState";

/**
 * Studio actions hook. Encapsulates the "run" actions:
 *  - generatePreview: POST /api/preview (single-frame)
 *  - generateSwap: POST /api/jobs (full render)
 *  - exportDiagnostic: GET /api/diagnostic/export (ZIP bundle)
 *  - downloadOutput: GET /api/media/output/{filename}
 *
 * Extracted from page.tsx handlers: handleGeneratePreview,
 * handleGenerateSwap, handleExportDiagnostic, handleDownloadOutput.
 */
export interface UseStudioActionsOptions {
  apiUrl: string;
  showToast: (type: "success" | "error" | "info", title: string, message?: string) => void;
  /** Optional callback after a successful job creation (e.g., refresh list) */
  onJobCreated?: () => void;
}

export interface UseStudioActionsReturn {
  generatePreview: (silent?: boolean) => Promise<void>;
  generateSwap: () => Promise<void>;
  exportDiagnostic: () => Promise<void>;
  downloadOutput: (filename: string) => Promise<void>;
}

export function useStudioActions(options: UseStudioActionsOptions): UseStudioActionsReturn {
  const { apiUrl, showToast, onJobCreated } = options;
  const studio = useStudioState();

  const generatePreview = useCallback(async (silent = false) => {
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
          face_mask_blur: studio.state.processorOptions.face_mask_blur,
          detection_threshold: studio.state.processorOptions.detection_threshold,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
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
  }, [apiUrl, studio, showToast]);

  const generateSwap = useCallback(async () => {
    const sources = studio.state.sourceItems.map(s => s.file_path);
    if (!sources.length || !studio.state.targetMediaFullPath) {
      showToast("info", "Mídia Faltando", "Selecione fonte e destino antes de gerar.");
      return;
    }
    studio.set("isGenerating", true);
    try {
      const url = formatApiUrl(apiUrl, "/api/jobs");
      const faceMappings: Array<{ source_path: string; target_face_index: number; reference_frame_number: number }> = [];
      for (const [idx, sourcePath] of Object.entries(studio.state.faceMappings)) {
        faceMappings.push({
          source_path: sourcePath,
          target_face_index: Number(idx),
          reference_frame_number: studio.state.referenceFrameNumber,
        });
      }
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_paths: sources,
          target_path: studio.state.targetMediaFullPath,
          processors: studio.state.selectedProcessors.length > 0 ? studio.state.selectedProcessors : ["face_swapper"],
          face_swapper_weight: studio.state.processorOptions.face_swapper_weight,
          face_mask_blur: studio.state.processorOptions.face_mask_blur,
          detection_threshold: studio.state.processorOptions.detection_threshold,
          smoothing: studio.state.processorOptions.smoothing,
          face_swapper_model: studio.state.processorOptions.face_swapper_model,
          face_swapper_pixel_boost: studio.state.processorOptions.face_swapper_pixel_boost,
          face_enhancer_model: studio.state.processorOptions.face_enhancer_model,
          face_enhancer_blend: studio.state.processorOptions.face_enhancer_blend,
          face_enhancer_weight: studio.state.processorOptions.face_enhancer_weight,
          output_format: studio.state.output.format.toLowerCase(),
          output_video_encoder: studio.state.output.videoEncoder,
          output_video_quality: studio.state.output.quality,
          output_audio_encoder: studio.state.output.audioEncoder,
          output_audio_quality: studio.state.output.audioQuality,
          output_audio_volume: studio.state.output.audioVolume,
          face_mappings: faceMappings,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      showToast("success", "Job Criado", "Tarefa adicionada à fila. Acompanhe na aba Jobs.");
      onJobCreated?.();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      showToast("error", "Erro ao Criar Tarefa", message || "Falha na conexão.");
    } finally {
      studio.set("isGenerating", false);
    }
  }, [apiUrl, studio, showToast, onJobCreated]);

  const exportDiagnostic = useCallback(async () => {
    try {
      const url = formatApiUrl(apiUrl, "/api/diagnostic/export");
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "youface_diagnostic.zip";
      a.click();
      URL.revokeObjectURL(a.href);
      showToast("success", "Diagnóstico Exportado", "Bundle baixado com sucesso.");
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      showToast("error", "Erro no Export", message || "Falha ao baixar diagnóstico.");
    }
  }, [apiUrl, showToast]);

  const downloadOutput = useCallback(async (filename: string) => {
    try {
      const url = formatApiUrl(apiUrl, `/api/media/output/${filename}`);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      showToast("success", "Download Iniciado", filename);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      showToast("error", "Erro no Download", message || "Falha ao baixar arquivo.");
    }
  }, [apiUrl, showToast]);

  return { generatePreview, generateSwap, exportDiagnostic, downloadOutput };
}
