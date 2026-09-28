"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { Play, Sparkles, RefreshCw, AlertCircle, Folder, Clock } from "lucide-react";
import { Toast, SourceItem, DetectedFace, Job, Project, VideoDiagnosticReport } from "../types";
import { resolveApiUrl, formatApiUrl, getInitialApiUrl } from "../utils/api";
import { useJobs } from "../hooks/useJobs";
import { useProjects } from "../hooks/useProjects";
import { useHardware } from "../hooks/useHardware";
import { usePresets } from "../hooks/usePresets";
import { useStudioState } from "../hooks/useStudioState";
import { useConfig } from "../hooks/useConfig";
import { useWizard } from "../hooks/useWizard";
import { ToastContainer } from "../components/ToastContainer";
import { Header } from "../components/Header";
import { SourceUploader } from "../components/SourceUploader";
import { TargetMediaViewer } from "../components/TargetMediaViewer";
import { FaceMappingModal } from "../components/FaceMappingModal";
import { ProcessorSettings } from "../components/ProcessorSettings";
import { VideoComparator } from "../components/VideoComparator";
import { ExportSettings } from "../components/ExportSettings";
import { FaceMaskSettings } from "../components/FaceMaskSettings";
import { ProjectsGallery } from "../components/ProjectsGallery";
import { JobsList } from "../components/JobsList";
import { SettingsModal } from "../components/SettingsModal";
import { NewProjectModal } from "../components/NewProjectModal";
import { VideoDiagnosticWizard } from "../components/VideoDiagnosticWizard";
import { StatusBar } from "../components/StatusBar";
import { ConnectionModeBadge } from "../components/ConnectionModeBadge";

