import React, { useCallback } from "react";
import { formatApiUrl } from "../utils/api";
import type { Project, SourceItem } from "../types";

/**
 * Project actions hook. Encapsulates the lifecycle handlers around
 * `createProject` and the studio-state hydration that follows it.
 * Extracted from page.tsx (handleCreateNewProject, handleOpenProjectInStudio).
 *
 * Side effects (studio state setters) are passed in by the page because
 * they live in page-local useState. The hook only orchestrates the
 * async + business rules.
 */
export interface CreateProjectInput {
  name: string;
  description: string;
  output_format: string;
  output_video_encoder: string;
  output_video_quality: string;
  output_audio_encoder: string;
  output_audio_quality: number;
  output_audio_volume: number;
  processors: string[];
}

export interface StudioSetters {
  setProjectName: (name: string) => void;
  setOutputFormat: (fmt: string) => void;
  setOutputVideoEncoder: (e: string) => void;
  setOutputQuality: (q: string) => void;
  setOutputAudioEncoder: (e: string) => void;
  setOutputAudioQuality: (q: number) => void;
  setOutputAudioVolume: (v: number) => void;
  setSelectedProcessors: React.Dispatch<React.SetStateAction<string[]>>;
  setSourceItems: React.Dispatch<React.SetStateAction<SourceItem[]>>;
  setSourceImageFullPath: (p: string | null) => void;
  setTargetMedia: (m: string | null) => void;
  setTargetMediaFullPath: (p: string | null) => void;
  setTargetMediaName: (n: string) => void;
  setPreviewOutputUrl: (u: string | null) => void;
  setActiveTab: (tab: string) => void;
}

export interface UseProjectActionsOptions {
  apiUrl: string;
  createProject: (data: CreateProjectInput) => Promise<Project | null>;
  showToast: (type: "success" | "error" | "info", title: string, message?: string) => void;
  setters: StudioSetters;
}

export interface UseProjectActionsReturn {
  handleCreateNewProject: (data: CreateProjectInput) => Promise<void>;
  handleOpenProjectInStudio: (proj: Project) => void;
}

export function useProjectActions(options: UseProjectActionsOptions): UseProjectActionsReturn {
  const { apiUrl, createProject, showToast, setters } = options;

  const handleCreateNewProject = useCallback(
    async (projectData: CreateProjectInput) => {
      const newProj = await createProject(projectData);
      if (!newProj) {
        showToast("error", "Erro", "Não foi possível criar a pasta do projeto.");
        throw new Error("Falha ao criar o projeto.");
      }

      setters.setProjectName(newProj.name);
      setters.setOutputFormat(newProj.output_format ? newProj.output_format.toUpperCase() : "MP4");
      if (newProj.output_video_encoder) setters.setOutputVideoEncoder(newProj.output_video_encoder);
      if (newProj.output_video_quality) setters.setOutputQuality(newProj.output_video_quality);
      if (newProj.output_audio_encoder) setters.setOutputAudioEncoder(newProj.output_audio_encoder);
      if (newProj.output_audio_quality !== undefined) setters.setOutputAudioQuality(newProj.output_audio_quality);
      if (newProj.output_audio_volume !== undefined) setters.setOutputAudioVolume(newProj.output_audio_volume);
      if (newProj.processors && newProj.processors.length > 0) setters.setSelectedProcessors(newProj.processors);

      // Limpa mídias anteriores para novo início
      setters.setSourceItems([]);
      setters.setSourceImageFullPath(null);
      setters.setTargetMedia(null);
      setters.setTargetMediaFullPath(null);
      setters.setPreviewOutputUrl(null);

      showToast(
        "success",
        "Projeto Criado",
        `Projeto "${newProj.name}" criado com sucesso em ~/Vídeos. Abrindo Estúdio...`,
      );
      setters.setActiveTab("create_new");
    },
    [createProject, showToast, setters],
  );

  const handleOpenProjectInStudio = useCallback(
    (proj: Project) => {
      if (proj.source_url) {
        setters.setSourceImageFullPath(proj.source_url);
        setters.setSourceItems([{
          url: formatApiUrl(apiUrl, proj.source_url),
          file_path: proj.source_url,
          filename: proj.source_files[0] || "origem",
        }]);
      }
      if (proj.target_url) {
        const fullTarget = formatApiUrl(apiUrl, proj.target_url);
        setters.setTargetMedia(fullTarget);
        setters.setTargetMediaFullPath(proj.target_url);
        setters.setTargetMediaName(proj.target_files[0] || "destino");
      }
      setters.setProjectName(proj.name);
      setters.setActiveTab("create_new");
      showToast("info", "Projeto Carregado", `Mídias do projeto "${proj.name}" carregadas no Estúdio.`);
    },
    [apiUrl, showToast, setters],
  );

  return { handleCreateNewProject, handleOpenProjectInStudio };
}
