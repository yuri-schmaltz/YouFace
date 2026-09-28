import { useCallback } from "react";
import { formatApiUrl } from "../utils/api";
import type { SourceItem } from "../types";
import { useStudioState } from "./useStudioState";

/**
 * Media upload hook. Encapsulates POST /api/media/upload and updates the
 * Studio state with the returned file_path / url.
 *
 * Extracted from page.tsx (handlers: handleSourceUpload,
 * handleTargetUpload, handleDropSource, handleDropTarget). All four
 * were inline async functions calling fetch + setX; the new hook
 * keeps the API surface (returns nothing; sets state via useStudioState).
 */
export interface UploadResult {
  url: string;
  file_path: string;
  filename: string;
}

export interface UseMediaUploadReturn {
  uploadFile: (file: File) => Promise<UploadResult>;
  handleSourceUpload: (files: File[]) => Promise<void>;
  handleTargetUpload: (file: File) => Promise<void>;
  handleDropSource: (dataTransferFiles: FileList) => Promise<void>;
  handleDropTarget: (dataTransferFiles: FileList) => Promise<void>;
}

export interface UseMediaUploadOptions {
  apiUrl: string;
  showToast: (type: "success" | "error" | "info", title: string, message?: string) => void;
}

export function useMediaUpload(options: UseMediaUploadOptions): UseMediaUploadReturn {
  const { apiUrl, showToast } = options;
  const studio = useStudioState();

  const uploadFile = useCallback(async (file: File): Promise<UploadResult> => {
    const formData = new FormData();
    formData.append("file", file);
    const url = formatApiUrl(apiUrl, "/api/media/upload");
    const res = await fetch(url, { method: "POST", body: formData });
    if (!res.ok) {
      throw new Error("Falha no upload do arquivo.");
    }
    return (await res.json()) as UploadResult;
  }, [apiUrl]);

  const handleSourceUpload = useCallback(async (files: File[]) => {
    for (const file of files) {
      try {
        const data = await uploadFile(file);
        const resolvedUrl = formatApiUrl(apiUrl, data.url);
        const newSource: SourceItem = {
          url: resolvedUrl,
          file_path: data.file_path,
          filename: data.filename,
        };
        studio.set("sourceItems", [...studio.state.sourceItems, newSource]);
        studio.set("sourceImageFullPath", data.file_path);
        showToast("success", "Imagem Carregada", file.name);
      } catch {
        showToast("error", "Erro no Upload", `Falha ao enviar ${file.name}`);
      }
    }
  }, [apiUrl, studio, uploadFile, showToast]);

  const handleTargetUpload = useCallback(async (file: File) => {
    try {
      const data = await uploadFile(file);
      const resolvedUrl = formatApiUrl(apiUrl, data.url);
      studio.set("targetMedia", resolvedUrl);
      studio.set("targetMediaFullPath", data.file_path);
      studio.set("targetMediaName", data.filename);
      studio.set("detectedTargetFaces", []);
      studio.set("faceMappings", {});
      showToast("success", "Mídia de Destino Carregada", file.name);
    } catch {
      showToast("error", "Erro no Upload", "Falha ao enviar mídia de destino.");
    }
  }, [apiUrl, studio, uploadFile, showToast]);

  const handleDropSource = useCallback(async (dataTransferFiles: FileList) => {
    studio.set("isDraggingSource", false);
    const files = Array.from(dataTransferFiles);
    if (files.length === 0) return;
    await handleSourceUpload(files);
  }, [studio, handleSourceUpload]);

  const handleDropTarget = useCallback(async (dataTransferFiles: FileList) => {
    studio.set("isDraggingTarget", false);
    const file = dataTransferFiles[0];
    if (!file) return;
    await handleTargetUpload(file);
  }, [studio, handleTargetUpload]);

  return {
    uploadFile,
    handleSourceUpload,
    handleTargetUpload,
    handleDropSource,
    handleDropTarget,
  };
}