export default function Home() {
  // Configuração e conexão com a API
  const [apiUrl, setApiUrl] = useState<string>(getInitialApiUrl());
  const [isBackendConnected, setIsBackendConnected] = useState<boolean>(false);

  // Navegação
  const [activeTab, setActiveTab] = useState<"projects" | "create_new" | "jobs" | "settings">("projects");
  const [projectName, setProjectName] = useState<string>("");
  const [isNewProjectModalOpen, setIsNewProjectModalOpen] = useState<boolean>(false);

  // Toasts
  const [toasts, setToasts] = useState<Toast[]>([]);
  const showToast = useCallback((type: Toast["type"], title: string, message?: string) => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts(prev => [...prev, { id, type, title, message }]);
    setTimeout(() => {
      setToasts(prev => prev.map(t => (t.id === id ? { ...t, exiting: true } : t)));
      setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== id));
      }, 300);
    }, 4000);
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  // Inicializar API URL dinâmica
  useEffect(() => {
    resolveApiUrl().then(url => {
      setApiUrl(url);
    });
  }, []);

  // Custom Hooks
  const { jobs, activeJob, cancelJob, deleteJob, fetchJobs, connectionMode } = useJobs(apiUrl);
  const { projects, fetchProjects, openProjectFolder, deleteProject, createProject } = useProjects(apiUrl);
  const { telemetry, hardwareInfo, availableProviders, fetchHardware } = useHardware(apiUrl);

  const handleCreateNewProject = async (projectData: {
    name: string;
    description: string;
    output_format: string;
    output_video_encoder: string;
    output_video_quality: string;
    output_audio_encoder: string;
    output_audio_quality: number;
    output_audio_volume: number;
    processors: string[];
  }) => {
    const newProj = await createProject(projectData);
    if (newProj) {
      setProjectName(newProj.name);
      setOutputFormat(newProj.output_format ? newProj.output_format.toUpperCase() : "MP4");
      if (newProj.output_video_encoder) setOutputVideoEncoder(newProj.output_video_encoder);
      if (newProj.output_video_quality) setOutputQuality(newProj.output_video_quality);
      if (newProj.output_audio_encoder) setOutputAudioEncoder(newProj.output_audio_encoder);
      if (newProj.output_audio_quality) setOutputAudioQuality(newProj.output_audio_quality);
      if (newProj.output_audio_volume !== undefined) setOutputAudioVolume(newProj.output_audio_volume);
      if (newProj.processors && newProj.processors.length > 0) setSelectedProcessors(newProj.processors);

      // Limpa mídias anteriores para novo início
      setSourceItems([]);
      setSourceImageFullPath(null);
      setTargetMedia(null);
      setTargetMediaFullPath(null);
      setPreviewOutputUrl(null);

      showToast("success", "Projeto Criado", `Projeto "${newProj.name}" criado com sucesso em ~/Vídeos. Abrindo Estúdio...`);
      setActiveTab("create_new");
    } else {
      showToast("error", "Erro", "Não foi possível criar a pasta do projeto.");
      throw new Error("Falha ao criar o projeto.");
    }
  };

  const handleOpenProjectInStudio = (proj: Project) => {
    if (proj.source_url) {
      setSourceImageFullPath(proj.source_url);
      setSourceItems([{
        url: formatApiUrl(apiUrl, proj.source_url),
        file_path: proj.source_url,
        filename: proj.source_files[0] || "origem"
      }]);
    }
    if (proj.target_url) {
      const fullTarget = formatApiUrl(apiUrl, proj.target_url);
      setTargetMedia(fullTarget);
      setTargetMediaFullPath(proj.target_url);
      setTargetMediaName(proj.target_files[0] || "destino");
    }
    setProjectName(proj.name);
    setActiveTab("create_new");
    showToast("info", "Projeto Carregado", `Mídias do projeto "${proj.name}" carregadas no Estúdio.`);
  };
  const {
    presets,
    selectedPresetName,
    setSelectedPresetName,
    newPresetName,
    setNewPresetName,
    saveCustomPreset,
  } = usePresets();

  // Testar conexão com o backend
  useEffect(() => {
    if (apiUrl === null) return;
    const testConnection = async () => {
      try {
        const pingUrl = formatApiUrl(apiUrl, "/api/hardware/devices");
        const res = await fetch(pingUrl);
        setIsBackendConnected(res.ok);
      } catch {
        setIsBackendConnected(false);
      }
    };
    testConnection();
    const interval = setInterval(testConnection, 8000);
    return () => clearInterval(interval);
  }, [apiUrl]);

  // Studio state agregado (substitui 50+ useState do monólito — ver
  // useStudioState.ts para a migration guide completa).
  const studio = useStudioState();
  const {
    sourceItems, sourceImageFullPath,
    targetMedia, targetMediaFullPath, targetMediaName, targetVideoTime,
    detectedTargetFaces, isAnalyzingTargetFaces, selectedFaceForModal,
    faceMappings, referenceFrameNumber,
    selectedProcessors, autoPreview, processorOptions,
    output, mask,
    isPreviewLoading, isGenerating, isDraggingSource, isDraggingTarget, jobToDelete,
  } = studio.state;

  // Aliases de leitura para manter compatibilidade com referências existentes
  // no JSX (que leem `deepSwapperModel` em vez de `processorOptions.deep_swapper_model`).
  const {
    deep_swapper_model: deepSwapperModel,
    deep_swapper_morph: deepSwapperMorph,
    lip_syncer_model: lipSyncerModel,
    lip_syncer_weight: lipSyncerWeight,
    face_debugger_items: faceDebuggerItems,
    frame_colorizer_model: frameColorizerModel,
    frame_colorizer_blend: frameColorizerBlend,
    frame_colorizer_size: frameColorizerSize,
    background_remover_model: backgroundRemoverModel,
    background_remover_color: backgroundRemoverColor,
    face_swapper_weight: faceSwapperWeight,
    face_swapper_model: faceSwapperModel,
    face_swapper_pixel_boost: faceSwapperPixelBoost,
    face_mask_blur: faceMaskBlur,
    detection_threshold: detectionThreshold,
    smoothing,
    face_enhancer_model: faceEnhancerModel,
    face_enhancer_blend: faceEnhancerBlend,
    face_enhancer_weight: faceEnhancerWeight,
    frame_enhancer_model: frameEnhancerModel,
    frame_enhancer_blend: frameEnhancerBlend,
    face_editor_model: faceEditorModel,
    face_editor_smile: faceEditorSmile,
    age_modifier_model: ageModifierModel,
    age_modifier_direction: ageModifierDirection,
    expression_restorer_factor: expressionRestorerFactor,
  } = processorOptions;
  const {
    types: faceMaskTypes,
    padding: faceMaskPadding,
    detectorModel: faceDetectorModel,
    detectorSize: faceDetectorSize,
    detectorAngles: faceDetectorAngles,
    landmarkerModel: faceLandmarkerModel,
    landmarkerScore: faceLandmarkerScore,
  } = mask;
  const {
    format: outputFormat,
    quality: outputQuality,
    videoEncoder: outputVideoEncoder,
    audioEncoder: outputAudioEncoder,
    audioQuality: outputAudioQuality,
    audioVolume: outputAudioVolume,
  } = output;

  // Wrapper setters para manter compatibilidade com o resto do componente.
  // Cada setter é apenas um alias para `studio.set` — zero overhead.
  const setSourceItems = (v: SourceItem[]) => studio.set("sourceItems", v);
  const setSourceImageFullPath = (v: string | null) => studio.set("sourceImageFullPath", v);
  const setTargetMedia = (v: string | null) => studio.set("targetMedia", v);
  const setTargetMediaFullPath = (v: string | null) => studio.set("targetMediaFullPath", v);
  const setTargetMediaName = (v: string) => studio.set("targetMediaName", v);
  const setTargetVideoTime = (v: number) => studio.set("targetVideoTime", v);
  const setDetectedTargetFaces = (v: DetectedFace[]) => studio.set("detectedTargetFaces", v);
  const setIsAnalyzingTargetFaces = (v: boolean) => studio.set("isAnalyzingTargetFaces", v);
  const setSelectedFaceForModal = (v: DetectedFace | null) => studio.set("selectedFaceForModal", v);
  const setFaceMappings = (v: Record<number, string>) => studio.set("faceMappings", v);
  const setReferenceFrameNumber = (v: number) => studio.set("referenceFrameNumber", v);
  const setSelectedProcessors = (v: string[]) => studio.set("selectedProcessors", v);
  const setAutoPreview = (v: boolean) => studio.set("autoPreview", v);
  const setPreviewOutputUrl = (v: string | null) => studio.set("previewOutputUrl", v);
  const setIsPreviewLoading = (v: boolean) => studio.set("isPreviewLoading", v);
  const setIsGenerating = (v: boolean) => studio.set("isGenerating", v);
  const setIsDraggingSource = (v: boolean) => studio.set("isDraggingSource", v);
  const setIsDraggingTarget = (v: boolean) => studio.set("isDraggingTarget", v);
  const setJobToDelete = (v: string | null) => studio.set("jobToDelete", v);

  // Processors adicionais: helpers que fazem patch no sub-objeto
  // `processorOptions` para manter defaults imutáveis.
  const setDeepSwapperModel = (v: string) => studio.patch("processorOptions", { deep_swapper_model: v });
  const setDeepSwapperMorph = (v: number) => studio.patch("processorOptions", { deep_swapper_morph: v });
  const setLipSyncerModel = (v: string) => studio.patch("processorOptions", { lip_syncer_model: v });
  const setLipSyncerWeight = (v: number) => studio.patch("processorOptions", { lip_syncer_weight: v });
  const setFaceDebuggerItems = (v: string[]) => studio.patch("processorOptions", { face_debugger_items: v });
  const setFrameColorizerModel = (v: string) => studio.patch("processorOptions", { frame_colorizer_model: v });
  const setFrameColorizerBlend = (v: number) => studio.patch("processorOptions", { frame_colorizer_blend: v });
  const setFrameColorizerSize = (v: string) => studio.patch("processorOptions", { frame_colorizer_size: v });
  const setBackgroundRemoverModel = (v: string) => studio.patch("processorOptions", { background_remover_model: v });
  const setBackgroundRemoverColor = (v: string) => studio.patch("processorOptions", { background_remover_color: v });
  const setFaceSwapperWeight = (v: number) => studio.patch("processorOptions", { face_swapper_weight: v });
  const setFaceSwapperModel = (v: string) => studio.patch("processorOptions", { face_swapper_model: v });
  const setFaceSwapperPixelBoost = (v: string) => studio.patch("processorOptions", { face_swapper_pixel_boost: v });
  const setFaceMaskBlur = (v: number) => studio.patch("processorOptions", { face_mask_blur: v });
  const setDetectionThreshold = (v: number) => studio.patch("processorOptions", { detection_threshold: v });
  const setSmoothing = (v: number) => studio.patch("processorOptions", { smoothing: v });
  const setFaceEnhancerModel = (v: string) => studio.patch("processorOptions", { face_enhancer_model: v });
  const setFaceEnhancerBlend = (v: number) => studio.patch("processorOptions", { face_enhancer_blend: v });
  const setFaceEnhancerWeight = (v: number) => studio.patch("processorOptions", { face_enhancer_weight: v });
  const setFrameEnhancerModel = (v: string) => studio.patch("processorOptions", { frame_enhancer_model: v });
  const setFrameEnhancerBlend = (v: number) => studio.patch("processorOptions", { frame_enhancer_blend: v });
  const setFaceEditorModel = (v: string) => studio.patch("processorOptions", { face_editor_model: v });
  const setFaceEditorSmile = (v: number) => studio.patch("processorOptions", { face_editor_smile: v });
  const setAgeModifierModel = (v: string) => studio.patch("processorOptions", { age_modifier_model: v });
  const setAgeModifierDirection = (v: number) => studio.patch("processorOptions", { age_modifier_direction: v });
  const setExpressionRestorerFactor = (v: number) => studio.patch("processorOptions", { expression_restorer_factor: v });

  // Mask & detector: patch no sub-objeto `mask`.
  const setFaceMaskTypes = (v: string[]) => studio.patch("mask", { types: v });
  const setFaceMaskPadding = (v: number[]) => studio.patch("mask", { padding: v });
  const setFaceDetectorModel = (v: string) => studio.patch("mask", { detectorModel: v });
  const setFaceDetectorSize = (v: string) => studio.patch("mask", { detectorSize: v });
  const setFaceDetectorAngles = (v: number[]) => studio.patch("mask", { detectorAngles: v });
  const setFaceLandmarkerModel = (v: string) => studio.patch("mask", { landmarkerModel: v });
  const setFaceLandmarkerScore = (v: number) => studio.patch("mask", { landmarkerScore: v });

  // Output: patch no sub-objeto `output`.
  const setOutputFormat = (v: string) => studio.patch("output", { format: v });
  const setOutputQuality = (v: string) => studio.patch("output", { quality: v });
  const setOutputVideoEncoder = (v: string) => studio.patch("output", { videoEncoder: v });
  const setOutputAudioEncoder = (v: string) => studio.patch("output", { audioEncoder: v });
  const setOutputAudioQuality = (v: number) => studio.patch("output", { audioQuality: v });
  const setOutputAudioVolume = (v: number) => studio.patch("output", { audioVolume: v });

  // Estados que permanecem locais (UI/auxiliares de layout).
  const [targetDimensions, setTargetDimensions] = useState<{ width: number; height: number } | null>(null);
  const [containerDimensions, setContainerDimensions] = useState<{ width: number; height: number } | null>(null);
  const targetContainerRef = useRef<HTMLDivElement>(null);

  // Lista estática de processors disponíveis (não é estado mutável).
  const availableProcessors = [
    "face_swapper", "face_enhancer", "frame_enhancer", "face_editor",
    "age_modifier", "expression_restorer", "deep_swapper", "lip_syncer",
    "face_debugger", "frame_colorizer", "background_remover",
  ];

  // Configurações do sistema: hook agregador com fetch inicial + save action.
  const configHook = useConfig(apiUrl);
  const {
    temp_path: configTempPath,
    jobs_path: configJobsPath,
    video_memory_strategy: configMemoryStrategy,
    execution_thread_count: configThreadCount,
    log_level: configLogLevel,
    execution_providers: configProviders,
    is_saving: isSavingConfig,
  } = configHook.config;
  const setConfigTempPath = (v: string) => configHook.set("temp_path", v);
  const setConfigJobsPath = (v: string) => configHook.set("jobs_path", v);
  const setConfigMemoryStrategy = (v: string) => configHook.set("video_memory_strategy", v);
  const setConfigThreadCount = (v: number) => configHook.set("execution_thread_count", v);
  const setConfigLogLevel = (v: string) => configHook.set("log_level", v);
  const setConfigProviders = (v: string[]) => configHook.set("execution_providers", v);
  const setIsSavingConfig = (v: boolean) => configHook.set("is_saving", v);

  // Wizard de diagnóstico: hook encapsula visibilidade + estado do relatório.
  const wizard = useWizard();
  const { isOpen: isWizardOpen, isDiagnosing, report: diagnosticReport } = wizard;
  const setIsWizardOpen = wizard.setIsOpen;
  const setIsDiagnosing = wizard.setLoading;
  const setDiagnosticReport = wizard.setReport;

  // Configurações são carregadas automaticamente pelo hook useConfig
  // (useEffect interno dispara fetch inicial em mount e em mudança de apiUrl).

  // Atualizar dimensões do container de destino para cálculo das caixas faciais
  const updateContainerDimensions = useCallback(() => {
    if (targetContainerRef.current) {
      setContainerDimensions({
        width: targetContainerRef.current.clientWidth,
        height: targetContainerRef.current.clientHeight,
      });
    }
  }, []);

  useEffect(() => {
    updateContainerDimensions();
    window.addEventListener("resize", updateContainerDimensions);
    return () => window.removeEventListener("resize", updateContainerDimensions);
  }, [detectedTargetFaces, targetMedia, updateContainerDimensions]);

  const getScaledBox = useCallback((bbox: number[]) => {
    if (!targetDimensions || !containerDimensions) return null;
    const [x_min, y_min, x_max, y_max] = bbox;
    const Mw = targetDimensions.width;
    const Mh = targetDimensions.height;
    const Cw = containerDimensions.width;
    const Ch = containerDimensions.height;
    if (!Mw || !Mh || !Cw || !Ch) return null;

    const Rm = Mw / Mh;
    const Rc = Cw / Ch;
    let Rw = Cw;
    let Rh = Ch;
    let Ro = 0;
    let To = 0;

    if (Rc > Rm) {
      Rw = Ch * Rm;
      Ro = (Cw - Rw) / 2;
    } else {
      Rh = Cw / Rm;
      To = (Ch - Rh) / 2;
    }

    return {
      left: Ro + (x_min / Mw) * Rw,
      top: To + (y_min / Mh) * Rh,
      width: ((x_max - x_min) / Mw) * Rw,
      height: ((y_max - y_min) / Mh) * Rh,
    };
  }, [targetDimensions, containerDimensions]);

  // Upload file helper
  const uploadFile = async (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    const url = formatApiUrl(apiUrl, "/api/media/upload");
    const res = await fetch(url, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      throw new Error("Falha no upload do arquivo.");
    }
    return await res.json();
  };

  const handleSourceUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      try {
        const data = await uploadFile(file);
        const resolvedUrl = formatApiUrl(apiUrl, data.url);
        const newSource: SourceItem = {
          url: resolvedUrl,
          file_path: data.file_path,
          filename: data.filename,
        };
        setSourceItems(prev => [...prev, newSource]);
        setSourceImageFullPath(data.file_path);
        showToast("success", "Imagem Carregada", file.name);
      } catch {
        showToast("error", "Erro no Upload", `Falha ao enviar ${file.name}`);
      }
    }
  };

  const handleTargetUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const data = await uploadFile(file);
      const resolvedUrl = formatApiUrl(apiUrl, data.url);
      setTargetMedia(resolvedUrl);
      setTargetMediaFullPath(data.file_path);
      setTargetMediaName(data.filename);
      setDetectedTargetFaces([]);
      setFaceMappings({});
      showToast("success", "Mídia de Destino Carregada", file.name);
    } catch {
      showToast("error", "Erro no Upload", "Falha ao enviar mídia de destino.");
    }
  };

  // Drag & drop handlers
  const handleDropSource = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDraggingSource(false);
    const files = e.dataTransfer.files;
    if (!files || files.length === 0) return;
    for (let i = 0; i < files.length; i++) {
      try {
        const data = await uploadFile(files[i]);
        const resolvedUrl = formatApiUrl(apiUrl, data.url);
        setSourceItems(prev => [...prev, { url: resolvedUrl, file_path: data.file_path, filename: data.filename }]);
        setSourceImageFullPath(data.file_path);
        showToast("success", "Imagem Carregada", files[i].name);
      } catch {
        showToast("error", "Erro no Upload", "Falha no envio.");
      }
    }
  };

  const handleDropTarget = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDraggingTarget(false);
    const file = e.dataTransfer.files?.[0];
    if (!file) return;
    try {
      const data = await uploadFile(file);
      const resolvedUrl = formatApiUrl(apiUrl, data.url);
      setTargetMedia(resolvedUrl);
      setTargetMediaFullPath(data.file_path);
      setTargetMediaName(data.filename);
      setDetectedTargetFaces([]);
      setFaceMappings({});
      showToast("success", "Mídia de Destino Carregada", file.name);
    } catch {
      showToast("error", "Erro no Upload", "Falha no envio.");
    }
  };

  // Analisar rostos
  const handleAnalyzeFaces = async () => {
    if (!targetMediaFullPath) return;
    setIsAnalyzingTargetFaces(true);
    setDetectedTargetFaces([]);
    setFaceMappings({});

    const isVideoFile = !!targetMediaName.match(/\.(mp4|webm|mkv|avi|mov)$/i);
    const timestamp = isVideoFile ? targetVideoTime : null;
    const frameNumber = isVideoFile ? Math.round(targetVideoTime * 30) : 0;
    setReferenceFrameNumber(frameNumber);

    try {
      const url = formatApiUrl(apiUrl, "/api/media/analyze-faces");
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          file_path: targetMediaFullPath,
          timestamp,
          frame_number: frameNumber,
        }),
      });
      if (!res.ok) throw new Error("Erro na detecção de rostos.");
      const data = await res.json();
      setDetectedTargetFaces(data.faces || []);
      if ((data.faces || []).length === 0) {
        showToast("info", "Nenhum Rosto", "Nenhum rosto foi encontrado neste frame.");
      } else {
        showToast("success", "Rostos Detectados", `${data.faces.length} rostos prontos para mapeamento.`);
      }
    } catch {
      showToast("error", "Erro na Análise", "Não foi possível analisar rostos na mídia.");
    } finally {
      setIsAnalyzingTargetFaces(false);
    }
  };

  // Executar Assistente de Pré-Análise & Diagnóstico de Vídeo
  const handleRunVideoDiagnosis = async () => {
    if (!targetMediaFullPath) {
      showToast("warning", "Mídia de Destino Ausente", "Carregue um vídeo de destino antes de iniciar o assistente.");
      return;
    }
    const isVideoFile = !!targetMediaName.match(/\.(mp4|webm|mkv|avi|mov)$/i);
    if (!isVideoFile) {
      showToast("info", "Recurso Exclusivo para Vídeos", "O Assistente de Diagnóstico analisa takes e ruído temporal em vídeos.");
      return;
    }

    setIsWizardOpen(true);
    setIsDiagnosing(true);

    try {
      const url = formatApiUrl(apiUrl, "/api/video/diagnose");
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          video_path: targetMediaFullPath,
          max_scenes: 15,
        }),
      });

      if (!res.ok) throw new Error("Falha ao diagnosticar vídeo.");
      const data: VideoDiagnosticReport = await res.json();
      setDiagnosticReport(data);
      showToast("success", "Diagnóstico Concluído", `${data.total_scenes} takes mapeados com recomendações personalizadas.`);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      showToast("error", "Erro no Diagnóstico", message || "Não foi possível analisar o vídeo.");
    } finally {
      setIsDiagnosing(false);
    }
  };

  // Aplicar Recomendações do Assistente
  const handleApplyDiagnosticRecommendation = (rec: {
    face_detector_model: string;
    face_detector_size: string;
    detection_threshold: number;
    reference_face_distance: number;
    smoothing: number;
    face_detector_angles: number[];
    face_landmarker_score: number;
  }) => {
    setFaceDetectorModel(rec.face_detector_model);
    setFaceDetectorSize(rec.face_detector_size);
    setDetectionThreshold(rec.detection_threshold);
    setSmoothing(rec.smoothing);
    setFaceDetectorAngles(rec.face_detector_angles || [0]);
    setFaceLandmarkerScore(rec.face_landmarker_score || 0.5);

    showToast("success", "Parâmetros Calibrados", `Detector ajustado para ${rec.face_detector_model} com limiar ${rec.detection_threshold} e smoothing ${rec.smoothing}.`);
  };

  // Gerar Preview
  const handleGeneratePreview = async (silent = false) => {
    if (!sourceImageFullPath || !targetMediaFullPath) {
      if (!silent) showToast("warning", "Mídia Incompleta", "Selecione origem e destino antes do preview.");
      return;
    }
    setIsPreviewLoading(true);

    const isVideoFile = !!targetMediaName.match(/\.(mp4|webm|mkv|avi|mov)$/i);
    const timestamp = isVideoFile ? targetVideoTime : null;
    const frameNumber = isVideoFile ? Math.round(targetVideoTime * 30) : 0;

    try {
      const url = formatApiUrl(apiUrl, "/api/preview");
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_paths: [sourceImageFullPath],
          target_path: targetMediaFullPath,
          timestamp,
          frame_number: frameNumber,
          processors: selectedProcessors,
          face_swapper_model: faceSwapperModel,
          face_swapper_pixel_boost: faceSwapperPixelBoost,
          face_swapper_weight: faceSwapperWeight,
          face_mask_blur: faceMaskBlur / 50.0,
          detection_threshold: detectionThreshold,
          face_enhancer_model: faceEnhancerModel,
          face_enhancer_blend: faceEnhancerBlend,
          face_enhancer_weight: faceEnhancerWeight,
          frame_enhancer_model: frameEnhancerModel,
          frame_enhancer_blend: frameEnhancerBlend,
          face_editor_model: faceEditorModel,
          face_editor_mouth_smile: faceEditorSmile,
          age_modifier_model: ageModifierModel,
          age_modifier_direction: ageModifierDirection,
          expression_restorer_factor: expressionRestorerFactor,
          deep_swapper_model: deepSwapperModel,
          deep_swapper_morph: deepSwapperMorph,
          lip_syncer_model: lipSyncerModel,
          lip_syncer_weight: lipSyncerWeight,
          face_debugger_items: faceDebuggerItems,
          frame_colorizer_model: frameColorizerModel,
          frame_colorizer_blend: frameColorizerBlend,
          frame_colorizer_size: frameColorizerSize,
          background_remover_model: backgroundRemoverModel,
          background_remover_color: backgroundRemoverColor === "transparent" ? undefined : (backgroundRemoverColor === "black" ? [0, 0, 0] : (backgroundRemoverColor === "white" ? [255, 255, 255] : [0, 255, 0])),
          face_mask_types: faceMaskTypes,
          face_mask_padding: faceMaskPadding,
          face_detector_model: faceDetectorModel,
          face_detector_size: faceDetectorSize,
          face_detector_angles: faceDetectorAngles,
          face_landmarker_model: faceLandmarkerModel,
          face_landmarker_score: faceLandmarkerScore,
        }),
      });

      if (!res.ok) throw new Error("Falha ao gerar preview.");
      const data = await res.json();
      if (data.preview_url) {
        setPreviewOutputUrl(formatApiUrl(apiUrl, data.preview_url));
        if (!silent) showToast("success", "Preview Atualizado", "Novo frame processado.");
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      if (!silent) showToast("error", "Erro no Preview", message || "Falha na pré-visualização.");
    } finally {
      setIsPreviewLoading(false);
    }
  };

  // Preview automático ao trocar opções (debounce)
  useEffect(() => {
    if (!autoPreview || !sourceImageFullPath || !targetMediaFullPath || isGenerating) return;
    const timer = setTimeout(() => {
      handleGeneratePreview(true);
    }, 500);
    return () => clearTimeout(timer);
  }, [
    autoPreview,
    sourceImageFullPath,
    targetMediaFullPath,
    selectedProcessors,
    faceSwapperWeight,
    faceMaskBlur,
    detectionThreshold,
    faceSwapperModel,
    faceSwapperPixelBoost,
    faceEnhancerModel,
    faceEnhancerBlend,
    frameEnhancerModel,
    frameEnhancerBlend,
    faceEditorSmile,
    ageModifierDirection,
    targetVideoTime,
  ]);

  // Iniciar Tarefa Completa (Job)
  const handleGenerateSwap = async () => {
    if (isGenerating) return;
    if (!sourceImageFullPath || !targetMediaFullPath) {
      showToast("warning", "Mídia Incompleta", "Envie a origem e o destino antes de iniciar.");
      return;
    }
    setIsGenerating(true);
    const trimFrameStart = null;
    const mappings = Object.entries(faceMappings).map(([targetIdx, srcPath]) => ({
      source_path: srcPath,
      target_face_index: parseInt(targetIdx, 10),
      reference_frame_number: referenceFrameNumber,
    }));

    const sourcePaths = mappings.length > 0
      ? Array.from(new Set(mappings.map(m => m.source_path)))
      : [sourceImageFullPath];

    try {
      const url = formatApiUrl(apiUrl, "/api/jobs");
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_name: projectName.trim() || undefined,
          source_paths: sourcePaths,
          target_path: targetMediaFullPath,
          face_swapper_weight: faceSwapperWeight,
          face_mask_blur: faceMaskBlur / 50.0,
          detection_threshold: detectionThreshold,
          smoothing: smoothing,
          processors: selectedProcessors,
          output_format: outputFormat.toLowerCase(),
          output_video_encoder: outputVideoEncoder,
          trim_frame_start: trimFrameStart,
          face_swapper_model: faceSwapperModel,
          face_swapper_pixel_boost: faceSwapperPixelBoost,
          face_enhancer_model: faceEnhancerModel,
          face_enhancer_blend: faceEnhancerBlend,
          face_enhancer_weight: faceEnhancerWeight,
          frame_enhancer_model: frameEnhancerModel,
          frame_enhancer_blend: frameEnhancerBlend,
          face_editor_model: faceEditorModel,
          face_editor_mouth_smile: faceEditorSmile,
          age_modifier_model: ageModifierModel,
          age_modifier_direction: ageModifierDirection,
          expression_restorer_factor: expressionRestorerFactor,
          deep_swapper_model: deepSwapperModel,
          deep_swapper_morph: deepSwapperMorph,
          lip_syncer_model: lipSyncerModel,
          lip_syncer_weight: lipSyncerWeight,
          face_debugger_items: faceDebuggerItems,
          frame_colorizer_model: frameColorizerModel,
          frame_colorizer_blend: frameColorizerBlend,
          frame_colorizer_size: frameColorizerSize,
          background_remover_model: backgroundRemoverModel,
          background_remover_color: backgroundRemoverColor === "transparent" ? undefined : (backgroundRemoverColor === "black" ? [0, 0, 0] : (backgroundRemoverColor === "white" ? [255, 255, 255] : [0, 255, 0])),
          output_audio_encoder: outputAudioEncoder === "none" ? undefined : outputAudioEncoder,
          output_audio_quality: outputAudioEncoder === "none" ? undefined : outputAudioQuality,
          output_audio_volume: outputAudioEncoder === "none" ? 0 : outputAudioVolume,
          face_mask_types: faceMaskTypes,
          face_mask_padding: faceMaskPadding,
          face_detector_model: faceDetectorModel,
          face_detector_size: faceDetectorSize,
          face_detector_angles: faceDetectorAngles,
          face_landmarker_model: faceLandmarkerModel,
          face_landmarker_score: faceLandmarkerScore,
          mappings: mappings.length > 0 ? mappings : undefined,
        }),
      });

      if (!res.ok) throw new Error("Falha ao submeter job.");
      const data = await res.json();
      showToast("success", "Projeto Criado", `Subpasta criada em ~/Vídeos: ${data.project_name || data.job_id}`);
      await fetchJobs();
      fetchProjects();
      setProjectName("");
      setActiveTab("jobs");
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      showToast("error", "Erro ao Criar Tarefa", message || "Falha na conexão.");
    } finally {
      setIsGenerating(false);
    }
  };

  // Salvar Configurações
  const handleSaveConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSavingConfig(true);
    try {
      const url = formatApiUrl(apiUrl, "/api/config");
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          temp_path: configTempPath,
          jobs_path: configJobsPath,
          video_memory_strategy: configMemoryStrategy,
          execution_thread_count: configThreadCount,
          log_level: configLogLevel,
          execution_providers: configProviders,
        }),
      });
      if (!res.ok) throw new Error("Erro ao salvar.");
      showToast("success", "Configurações Salvas", "Novos parâmetros registrados.");
    } catch {
      showToast("error", "Erro", "Não foi possível persistir as configurações.");
    } finally {
      setIsSavingConfig(false);
    }
  };

  // Exportar Diagnóstico
  const handleExportDiagnostic = () => {
    const url = formatApiUrl(apiUrl, "/api/diagnostic/export");
    const a = document.createElement("a");
    a.href = url;
    a.download = "facefusion_diagnostic.zip";
    document.body.appendChild(a);
    a.click();
    a.remove();
    showToast("info", "Diagnóstico", "Download do pacote de logs iniciado.");
  };

  // Download do Resultado
  const handleDownloadOutput = () => {
    if (!previewOutputUrl) return;
    const a = document.createElement("a");
    a.href = previewOutputUrl;
    a.download = "facefusion_output";
    document.body.appendChild(a);
    a.click();
    a.remove();
    showToast("info", "Download", "Arquivo sendo transferido.");
  };

  // Toggle Processor Selection
  const toggleProcessor = (proc: string) => {
    setSelectedProcessors(prev =>
      prev.includes(proc) ? prev.filter(p => p !== proc) : [...prev, proc]
    );
  };

  // Presets Handlers
  const handleApplyPreset = (name: string) => {
    const preset = presets.find(p => p.name === name);
    if (!preset) return;
    setSelectedPresetName(name);
    setFaceSwapperWeight(preset.faceSwapperWeight);
    setFaceMaskBlur(preset.faceMaskBlur);
    setDetectionThreshold(preset.detectionThreshold);
    setSmoothing(preset.smoothing);
    setFaceSwapperModel(preset.faceSwapperModel);
    setFaceSwapperPixelBoost(preset.faceSwapperPixelBoost);
    if (preset.faceEnhancerModel) setFaceEnhancerModel(preset.faceEnhancerModel);
    if (preset.faceEnhancerBlend !== undefined) setFaceEnhancerBlend(preset.faceEnhancerBlend);
    if (preset.frameEnhancerModel) setFrameEnhancerModel(preset.frameEnhancerModel);
    if (preset.frameEnhancerBlend !== undefined) setFrameEnhancerBlend(preset.frameEnhancerBlend);
    showToast("success", "Preset Aplicado", preset.name);
  };

  const handleSaveCurrentPreset = () => {
    const success = saveCustomPreset(
      {
        faceSwapperWeight,
        faceMaskBlur,
        detectionThreshold,
        smoothing,
        faceSwapperModel,
        faceSwapperPixelBoost,
        faceEnhancerModel,
        faceEnhancerBlend,
        faceEnhancerWeight,
        frameEnhancerModel,
        frameEnhancerBlend,
      },
      newPresetName
    );
    if (success) {
      showToast("success", "Preset Salvo", newPresetName);
    } else {
      showToast("warning", "Nome Inválido", "Informe um nome válido para o preset.");
    }
  };

  // Carregar job para o comparador
  const handleLoadToComparator = (job: Job) => {
    if (job.outputUrl) {
      setPreviewOutputUrl(formatApiUrl(apiUrl, job.outputUrl));
      setActiveTab("create_new");
      showToast("info", "Job Carregado", `Visualizando resultado de ${job.id}`);
    }
  };

  // Confirmar exclusão de job
  const handleDeleteJobConfirmed = async () => {
    if (!jobToDelete) return;
    const res = await deleteJob(jobToDelete);
    if (res.success) {
      showToast("success", "Job Excluído", `Tarefa ${jobToDelete} removida.`);
    } else {
      showToast("error", "Erro ao Excluir", res.message);
    }
    setJobToDelete(null);
  };

  const queuedCount = jobs.filter(j => j.status === "processing" || j.status === "queued").length;

  return (
    <div className="flex flex-col h-screen bg-[#0a0a0a] text-[#ededed] font-sans overflow-hidden">
      {/* Toast Notifications */}
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />

      {/* Top Header with Centered Tabs */}
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        queuedCount={queuedCount}
      />

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col overflow-hidden">

        {/* Workspace Body */}
        <div className="flex-1 p-4 md:p-6 flex flex-col overflow-hidden">
          {/* TAB 1: CRIAR NOVO */}
          {activeTab === "create_new" && (
            <div className="flex-1 flex flex-col overflow-hidden space-y-4 animate-fade-in">
              {/* Active Job Progress Bar */}
              {activeJob && (
                <div className={`flex items-center gap-3 bg-zinc-950/50 border rounded-xl px-4 py-2.5 flex-shrink-0 animate-fade-in ${
                  activeJob.status === "queued" || (activeJob.status === "idle" && activeJob.progress === 0)
                    ? "border-emerald-500/30 shadow-sm shadow-emerald-950/20"
                    : "border-zinc-900 shadow-sm shadow-amber-950/20"
                }`}>
                  {activeJob.status === "queued" || (activeJob.status === "idle" && activeJob.progress === 0) ? (
                    <Clock size={15} className="text-emerald-400 flex-shrink-0" />
                  ) : (
                    <RefreshCw size={15} className="text-amber-500 animate-spin flex-shrink-0" />
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-bold text-zinc-300 truncate">{activeJob.id}</span>
                      <span className={`text-xs font-mono font-bold ${
                        activeJob.status === "queued" || (activeJob.status === "idle" && activeJob.progress === 0)
                          ? "text-emerald-400"
                          : "text-amber-500"
                      }`}>
                        {activeJob.progress}%
                      </span>
                    </div>
                    <div className="w-full h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-700 ease-out ${
                          activeJob.status === "queued" || (activeJob.status === "idle" && activeJob.progress === 0)
                            ? "bg-gradient-to-r from-emerald-500 to-teal-400"
                            : "bg-gradient-to-r from-amber-500 to-red-500"
                        }`}
                        style={{ width: `${Math.max(activeJob.progress, 4)}%` }}
                      />
                    </div>
                  </div>
                  <span className={`text-[10px] font-extrabold uppercase tracking-wider px-2.5 py-0.5 rounded-full flex-shrink-0 border ${
                    activeJob.status === "queued" || (activeJob.status === "idle" && activeJob.progress === 0)
                      ? "text-emerald-400 bg-emerald-500/15 border-emerald-500/30"
                      : "text-amber-400 bg-amber-500/15 border-amber-500/30 animate-pulse"
                  }`}>
                    {activeJob.status === "queued" || (activeJob.status === "idle" && activeJob.progress === 0)
                      ? "Aguardando"
                      : (activeJob.step || "Processando")}
                  </span>
                </div>
              )}

              {/* 3-Column Creative Suite Layout (25% / 40% / 35%) */}
              <div className="grid grid-cols-1 lg:grid-cols-[25%_minmax(0,1fr)_35%] gap-4 flex-1 overflow-hidden">
                {/* COLUNA 1: MÍDIAS DE ENTRADA (25%) */}
                <div className="flex flex-col gap-3.5 overflow-hidden h-full">
                  <div className="flex-[0.9] min-h-[170px] overflow-hidden">
                    <SourceUploader
                      sourceItems={sourceItems}
                      sourceImageFullPath={sourceImageFullPath}
                      onSelectSource={(item) => setSourceImageFullPath(item.file_path)}
                      onRemoveSource={(idx) => {
                        const next = sourceItems.filter((_, i) => i !== idx);
                        setSourceItems(next);
                        if (next.length > 0) setSourceImageFullPath(next[0].file_path);
                        else setSourceImageFullPath(null);
                      }}
                      onUpload={handleSourceUpload}
                      isDragging={isDraggingSource}
                      onDragOver={(e) => { e.preventDefault(); setIsDraggingSource(true); }}
                      onDragLeave={() => setIsDraggingSource(false)}
                      onDrop={handleDropSource}
                    />
                  </div>

                  <div className="flex-[1.1] min-h-[220px] overflow-hidden">
                    <TargetMediaViewer
                      targetMedia={targetMedia}
                      targetMediaName={targetMediaName}
                      onUpload={handleTargetUpload}
                      onClear={() => {
                        setTargetMedia(null);
                        setTargetMediaFullPath(null);
                        setTargetMediaName("");
                        setDetectedTargetFaces([]);
                        setFaceMappings({});
                      }}
                      detectedFaces={detectedTargetFaces}
                      faceMappings={faceMappings}
                      onSelectFace={(face) => setSelectedFaceForModal(face)}
                      isAnalyzing={isAnalyzingTargetFaces}
                      onAnalyzeFaces={handleAnalyzeFaces}
                      targetVideoTime={targetVideoTime}
                      setTargetVideoTime={setTargetVideoTime}
                      isDragging={isDraggingTarget}
                      onDragOver={(e) => { e.preventDefault(); setIsDraggingTarget(true); }}
                      onDragLeave={() => setIsDraggingTarget(false)}
                      onDrop={handleDropTarget}
                      getScaledBox={getScaledBox}
                      targetContainerRef={targetContainerRef}
                      setTargetDimensions={setTargetDimensions}
                      onOpenWizard={handleRunVideoDiagnosis}
                      isDiagnosing={isDiagnosing}
                    />
                  </div>
                </div>

                {/* COLUNA 2: MONITOR CENTRAL DE VISUALIZAÇÃO (40%) */}
                <div className="flex flex-col gap-3.5 overflow-hidden h-full">
                  {/* Visualização de Resultado (Topo) */}
                  <div className="flex-1 min-h-[220px] overflow-hidden">
                    <VideoComparator
                      previewOutputUrl={previewOutputUrl}
                      onDownloadOutput={handleDownloadOutput}
                    />
                  </div>

                  {/* Espaço Inferior dividido em 2 Colunas: Esquerda (Exportação) | Direita (Detecção Facial & Máscaras) */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 flex-shrink-0 min-h-[175px]">
                    {/* Sub-coluna Esquerda: Opções de Exportação */}
                    <ExportSettings
                      outputFormat={outputFormat}
                      setOutputFormat={setOutputFormat}
                      outputQuality={outputQuality}
                      setOutputQuality={setOutputQuality}
                      outputVideoEncoder={outputVideoEncoder}
                      setOutputVideoEncoder={setOutputVideoEncoder}
                      outputAudioEncoder={outputAudioEncoder}
                      setOutputAudioEncoder={setOutputAudioEncoder}
                      outputAudioQuality={outputAudioQuality}
                      setOutputAudioQuality={setOutputAudioQuality}
                      outputAudioVolume={outputAudioVolume}
                      setOutputAudioVolume={setOutputAudioVolume}
                    />

                    {/* Sub-coluna Direita: Detecção Facial & Máscaras */}
                    <FaceMaskSettings
                      faceMaskTypes={faceMaskTypes}
                      setFaceMaskTypes={setFaceMaskTypes}
                      faceMaskPadding={faceMaskPadding}
                      setFaceMaskPadding={setFaceMaskPadding}
                      faceDetectorModel={faceDetectorModel}
                      setFaceDetectorModel={setFaceDetectorModel}
                      faceDetectorSize={faceDetectorSize}
                      setFaceDetectorSize={setFaceDetectorSize}
                      faceDetectorAngles={faceDetectorAngles}
                      setFaceDetectorAngles={setFaceDetectorAngles}
                      faceLandmarkerModel={faceLandmarkerModel}
                      setFaceLandmarkerModel={setFaceLandmarkerModel}
                      faceLandmarkerScore={faceLandmarkerScore}
                      setFaceLandmarkerScore={setFaceLandmarkerScore}
                    />
                  </div>
                </div>

                {/* COLUNA 3: INSPETOR DE PROCESSADORES & RENDERING (35%) */}
                <div className="flex flex-col gap-3 overflow-hidden h-full bg-zinc-950/40 border border-zinc-900/90 rounded-2xl p-3.5 shadow-xl">
                  <div className="flex-1 overflow-hidden flex flex-col">
                    <ProcessorSettings
                      availableProcessors={availableProcessors}
                      selectedProcessors={selectedProcessors}
                      onToggleProcessor={toggleProcessor}
                      autoPreview={autoPreview}
                      setAutoPreview={setAutoPreview}
                      presets={presets}
                      selectedPresetName={selectedPresetName}
                      onApplyPreset={handleApplyPreset}
                      newPresetName={newPresetName}
                      setNewPresetName={setNewPresetName}
                      onSavePreset={handleSaveCurrentPreset}
                      faceSwapperWeight={faceSwapperWeight}
                      setFaceSwapperWeight={setFaceSwapperWeight}
                      faceMaskBlur={faceMaskBlur}
                      setFaceMaskBlur={setFaceMaskBlur}
                      detectionThreshold={detectionThreshold}
                      setDetectionThreshold={setDetectionThreshold}
                      smoothing={smoothing}
                      setSmoothing={setSmoothing}
                      faceSwapperModel={faceSwapperModel}
                      setFaceSwapperModel={setFaceSwapperModel}
                      faceSwapperPixelBoost={faceSwapperPixelBoost}
                      setFaceSwapperPixelBoost={setFaceSwapperPixelBoost}
                      faceEnhancerModel={faceEnhancerModel}
                      setFaceEnhancerModel={setFaceEnhancerModel}
                      faceEnhancerBlend={faceEnhancerBlend}
                      setFaceEnhancerBlend={setFaceEnhancerBlend}
                      faceEnhancerWeight={faceEnhancerWeight}
                      setFaceEnhancerWeight={setFaceEnhancerWeight}
                      frameEnhancerModel={frameEnhancerModel}
                      setFrameEnhancerModel={setFrameEnhancerModel}
                      frameEnhancerBlend={frameEnhancerBlend}
                      setFrameEnhancerBlend={setFrameEnhancerBlend}
                      faceEditorModel={faceEditorModel}
                      setFaceEditorModel={setFaceEditorModel}
                      faceEditorSmile={faceEditorSmile}
                      setFaceEditorSmile={setFaceEditorSmile}
                      ageModifierModel={ageModifierModel}
                      setAgeModifierModel={setAgeModifierModel}
                      ageModifierDirection={ageModifierDirection}
                      setAgeModifierDirection={setAgeModifierDirection}
                      expressionRestorerFactor={expressionRestorerFactor}
                      setExpressionRestorerFactor={setExpressionRestorerFactor}
                      deepSwapperModel={deepSwapperModel}
                      setDeepSwapperModel={setDeepSwapperModel}
                      deepSwapperMorph={deepSwapperMorph}
                      setDeepSwapperMorph={setDeepSwapperMorph}
                      lipSyncerModel={lipSyncerModel}
                      setLipSyncerModel={setLipSyncerModel}
                      lipSyncerWeight={lipSyncerWeight}
                      setLipSyncerWeight={setLipSyncerWeight}
                      faceDebuggerItems={faceDebuggerItems}
                      setFaceDebuggerItems={setFaceDebuggerItems}
                      frameColorizerModel={frameColorizerModel}
                      setFrameColorizerModel={setFrameColorizerModel}
                      frameColorizerBlend={frameColorizerBlend}
                      setFrameColorizerBlend={setFrameColorizerBlend}
                      frameColorizerSize={frameColorizerSize}
                      setFrameColorizerSize={setFrameColorizerSize}
                      backgroundRemoverModel={backgroundRemoverModel}
                      setBackgroundRemoverModel={setBackgroundRemoverModel}
                      backgroundRemoverColor={backgroundRemoverColor}
                      setBackgroundRemoverColor={setBackgroundRemoverColor}
                    />
                  </div>

                  {/* Base do Inspetor: Disparo de Processamento */}
                  <div className="pt-2 border-t border-zinc-900/80 flex-shrink-0">
                    <button
                      onClick={handleGenerateSwap}
                      disabled={isGenerating || !sourceImageFullPath || !targetMediaFullPath}
                      className="w-full bg-gradient-to-r from-red-600 to-red-700 hover:from-red-500 hover:to-red-600 text-white font-black py-3 rounded-xl text-xs tracking-widest uppercase transition-all shadow-lg shadow-red-600/30 flex items-center justify-center gap-2 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed active:scale-[0.99]"
                    >
                      {isGenerating ? <RefreshCw size={15} className="animate-spin" /> : <Sparkles size={15} />}
                      INICIAR PROCESSAMENTO
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 1: PROJETOS (Galeria no disco em ~/Vídeos/FaceFusion_Projects) */}
          {activeTab === "projects" && (
            <ProjectsGallery
              projects={projects}
              apiUrl={apiUrl}
              onOpenFolder={async (name) => {
                const ok = await openProjectFolder(name);
                if (ok) showToast("success", "Pasta Aberta", `Abrindo pasta do projeto "${name}" no explorador de arquivos.`);
                else showToast("error", "Erro", "Não foi possível abrir a pasta.");
                return ok;
              }}
              onDeleteProject={async (name) => {
                const ok = await deleteProject(name);
                if (ok) {
                  showToast("info", "Projeto Excluído", `Projeto "${name}" removido do disco.`);
                  fetchJobs();
                } else {
                  showToast("error", "Erro", "Não foi possível excluir o projeto.");
                }
                return ok;
              }}
              onOpenInStudio={handleOpenProjectInStudio}
              onRequestNewProject={() => setIsNewProjectModalOpen(true)}
              onRefresh={fetchProjects}
            />
          )}

          {/* TAB 3: JOBS (Fila de Renderização) */}
          {activeTab === "jobs" && (
            <JobsList
              jobs={jobs}
              onLoadToComparator={handleLoadToComparator}
              onRequestDelete={(id) => setJobToDelete(id)}
              onCancelJob={async (id) => {
                const ok = await cancelJob(id);
                if (ok) showToast("info", "Cancelamento", `Sinal de cancelamento enviado para ${id}.`);
                else showToast("error", "Erro", "Não foi possível cancelar.");
              }}
              onNavigateToStudio={() => setActiveTab("create_new")}
            />
          )}

          {/* TAB 3: CONFIGURAÇÕES */}
          {activeTab === "settings" && (
            <SettingsModal
              apiUrl={apiUrl}
              configTempPath={configTempPath}
              setConfigTempPath={setConfigTempPath}
              configJobsPath={configJobsPath}
              setConfigJobsPath={setConfigJobsPath}
              configMemoryStrategy={configMemoryStrategy}
              setConfigMemoryStrategy={setConfigMemoryStrategy}
              configThreadCount={configThreadCount}
              setConfigThreadCount={setConfigThreadCount}
              configLogLevel={configLogLevel}
              setConfigLogLevel={setConfigLogLevel}
              configProviders={configProviders}
              setConfigProviders={setConfigProviders}
              availableProviders={availableProviders}
              isSavingConfig={isSavingConfig}
              onSaveConfig={handleSaveConfig}
              onExportDiagnostic={handleExportDiagnostic}
              showToast={showToast}
            />
          )}
        </div>
      </main>

      {/* Modal de Mapeamento de Rosto */}
      <FaceMappingModal
        apiUrl={apiUrl}
        selectedFace={selectedFaceForModal}
        onClose={() => setSelectedFaceForModal(null)}
        sourceItems={sourceItems}
        faceMappings={faceMappings}
        onSelectMapping={(faceIdx, sourcePath) => {
          setFaceMappings(prev => {
            const next = { ...prev };
            if (sourcePath) {
              next[faceIdx] = sourcePath;
            } else {
              delete next[faceIdx];
            }
            return next;
          });
          setSelectedFaceForModal(null);
        }}
      />

      {/* Modal de Confirmação de Exclusão */}
      {jobToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-fade-in">
          <div className="bg-zinc-950 border border-zinc-900 rounded-2xl p-6 w-full max-w-md shadow-2xl shadow-black/80">
            <h3 className="text-base font-bold text-white mb-2 flex items-center gap-2">
              <AlertCircle size={18} className="text-red-500" /> Confirmar Exclusão
            </h3>
            <p className="text-xs text-zinc-400 mb-6 leading-relaxed">
              Deseja realmente excluir a tarefa <span className="text-red-500 font-mono font-bold">{jobToDelete}</span>?
              Esta ação removerá todos os arquivos e mídias associados do disco.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setJobToDelete(null)}
                className="px-4 py-2 rounded-lg text-xs font-bold bg-zinc-900 hover:bg-zinc-800 text-zinc-300 border border-zinc-800 transition-all cursor-pointer"
              >
                Cancelar
              </button>
              <button
                onClick={handleDeleteJobConfirmed}
                className="px-4 py-2 rounded-lg text-xs font-bold bg-red-600 hover:bg-red-500 text-white shadow-lg shadow-red-600/20 transition-all cursor-pointer"
              >
                Excluir Tarefa
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal de Criação de Novo Projeto */}
      <NewProjectModal
        isOpen={isNewProjectModalOpen}
        onClose={() => setIsNewProjectModalOpen(false)}
        onCreateProject={handleCreateNewProject}
        availableProcessors={availableProcessors}
      />

      {/* Assistente de Pré-Análise & Diagnóstico de Vídeo */}
      <VideoDiagnosticWizard
        isOpen={isWizardOpen}
        onClose={() => setIsWizardOpen(false)}
        report={diagnosticReport}
        isLoading={isDiagnosing}
        onApplyRecommendation={handleApplyDiagnosticRecommendation}
        onJumpToSceneTimestamp={(sec) => {
          setTargetVideoTime(sec);
          showToast("info", "Navegação por Take", `Posicionado em ${sec.toFixed(1)}s`);
        }}
      />

      {/* Bottom Status Bar */}
      <StatusBar
        telemetry={telemetry}
        hardwareInfo={hardwareInfo}
        isBackendConnected={isBackendConnected}
        onRefreshHardware={fetchHardware}
        connectionMode={connectionMode}
      />
    </div>
  );
}
