import { useCallback } from "react";
import { formatApiUrl } from "../utils/api";
import { useStudioState } from "./useStudioState";
import type { DetectedFace, VideoDiagnosticReport } from "../types";

/**
 * Face analysis hook. Encapsulates:
 *  - analyzeFaces: POST /api/media/analyze-faces
 *  - runVideoDiagnosis: POST /api/video/diagnose
 *  - applyDiagnosticRecommendation: updates processor options from rec
 *
 * Extracted from page.tsx handlers: handleAnalyzeFaces,
 * handleRunVideoDiagnosis, handleApplyDiagnosticRecommendation.
 */
export interface UseFaceAnalysisOptions {
  apiUrl: string;
  showToast: (type: "success" | "error" | "info", title: string, message?: string) => void;
}

export interface UseFaceAnalysisReturn {
  analyzeFaces: () => Promise<void>;
  runVideoDiagnosis: () => Promise<void>;
  applyDiagnosticRecommendation: (rec: {
    face_detector_model: string;
    face_detector_size: string;
    detection_threshold: number;
    smoothing: number;
  }) => void;
}

export function useFaceAnalysis(options: UseFaceAnalysisOptions): UseFaceAnalysisReturn {
  const { apiUrl, showToast } = options;
  const studio = useStudioState();

  const analyzeFaces = useCallback(async () => {
    if (!studio.state.targetMediaFullPath) {
      showToast("info", "Sem Destino", "Carregue uma mídia de destino primeiro.");
      return;
    }
    studio.set("isAnalyzingTargetFaces", true);
    studio.set("detectedTargetFaces", []);
    studio.set("faceMappings", {});

    const isVideoFile = !!studio.state.targetMediaName.match(/\.(mp4|webm|mkv|avi|mov)$/i);
    const timestamp = isVideoFile ? studio.state.targetVideoTime : null;
    const frameNumber = isVideoFile ? Math.round(studio.state.targetVideoTime * 30) : 0;
    studio.set("referenceFrameNumber", frameNumber);

    try {
      const url = formatApiUrl(apiUrl, "/api/media/analyze-faces");
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          file_path: studio.state.targetMediaFullPath,
          timestamp,
          frame_number: frameNumber,
        }),
      });
      if (!res.ok) throw new Error("Erro na detecção de rostos.");
      const data = await res.json();
      const faces: DetectedFace[] = data.faces || [];
      studio.set("detectedTargetFaces", faces);
      if (faces.length === 0) {
        showToast("info", "Nenhum Rosto", "Nenhum rosto foi encontrado neste frame.");
      } else {
        showToast("success", "Rostos Detectados", `${faces.length} rostos prontos para mapeamento.`);
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      showToast("error", "Erro na Análise", message || "Não foi possível analisar rostos na mídia.");
    } finally {
      studio.set("isAnalyzingTargetFaces", false);
    }
  }, [apiUrl, studio, showToast]);

  const runVideoDiagnosis = useCallback(async () => {
    if (!studio.state.targetMediaFullPath) {
      showToast("info", "Sem Vídeo", "Carregue um vídeo de destino para diagnosticar.");
      return;
    }
    // isDiagnosing is managed by the wizard hook in page.tsx
    try {
      const url = formatApiUrl(apiUrl, "/api/video/diagnose");
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_path: studio.state.targetMediaFullPath }),
      });
      if (!res.ok) throw new Error("Falha ao diagnosticar vídeo.");
      const data: VideoDiagnosticReport = await res.json();
      showToast(
        "success",
        "Diagnóstico Concluído",
        `${data.total_scenes} takes mapeados com recomendações personalizadas.`
      );
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      showToast("error", "Erro no Diagnóstico", message || "Não foi possível analisar o vídeo.");
    } finally {
      // isDiagnosing is managed by the wizard hook in page.tsx
    }
  }, [apiUrl, studio, showToast]);

  const applyDiagnosticRecommendation = useCallback((rec: {
    face_detector_model: string;
    face_detector_size: string;
    detection_threshold: number;
    smoothing: number;
  }) => {
    studio.patch("mask", { detectorModel: rec.face_detector_model });
    studio.patch("mask", { detectorSize: rec.face_detector_size });
    studio.patch("processorOptions", { detection_threshold: rec.detection_threshold });
    studio.patch("processorOptions", { smoothing: rec.smoothing });
    showToast(
      "success",
      "Parâmetros Calibrados",
      `Detector ajustado para ${rec.face_detector_model} com limiar ${rec.detection_threshold} e smoothing ${rec.smoothing}.`
    );
  }, [studio, showToast]);

  return { analyzeFaces, runVideoDiagnosis, applyDiagnosticRecommendation };
}
