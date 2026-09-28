import React from "react";
import { ChevronDown } from "lucide-react";
import { ProcessorCard } from "../ProcessorCard";

/**
 * Face Swapper configuration card. Extracted from ProcessorSettings.tsx
 * (R4 of tech-debt inventory — split 919-LoC monolith into 11 focused cards).
 *
 * Owns: model, pixel_boost, weight, mask_blur, detection_threshold, smoothing.
 */
export interface FaceSwapperCardProps {
  isExpanded: boolean;
  onToggle: (key: string) => void;
  // state + setters
  faceSwapperModel: string;
  setFaceSwapperModel: (v: string) => void;
  faceSwapperPixelBoost: string;
  setFaceSwapperPixelBoost: (v: string) => void;
  faceSwapperWeight: number;
  setFaceSwapperWeight: (v: number) => void;
  faceMaskBlur: number;
  setFaceMaskBlur: (v: number) => void;
  detectionThreshold: number;
  setDetectionThreshold: (v: number) => void;
  smoothing: number;
  setSmoothing: (v: number) => void;
}

export const FaceSwapperCard: React.FC<FaceSwapperCardProps> = ({
  isExpanded,
  onToggle,
  faceSwapperModel,
  setFaceSwapperModel,
  faceSwapperPixelBoost,
  setFaceSwapperPixelBoost,
  faceSwapperWeight,
  setFaceSwapperWeight,
  faceMaskBlur,
  setFaceMaskBlur,
  detectionThreshold,
  setDetectionThreshold,
  smoothing,
  setSmoothing,
}) => {
  return (
    <ProcessorCard
      procKey="face_swapper"
      title="Face Swapper"
      isExpanded={isExpanded}
      onToggle={onToggle}
      subtitle={faceSwapperModel}
    >
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-[10px] font-bold text-zinc-400 block mb-1">Modelo</label>
          <div className="relative">
            <select
              value={faceSwapperModel}
              onChange={(e) => setFaceSwapperModel(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-800 text-xs px-2.5 py-1.5 rounded-lg appearance-none font-bold text-zinc-200 outline-none cursor-pointer focus:border-red-500"
            >
              <option value="inswapper_128_fp16">inswapper_128_fp16</option>
              <option value="inswapper_128">inswapper_128</option>
              <option value="simswap_256">simswap_256</option>
              <option value="simswap_512_unofficial">simswap_512_unofficial</option>
              <option value="blendswap_256">blendswap_256</option>
              <option value="uniface_256">uniface_256</option>
            </select>
            <ChevronDown size={12} className="absolute right-2.5 top-2.5 text-zinc-500 pointer-events-none" />
          </div>
        </div>

        <div>
          <label className="text-[10px] font-bold text-zinc-400 block mb-1">Pixel Boost</label>
          <div className="relative">
            <select
              value={faceSwapperPixelBoost}
              onChange={(e) => setFaceSwapperPixelBoost(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-800 text-xs px-2.5 py-1.5 rounded-lg appearance-none font-bold text-zinc-200 outline-none cursor-pointer focus:border-red-500"
            >
              <option value="None">None (Nenhum)</option>
              <option value="256x256">256x256</option>
              <option value="512x512">512x512</option>
              <option value="768x768">768x768</option>
              <option value="1024x1024">1024x1024</option>
            </select>
            <ChevronDown size={12} className="absolute right-2.5 top-2.5 text-zinc-500 pointer-events-none" />
          </div>
        </div>
      </div>

      <RangeRow label="Peso do Swap" value={faceSwapperWeight} setValue={setFaceSwapperWeight} min={0} max={100} step={1} suffix="%" />
      <RangeRow label="Blur da Máscara" value={faceMaskBlur} setValue={setFaceMaskBlur} min={0} max={100} step={1} suffix="%" />
      <RangeRow label="Limiar de Detecção" value={detectionThreshold} setValue={setDetectionThreshold} min={0} max={100} step={1} suffix="%" />
      <RangeRow label="Suavização" value={smoothing} setValue={setSmoothing} min={0} max={100} step={1} suffix="%" />
    </ProcessorCard>
  );
};

interface RangeRowProps {
  label: string;
  value: number;
  setValue: (v: number) => void;
  min: number;
  max: number;
  step: number;
  suffix?: string;
}

const RangeRow: React.FC<RangeRowProps> = ({ label, value, setValue, min, max, step, suffix }) => (
  <div>
    <div className="flex items-center justify-between mb-1">
      <label className="text-[10px] font-bold text-zinc-400">{label}</label>
      <span className="text-[10px] font-mono text-zinc-500">
        {value}{suffix ?? ""}
      </span>
    </div>
    <input
      type="range"
      min={min}
      max={max}
      step={step}
      value={value}
      onChange={(e) => setValue(Number(e.target.value))}
      className="w-full accent-red-500"
    />
  </div>
);
