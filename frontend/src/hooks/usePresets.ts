import { useState, useEffect, useCallback } from "react";
import { Preset } from "../types";

export const BUILT_IN_PRESETS: Preset[] = [
  {
    name: "Qualidade Máxima (Padrão)",
    faceSwapperWeight: 0.85,
    faceMaskBlur: 12,
    detectionThreshold: 0.70,
    smoothing: 5,
    faceSwapperModel: "inswapper_128_fp16",
    faceSwapperPixelBoost: "512x512",
    faceEnhancerModel: "gfpgan_1.4",
    faceEnhancerBlend: 80,
    faceEnhancerWeight: 1.0,
    frameEnhancerModel: "span_kendata_x4",
    frameEnhancerBlend: 80,
    isCustom: false
  },
  {
    name: "Draft Rápido",
    faceSwapperWeight: 0.70,
    faceMaskBlur: 8,
    detectionThreshold: 0.50,
    smoothing: 3,
    faceSwapperModel: "inswapper_128",
    faceSwapperPixelBoost: "",
    faceEnhancerModel: "gfpgan_1.4",
    faceEnhancerBlend: 50,
    faceEnhancerWeight: 0.5,
    frameEnhancerModel: "span_kendata_x4",
    frameEnhancerBlend: 50,
    isCustom: false
  },
  {
    name: "Cinemático Ultra",
    faceSwapperWeight: 0.90,
    faceMaskBlur: 15,
    detectionThreshold: 0.75,
    smoothing: 8,
    faceSwapperModel: "simswap_unofficial_512",
    faceSwapperPixelBoost: "1024x1024",
    faceEnhancerModel: "codeformer",
    faceEnhancerBlend: 90,
    faceEnhancerWeight: 1.0,
    frameEnhancerModel: "real_esrgan_x4_fp16",
    frameEnhancerBlend: 90,
    isCustom: false
  }
];

export function usePresets() {
  const [presets, setPresets] = useState<Preset[]>(BUILT_IN_PRESETS);
  const [selectedPresetName, setSelectedPresetName] = useState<string>("Qualidade Máxima (Padrão)");
  const [newPresetName, setNewPresetName] = useState<string>("");

  useEffect(() => {
    try {
      const saved = localStorage.getItem("youface_presets");
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed)) {
          const customs = parsed.filter(p => p.isCustom);
          setPresets([...BUILT_IN_PRESETS, ...customs]);
        }
      }
    } catch (e) {
      console.error("Erro ao carregar presets:", e);
    }
  }, []);

  const saveCustomPreset = useCallback((presetData: Omit<Preset, "name" | "isCustom">, name: string): boolean => {
    if (!name.trim()) return false;
    const newPreset: Preset = {
      ...presetData,
      name: name.trim(),
      isCustom: true
    };
    const updated = [...presets.filter(p => p.name !== newPreset.name), newPreset];
    setPresets(updated);
    setSelectedPresetName(newPreset.name);
    setNewPresetName("");

    try {
      const customs = updated.filter(p => p.isCustom);
      localStorage.setItem("youface_presets", JSON.stringify(customs));
      return true;
    } catch {
      return false;
    }
  }, [presets]);

  return {
    presets,
    selectedPresetName,
    setSelectedPresetName,
    newPresetName,
    setNewPresetName,
    saveCustomPreset,
  };
}
