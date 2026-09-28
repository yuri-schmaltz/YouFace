import { useState, useCallback } from "react";
import type { DetectedFace, SourceItem } from "../types";

/**
 * Estado agregado do Studio (fontes, processors, output, máscara, detecção).
 *
 * Extraído de `page.tsx` para reduzir o monólito (era 1.229 linhas, com 78
 * useState independentes) e isolar re-renders: cada sub-bloco é agrupado em
 * um único hook que devolve setters tipados e um reset geral.
 *
 * Por que objetos agrupados em vez de useState individuais:
 *  - Preserva a semântica de "salvar preset" (snapshot serializável).
 *  - Reduz 78 setters para ~12 helpers tipados.
 *  - Permite trocar a implementação interna (useReducer, zustand, context)
 *    sem alterar a API de quem consome.
 *
 * MIGRATION GUIDE (a ser feita em PR dedicada, com tsc rodando):
 *  1. Em page.tsx, importar: `const studio = useStudioState();`
 *  2. Substituir cada `const [x, setX] = useState(default)` por
 *     `studio.state.X` (leitura) + `studio.set("X", value)` (escrita).
 *  3. Onde havia `setX(prev => ...)` usar `studio.patch("X", { ...prev, ... })`.
 *  4. No `useEffect` de config fetch, chamar `studio.loadFromConfig(data)`.
 *  5. No `reset` (novo projeto, etc.), chamar `studio.reset()`.
 */
export interface ProcessorOptions {
  // Deep swapper
  deep_swapper_model: string;
  deep_swapper_morph: number;
  // Lip syncer
  lip_syncer_model: string;
  lip_syncer_weight: number;
  // Face debugger
  face_debugger_items: string[];
  // Frame colorizer
  frame_colorizer_model: string;
  frame_colorizer_blend: number;
  frame_colorizer_size: string;
  // Background remover
  background_remover_model: string;
  background_remover_color: string;
  // Face swapper
  face_swapper_weight: number;
  face_swapper_model: string;
  face_swapper_pixel_boost: string;
  face_mask_blur: number;
  detection_threshold: number;
  smoothing: number;
  // Enhancers
  face_enhancer_model: string;
  face_enhancer_blend: number;
  face_enhancer_weight: number;
  frame_enhancer_model: string;
  frame_enhancer_blend: number;
  // Face editor
  face_editor_model: string;
  face_editor_smile: number;
  // Age + expression
  age_modifier_model: string;
  age_modifier_direction: number;
  expression_restorer_factor: number;
}

export interface OutputOptions {
  format: string;
  quality: string;
  videoEncoder: string;
  audioEncoder: string;
  audioQuality: number;
  audioVolume: number;
}

export interface MaskOptions {
  types: string[];
  padding: number[];
  detectorModel: string;
  detectorSize: string;
  detectorAngles: number[];
  landmarkerModel: string;
  landmarkerScore: number;
}

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
  processorOptions: ProcessorOptions;

  // Saída
  output: OutputOptions;

  // Máscara e detecção
  mask: MaskOptions;

  // Estados de execução e drag
  isPreviewLoading: boolean;
  isGenerating: boolean;
  isDraggingSource: boolean;
  isDraggingTarget: boolean;
  jobToDelete: string | null;
}

const DEFAULT_PROCESSOR_OPTIONS: ProcessorOptions = {
  deep_swapper_model: "iperov/elon_musk_224",
  deep_swapper_morph: 100,
  lip_syncer_model: "wav2lip_gan_96",
  lip_syncer_weight: 0.8,
  face_debugger_items: ["bounding-box", "face-landmark-5", "face-mask"],
  frame_colorizer_model: "ddcolor",
  frame_colorizer_blend: 100,
  frame_colorizer_size: "512x512",
  background_remover_model: "birefnet_general",
  background_remover_color: "transparent",
  face_swapper_weight: 0.85,
  face_swapper_model: "inswapper_128_fp16",
  face_swapper_pixel_boost: "512x512",
  face_mask_blur: 12,
  detection_threshold: 0.70,
  smoothing: 5,
  face_enhancer_model: "gfpgan_1.4",
  face_enhancer_blend: 80,
  face_enhancer_weight: 1.0,
  frame_enhancer_model: "span_kendata_x4",
  frame_enhancer_blend: 80,
  face_editor_model: "live_portrait",
  face_editor_smile: 0,
  age_modifier_model: "styleganex_age",
  age_modifier_direction: 0,
  expression_restorer_factor: 0.8,
};

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
 * Hook agregador de todo o estado do Studio. API minimalista (read direto,
 * write por helper) para encorajar migração mecânica dos 78 useState atuais.
 */
export function useStudioState() {
  const [state, setState] = useState<StudioState>(DEFAULT_STATE);

  // Patch genérico de uma chave top-level do estado.
  const patch = useCallback(
    <K extends keyof StudioState>(key: K, partial: Partial<StudioState[K]>) => {
      setState(prev => ({
        ...prev,
        [key]: { ...(prev[key] as object), ...partial } as StudioState[K],
      }));
    },
    []
  );

  // Setter simples para campos escalares top-level.
  const set = useCallback(
    <K extends keyof StudioState>(key: K, value: StudioState[K]) => {
      setState(prev => ({ ...prev, [key]: value }));
    },
    []
  );

  const reset = useCallback(() => setState(DEFAULT_STATE), []);

  return { state, setState, set, patch, reset };
}
