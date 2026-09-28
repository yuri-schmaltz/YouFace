import { useState, useCallback } from "react";
import type { DetectedFace, SourceItem } from "../types";

/**
 * Estado agregado do Studio (fontes, processors, output, máscara, detecção).
 *
 * Extraído de `page.tsx` para reduzir o monólito e isolar re-renders: cada
 * sub-bloco é agrupado em um único hook que devolve setters e getters, e
 * pode ser substituído por context/redux se a complexidade aumentar.
 *
 * Padrão intencional: objetos agrupados em vez de dezenas de useState
 * independentes, porque isso preserva a semântica de "salvar preset" sem
 * precisar enumerar cada setter.
 */
export interface StudioState {
  // Mídia
  sourceItems: SourceItem[];
  sourceImageFullPath: string | null;
  targetMedia: string | null;
  targetMediaFullPath: string | null;
  targetMediaName: string;
  targetVideoTime: number;
  previewOutputUrl: string | null;

  // Mapeamento de múltiplos rostos
  detectedTargetFaces: DetectedFace[];
  isAnalyzingTargetFaces: boolean;
  selectedFaceForModal: DetectedFace | null;
  faceMappings: Record<number, string>;
  referenceFrameNumber: number;

  // Processadores selecionados
  selectedProcessors: string[];
  autoPreview: boolean;

  // Opções dos 11 processadores
  processorOptions: Record<string, unknown>;

  // Saída
  output: {
    format: string;
    quality: string;
    videoEncoder: string;
    audioEncoder: string;
    audioQuality: number;
    audioVolume: number;
  };

  // Máscara e detecção
  mask: {
    types: string[];
    padding: number[];
    detectorModel: string;
    detectorSize: string;
    detectorAngles: number[];
    landmarkerModel: string;
    landmarkerScore: number;
  };

  // Estados de execução e drag
  isPreviewLoading: boolean;
  isGenerating: boolean;
  isDraggingSource: boolean;
  isDraggingTarget: boolean;
  jobToDelete: string | null;
}

const DEFAULT_PROCESSOR_OPTIONS = {
  // Deep swapper
  deep_swapper_model: "iperov/elon_musk_224",
  deep_swapper_morph: 100,
  // Lip syncer
  lip_syncer_model: "wav2lip_gan_96",
  lip_syncer_weight: 0.8,
  // Face debugger
  face_debugger_items: ["bounding-box", "face-landmark-5", "face-mask"],
  // Frame colorizer
  frame_colorizer_model: "ddcolor",
  frame_colorizer_blend: 100,
  frame_colorizer_size: "512x512",
  // Background remover
  background_remover_model: "birefnet_general",
  background_remover_color: "transparent",
  // Face swapper
  face_swapper_weight: 0.85,
  face_swapper_model: "inswapper_128_fp16",
  face_swapper_pixel_boost: "512x512",
  face_mask_blur: 12,
  detection_threshold: 0.70,
  smoothing: 5,
  // Enhancers
  face_enhancer_model: "gfpgan_1.4",
  face_enhancer_blend: 80,
  face_enhancer_weight: 1.0,
  frame_enhancer_model: "span_kendata_x4",
  frame_enhancer_blend: 80,
  // Face editor
  face_editor_model: "live_portrait",
  face_editor_smile: 0,
  // Age + expression
  age_modifier_model: "styleganex_age",
  age_modifier_direction: 0,
  expression_restorer_factor: 0.8,
} as const;

const DEFAULT_STATE: StudioState = {
  sourceItems: [],
  sourceImageFullPath: null,
  targetMedia: null,
  targetMediaFullPath: null,
  targetMediaName: "",
  targetVideoTime: 0,
  previewOutputUrl: null,

  detectedTargetFaces: [],
  isAnalyzingTargetFaces: false,
  selectedFaceForModal: null,
  faceMappings: {},
  referenceFrameNumber: 0,

  selectedProcessors: ["face_swapper"],
  autoPreview: true,

  processorOptions: { ...DEFAULT_PROCESSOR_OPTIONS },

  output: {
    format: "MP4",
    quality: "High",
    videoEncoder: "libx264",
    audioEncoder: "aac",
    audioQuality: 80,
    audioVolume: 100,
  },

  mask: {
    types: ["box", "occlusion"],
    padding: [0, 0, 0, 0],
    detectorModel: "yolo_face",
    detectorSize: "640x640",
    detectorAngles: [0],
    landmarkerModel: "2dfan4",
    landmarkerScore: 0.5,
  },

  isPreviewLoading: false,
  isGenerating: false,
  isDraggingSource: false,
  isDraggingTarget: false,
  jobToDelete: null,
};

/**
 * Hook agregador de todo o estado do Studio.
 *
 * Cada sub-bloco pode ser consumido individualmente ou em conjunto — o retorno
 * preserva a forma original (objetos aninhados) para que a migração do
 * `page.tsx` seja mecânica.
 */
export function useStudioState() {
  const [state, setState] = useState<StudioState>(DEFAULT_STATE);

  const patch = useCallback(<K extends keyof StudioState>(key: K, partial: Partial<StudioState[K]>) => {
    setState(prev => ({ ...prev, [key]: { ...(prev[key] as object), ...partial } as StudioState[K] }));
  }, []);

  const reset = useCallback(() => setState(DEFAULT_STATE), []);

  return { state, setState, patch, reset };
}