import { useCallback } from "react";
import type { Preset } from "../types";

// Re-export so callers can still do `import type { Preset } from ".../usePresetActions"`.
export type { Preset } from "../types";

/**
 * Preset actions hook. Handles the apply/save preset handlers that
 * were previously inline in page.tsx. Setters come from page-local
 * state to keep the hook side-effect-free.
 */

export interface PresetSetters {
  setSelectedPresetName: (name: string) => void;
  setFaceSwapperWeight: (v: number) => void;
  setFaceMaskBlur: (v: number) => void;
  setDetectionThreshold: (v: number) => void;
  setSmoothing: (v: number) => void;
  setFaceSwapperModel: (v: string) => void;
  setFaceSwapperPixelBoost: (v: string) => void;
  setFaceEnhancerModel: (v: string) => void;
  setFaceEnhancerBlend: (v: number) => void;
  setFrameEnhancerModel: (v: string) => void;
  setFrameEnhancerBlend: (v: number) => void;
}

export interface UsePresetActionsOptions {
  presets: Preset[];
  saveCustomPreset: (data: Omit<Preset, "name" | "isCustom">, name: string) => boolean;
  newPresetName: string;
  showToast: (type: "success" | "error" | "info" | "warning", title: string, message?: string) => void;
  setters: PresetSetters;
  // Read-only access to the live state values needed for saveCurrentPreset.
  current: {
    faceSwapperWeight: number;
    faceMaskBlur: number;
    detectionThreshold: number;
    smoothing: number;
    faceSwapperModel: string;
    faceSwapperPixelBoost: string;
    faceEnhancerModel: string;
    faceEnhancerBlend: number;
    faceEnhancerWeight: number;
    frameEnhancerModel: string;
    frameEnhancerBlend: number;
  };
}

export interface UsePresetActionsReturn {
  handleApplyPreset: (name: string) => void;
  handleSaveCurrentPreset: () => void;
}

export function usePresetActions(options: UsePresetActionsOptions): UsePresetActionsReturn {
  const { presets, saveCustomPreset, newPresetName, showToast, setters, current } = options;

  const handleApplyPreset = useCallback(
    (name: string) => {
      const preset = presets.find((p) => p.name === name);
      if (!preset) return;
      setters.setSelectedPresetName(name);
      setters.setFaceSwapperWeight(preset.faceSwapperWeight);
      setters.setFaceMaskBlur(preset.faceMaskBlur);
      setters.setDetectionThreshold(preset.detectionThreshold);
      setters.setSmoothing(preset.smoothing);
      setters.setFaceSwapperModel(preset.faceSwapperModel);
      setters.setFaceSwapperPixelBoost(preset.faceSwapperPixelBoost);
      if (preset.faceEnhancerModel) setters.setFaceEnhancerModel(preset.faceEnhancerModel);
      if (preset.faceEnhancerBlend !== undefined) setters.setFaceEnhancerBlend(preset.faceEnhancerBlend);
      if (preset.frameEnhancerModel) setters.setFrameEnhancerModel(preset.frameEnhancerModel);
      if (preset.frameEnhancerBlend !== undefined) setters.setFrameEnhancerBlend(preset.frameEnhancerBlend);
      showToast("success", "Preset Aplicado", preset.name);
    },
    [presets, showToast, setters],
  );

  const handleSaveCurrentPreset = useCallback(
    () => {
      const success = saveCustomPreset(
        {
          faceSwapperWeight: current.faceSwapperWeight,
          faceMaskBlur: current.faceMaskBlur,
          detectionThreshold: current.detectionThreshold,
          smoothing: current.smoothing,
          faceSwapperModel: current.faceSwapperModel,
          faceSwapperPixelBoost: current.faceSwapperPixelBoost,
          faceEnhancerModel: current.faceEnhancerModel,
          faceEnhancerBlend: current.faceEnhancerBlend,
          faceEnhancerWeight: current.faceEnhancerWeight,
          frameEnhancerModel: current.frameEnhancerModel,
          frameEnhancerBlend: current.frameEnhancerBlend,
        },
        newPresetName,
      );
      if (success) {
        showToast("success", "Preset Salvo", newPresetName);
      } else {
        showToast("warning", "Nome Inválido", "Informe um nome válido para o preset.");
      }
    },
    [saveCustomPreset, newPresetName, showToast, current],
  );

  return { handleApplyPreset, handleSaveCurrentPreset };
}
