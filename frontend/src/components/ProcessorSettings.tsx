import React, { useState } from "react";
import { Cpu, Sliders, Save, ChevronDown, ChevronUp, Sparkles, Wand2, RefreshCw, Palette, Layers, Mic, Eye, Scissors } from "lucide-react";
import { Preset } from "../types";
import { FaceSwapperCard } from "./processorCards/FaceSwapperCard";

interface ProcessorSettingsProps {
  availableProcessors: string[];
  selectedProcessors: string[];
  onToggleProcessor: (proc: string) => void;
  autoPreview: boolean;
  setAutoPreview: (val: boolean) => void;
  // Presets
  presets: Preset[];
  selectedPresetName: string;
  onApplyPreset: (name: string) => void;
  newPresetName: string;
  setNewPresetName: (name: string) => void;
  onSavePreset: () => void;
  // Swapper state
  faceSwapperWeight: number;
  setFaceSwapperWeight: (val: number) => void;
  faceMaskBlur: number;
  setFaceMaskBlur: (val: number) => void;
  detectionThreshold: number;
  setDetectionThreshold: (val: number) => void;
  smoothing: number;
  setSmoothing: (val: number) => void;
  faceSwapperModel: string;
  setFaceSwapperModel: (val: string) => void;
  faceSwapperPixelBoost: string;
  setFaceSwapperPixelBoost: (val: string) => void;
  // Enhancers state
  faceEnhancerModel: string;
  setFaceEnhancerModel: (val: string) => void;
  faceEnhancerBlend: number;
  setFaceEnhancerBlend: (val: number) => void;
  faceEnhancerWeight: number;
  setFaceEnhancerWeight: (val: number) => void;
  frameEnhancerModel: string;
  setFrameEnhancerModel: (val: string) => void;
  frameEnhancerBlend: number;
  setFrameEnhancerBlend: (val: number) => void;
  // Face Editor state
  faceEditorModel: string;
  setFaceEditorModel: (val: string) => void;
  faceEditorSmile: number;
  setFaceEditorSmile: (val: number) => void;
  // Age Modifier state
  ageModifierModel: string;
  setAgeModifierModel: (val: string) => void;
  ageModifierDirection: number;
  setAgeModifierDirection: (val: number) => void;
  // Expression Restorer state
  expressionRestorerFactor: number;
  setExpressionRestorerFactor: (val: number) => void;
  // 5 Processadores Adicionais
  deepSwapperModel?: string;
  setDeepSwapperModel?: (val: string) => void;
  deepSwapperMorph?: number;
  setDeepSwapperMorph?: (val: number) => void;
  lipSyncerModel?: string;
  setLipSyncerModel?: (val: string) => void;
  lipSyncerWeight?: number;
  setLipSyncerWeight?: (val: number) => void;
  faceDebuggerItems?: string[];
  setFaceDebuggerItems?: (val: string[]) => void;
  frameColorizerModel?: string;
  setFrameColorizerModel?: (val: string) => void;
  frameColorizerBlend?: number;
  setFrameColorizerBlend?: (val: number) => void;
  frameColorizerSize?: string;
  setFrameColorizerSize?: (val: string) => void;
  backgroundRemoverModel?: string;
  setBackgroundRemoverModel?: (val: string) => void;
  backgroundRemoverColor?: string;
  setBackgroundRemoverColor?: (val: string) => void;
}

export const ProcessorSettings: React.FC<ProcessorSettingsProps> = ({
  availableProcessors,
  selectedProcessors,
  onToggleProcessor,
  autoPreview,
  setAutoPreview,
  presets,
  selectedPresetName,
  onApplyPreset,
  newPresetName,
  setNewPresetName,
  onSavePreset,
  faceSwapperWeight,
  setFaceSwapperWeight,
  faceMaskBlur,
  setFaceMaskBlur,
  detectionThreshold,
  setDetectionThreshold,
  smoothing,
  setSmoothing,
  faceSwapperModel,
  setFaceSwapperModel,
  faceSwapperPixelBoost,
  setFaceSwapperPixelBoost,
  faceEnhancerModel,
  setFaceEnhancerModel,
  faceEnhancerBlend,
  setFaceEnhancerBlend,
  faceEnhancerWeight,
  setFaceEnhancerWeight,
  frameEnhancerModel,
  setFrameEnhancerModel,
  frameEnhancerBlend,
  setFrameEnhancerBlend,
  faceEditorModel,
  setFaceEditorModel,
  faceEditorSmile,
  setFaceEditorSmile,
  ageModifierModel,
  setAgeModifierModel,
  ageModifierDirection,
  setAgeModifierDirection,
  expressionRestorerFactor,
  setExpressionRestorerFactor,
  deepSwapperModel = "inswapper_128",
  setDeepSwapperModel,
  deepSwapperMorph = 0.5,
  setDeepSwapperMorph,
  lipSyncerModel = "wav2lip",
  setLipSyncerModel,
  lipSyncerWeight = 0.8,
  setLipSyncerWeight,
  faceDebuggerItems = ["kps", "face-mask"],
  setFaceDebuggerItems,
  frameColorizerModel = "deoldify",
  setFrameColorizerModel,
  frameColorizerBlend = 0.8,
  setFrameColorizerBlend,
  frameColorizerSize = "512x512",
  setFrameColorizerSize,
  backgroundRemoverModel = "birefnet_general",
  setBackgroundRemoverModel,
  backgroundRemoverColor = "transparent",
  setBackgroundRemoverColor,
}) => {
  const [isAdvancedDetectionExpanded, setIsAdvancedDetectionExpanded] = useState<boolean>(false);
  // Controle de sanfona (accordion) individual para cada um dos 11 processadores
  const [expandedCards, setExpandedCards] = useState<Record<string, boolean>>({
    face_swapper: true,
    face_enhancer: false,
    frame_enhancer: false,
    face_editor: false,
    age_modifier: false,
    expression_restorer: false,
    deep_swapper: true,
    lip_syncer: false,
    face_debugger: false,
    frame_colorizer: false,
    background_remover: false,
  });

  const toggleExpand = (proc: string) => {
    setExpandedCards((prev) => ({
      ...prev,
      [proc]: !prev[proc],
    }));
  };

  const getProcessorTitle = (proc: string) => {
    switch (proc) {
      case "face_swapper": return "FACE SWAPPER";
      case "face_enhancer": return "FACE ENHANCER";
      case "frame_enhancer": return "FRAME ENHANCER";
      case "face_editor": return "FACE EDITOR";
      case "age_modifier": return "AGE MODIFIER";
      case "expression_restorer": return "EXPRESSION RESTORER";
      case "deep_swapper": return "DEEP SWAPPER";
      case "lip_syncer": return "LIP SYNCER";
      case "face_debugger": return "FACE DEBUGGER";
      case "frame_colorizer": return "FRAME COLORIZER";
      case "background_remover": return "BACKGROUND REMOVER";
      default: return proc.replace(/_/g, " ").toUpperCase();
    }
  };

  const toggleDebuggerItem = (item: string) => {
    if (!setFaceDebuggerItems) return;
    if (faceDebuggerItems.includes(item)) {
      setFaceDebuggerItems(faceDebuggerItems.filter((i) => i !== item));
    } else {
      setFaceDebuggerItems([...faceDebuggerItems, item]);
    }
  };

  return (
    <div className="flex flex-col h-full space-y-3 overflow-hidden select-none">
      {/* 1. Header do Inspetor: Chips de Processadores Ativos (Todos os 11) */}
      <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl p-3 flex flex-col gap-2 flex-shrink-0 shadow-inner">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 text-white font-extrabold text-xs tracking-wide">
              <Cpu size={14} className="text-red-500" />
              <span>Processadores</span>
            </div>

            {/* Combobox de Presets ao lado do título */}
            <div className="relative">
              <select
                value={selectedPresetName}
                onChange={(e) => onApplyPreset(e.target.value)}
                className="bg-zinc-950/80 border border-zinc-750 hover:border-red-500/50 text-zinc-200 text-[10px] font-bold pl-6 pr-6 py-1 rounded-md appearance-none outline-none cursor-pointer transition-colors shadow-sm"
                title="Carregar predefinição de processadores e ajustes"
              >
                {presets.map((preset) => (
                  <option key={preset.name} value={preset.name} className="bg-zinc-900 text-zinc-200 py-1">
                    {preset.name}
                  </option>
                ))}
              </select>
              <Wand2 size={11} className="absolute left-2 top-1/2 -translate-y-1/2 text-amber-400 pointer-events-none" />
              <ChevronDown size={11} className="absolute right-1.5 top-1/2 -translate-y-1/2 text-zinc-400 pointer-events-none" />
            </div>
          </div>

          <label className="flex items-center gap-1.5 cursor-pointer select-none" title="Atualiza o preview automaticamente ao alterar qualquer controle">
            <input
              type="checkbox"
              checked={autoPreview}
              onChange={(e) => setAutoPreview(e.target.checked)}
              className="w-3.5 h-3.5 accent-red-600 rounded cursor-pointer"
            />
            <span className="text-[10px] text-zinc-400 font-bold hover:text-zinc-200 transition-colors">
              Auto Preview
            </span>
          </label>
        </div>

        {/* Grade de Ativação Rápida dos 11 Processadores */}
        <div className="grid grid-cols-3 gap-1.5 max-h-[145px] overflow-y-auto pr-0.5 custom-scrollbar">
          {availableProcessors.map((proc) => {
            const isSelected = selectedProcessors.includes(proc);
            return (
              <button
                key={proc}
                type="button"
                onClick={() => onToggleProcessor(proc)}
                className={`flex items-center justify-between px-2 py-1.5 rounded-lg border text-[9.5px] font-bold transition-all duration-200 cursor-pointer ${
                  isSelected
                    ? "bg-red-600/20 border-red-500/50 text-red-400 shadow-sm"
                    : "bg-zinc-950/40 border-zinc-800 text-zinc-500 hover:border-zinc-700 hover:text-zinc-300"
                }`}
              >
                <span className="truncate">{getProcessorTitle(proc)}</span>
                <span
                  className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ml-1 transition-colors ${
                    isSelected ? "bg-red-500 shadow-sm shadow-red-500" : "bg-zinc-700"
                  }`}
                />
              </button>
            );
          })}
        </div>
      </div>

      {/* 2. Container dos Cards Sanfonados de Ajuste (Scroll Vertical dos Ativos) */}
      <div className="flex-1 overflow-y-auto pr-1 space-y-2.5 custom-scrollbar">
        {selectedProcessors.length === 0 && (
          <div className="p-8 text-center bg-zinc-900/30 border border-zinc-800/80 rounded-xl">
            <Cpu size={28} className="mx-auto text-zinc-600 mb-2" />
            <p className="text-xs font-bold text-zinc-400">Nenhum processador ativo</p>
            <p className="text-[10px] text-zinc-500 mt-1">Selecione um ou mais processadores nos botões acima.</p>
          </div>
        )}

        {/* CARD 1: FACE SWAPPER (extracted to processorCards/FaceSwapperCard) */}
        {selectedProcessors.includes("face_swapper") && (
          <FaceSwapperCard
            isExpanded={expandedCards["face_swapper"] || false}
            onToggle={toggleExpand}
            faceSwapperModel={faceSwapperModel}
            setFaceSwapperModel={setFaceSwapperModel}
            faceSwapperPixelBoost={faceSwapperPixelBoost}
            setFaceSwapperPixelBoost={setFaceSwapperPixelBoost}
            faceSwapperWeight={faceSwapperWeight}
            setFaceSwapperWeight={setFaceSwapperWeight}
            faceMaskBlur={faceMaskBlur}
            setFaceMaskBlur={setFaceMaskBlur}
            detectionThreshold={detectionThreshold}
            setDetectionThreshold={setDetectionThreshold}
            smoothing={smoothing}
            setSmoothing={setSmoothing}
          />
        )}

        {/* CARD 2: DEEP SWAPPER (Modelos de Celebridades & DeepFakes Especializados) */}
        {selectedProcessors.includes("deep_swapper") && (
          <div className="bg-zinc-950/60 border border-indigo-500/30 rounded-xl overflow-hidden shadow-lg shadow-indigo-950/20 transition-all">
            <div
              onClick={() => toggleExpand("deep_swapper")}
              className="px-3.5 py-2.5 bg-zinc-900/70 hover:bg-zinc-900 cursor-pointer flex items-center justify-between border-b border-zinc-800"
            >
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse shadow-sm shadow-indigo-500" />
                <span className="text-xs font-black text-white tracking-wider">
                  {getProcessorTitle("deep_swapper")}
                </span>
              </div>
              <div className="flex items-center gap-2 text-zinc-400">
                <span className="text-[10px] font-mono text-zinc-500 truncate max-w-[150px]">{deepSwapperModel}</span>
                {expandedCards["deep_swapper"] ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </div>
            </div>

            {expandedCards["deep_swapper"] && (
              <div className="p-3.5 space-y-3 animate-fade-in">
                <div>
                  <label className="text-[10px] font-bold text-zinc-400 block mb-1">Modelo Pré-Treinado</label>
                  <div className="relative">
                    <select
                      value={deepSwapperModel}
                      onChange={(e) => setDeepSwapperModel?.(e.target.value)}
                      className="w-full bg-zinc-900 border border-zinc-800 text-xs px-2.5 py-1.5 rounded-lg appearance-none font-bold text-zinc-200 outline-none cursor-pointer focus:border-indigo-500 font-mono"
                    >
                      <option value="iperov/elon_musk_224">Elon Musk (iperov 224)</option>
                      <option value="iperov/keanu_reeves_320">Keanu Reeves (iperov 320)</option>
                      <option value="iperov/scarlett_johansson_224">Scarlett Johansson (iperov 224)</option>
                      <option value="iperov/thomas_cruise_224">Tom Cruise (iperov 224)</option>
                      <option value="iperov/robert_downey_224">Robert Downey Jr (iperov 224)</option>
                      <option value="iperov/margot_robbie_224">Margot Robbie (iperov 224)</option>
                      <option value="druuzil/angelina_jolie_384">Angelina Jolie (druuzil 384)</option>
                      <option value="druuzil/bradley_pitt_224">Brad Pitt (druuzil 224)</option>
                      <option value="druuzil/christian_bale_320">Christian Bale (druuzil 320)</option>
                      <option value="druuzil/cillian_murphy_320">Cillian Murphy (druuzil 320)</option>
                      <option value="druuzil/henry_cavill_448">Henry Cavill (druuzil 448)</option>
                      <option value="rumateus/taylor_swift_224">Taylor Swift (rumateus 224)</option>
                      <option value="rumateus/john_cena_224">John Cena (rumateus 224)</option>
                    </select>
                    <ChevronDown size={12} className="absolute right-2.5 top-2.5 text-zinc-500 pointer-events-none" />
                  </div>
                </div>

                <div className="space-y-1">
                  <div className="flex justify-between text-xs font-bold">
                    <span className="text-zinc-300">Morph Intensity</span>
                    <span className="text-indigo-400 font-mono font-bold">{deepSwapperMorph}%</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    step="1"
                    value={deepSwapperMorph}
                    onChange={(e) => setDeepSwapperMorph?.(parseInt(e.target.value))}
                    className="w-full accent-indigo-500 h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer"
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {/* CARD 3: LIP SYNCER (Sincronização Labial com Áudio) */}
        {selectedProcessors.includes("lip_syncer") && (
          <div className="bg-zinc-950/60 border border-rose-500/30 rounded-xl overflow-hidden shadow-lg shadow-rose-950/20 transition-all">
            <div
              onClick={() => toggleExpand("lip_syncer")}
              className="px-3.5 py-2.5 bg-zinc-900/70 hover:bg-zinc-900 cursor-pointer flex items-center justify-between border-b border-zinc-800"
            >
              <div className="flex items-center gap-2">
                <Mic size={13} className="text-rose-400" />
                <span className="text-xs font-black text-white tracking-wider">
                  {getProcessorTitle("lip_syncer")}
                </span>
              </div>
              <div className="flex items-center gap-2 text-zinc-400">
                <span className="text-[10px] font-mono text-zinc-500">{lipSyncerModel}</span>
                {expandedCards["lip_syncer"] ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </div>
            </div>

            {expandedCards["lip_syncer"] && (
              <div className="p-3.5 space-y-3 animate-fade-in">
                <div>
                  <label className="text-[10px] font-bold text-zinc-400 block mb-1">Modelo Wav2Lip</label>
                  <div className="relative">
                    <select
                      value={lipSyncerModel}
                      onChange={(e) => setLipSyncerModel?.(e.target.value)}
                      className="w-full bg-zinc-900 border border-zinc-800 text-xs px-2.5 py-1.5 rounded-lg appearance-none font-bold text-zinc-200 outline-none cursor-pointer focus:border-rose-500"
                    >
                      <option value="wav2lip_gan_96">wav2lip_gan_96 (Alta Fidelidade)</option>
                      <option value="wav2lip_96">wav2lip_96 (Padrão)</option>
                    </select>
                    <ChevronDown size={12} className="absolute right-2.5 top-2.5 text-zinc-500 pointer-events-none" />
                  </div>
                </div>

                <div className="space-y-1">
                  <div className="flex justify-between text-xs font-bold">
                    <span className="text-zinc-300">Peso do Sincronismo Labial</span>
                    <span className="text-rose-400 font-mono font-bold">{(lipSyncerWeight * 100).toFixed(0)}%</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={lipSyncerWeight}
                    onChange={(e) => setLipSyncerWeight?.(parseFloat(e.target.value))}
                    className="w-full accent-rose-500 h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer"
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {/* CARD 4: FACE ENHANCER */}
        {selectedProcessors.includes("face_enhancer") && (
          <div className="bg-zinc-950/60 border border-emerald-500/30 rounded-xl overflow-hidden shadow-lg shadow-emerald-950/20 transition-all">
            <div
              onClick={() => toggleExpand("face_enhancer")}
              className="px-3.5 py-2.5 bg-zinc-900/70 hover:bg-zinc-900 cursor-pointer flex items-center justify-between border-b border-zinc-800"
            >
              <div className="flex items-center gap-2">
                <Sparkles size={13} className="text-emerald-400" />
                <span className="text-xs font-black text-white tracking-wider">
                  {getProcessorTitle("face_enhancer")}
                </span>
              </div>
              <div className="flex items-center gap-2 text-zinc-400">
                <span className="text-[10px] font-mono text-zinc-500">{faceEnhancerModel}</span>
                {expandedCards["face_enhancer"] ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </div>
            </div>

            {expandedCards["face_enhancer"] && (
              <div className="p-3.5 space-y-3 animate-fade-in">
                <div>
                  <label className="text-[10px] font-bold text-zinc-400 block mb-1">Modelo de Restauração</label>
                  <div className="relative">
                    <select
                      value={faceEnhancerModel}
                      onChange={(e) => setFaceEnhancerModel(e.target.value)}
                      className="w-full bg-zinc-900 border border-zinc-800 text-xs px-2.5 py-1.5 rounded-lg appearance-none font-bold text-zinc-200 outline-none cursor-pointer focus:border-emerald-500"
                    >
                      <option value="codeformer">codeformer</option>
                      <option value="gfpgan_1.4">gfpgan_1.4</option>
                      <option value="gpen_bfr_512">gpen_bfr_512</option>
                      <option value="restoreformer_plus_plus">restoreformer_plus_plus</option>
                    </select>
                    <ChevronDown size={12} className="absolute right-2.5 top-2.5 text-zinc-500 pointer-events-none" />
                  </div>
                </div>

                <div className="space-y-1">
                  <div className="flex justify-between text-xs font-bold">
                    <span className="text-zinc-300">Blend (Mesclagem com Original)</span>
                    <span className="text-emerald-400 font-mono font-bold">{faceEnhancerBlend}%</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    step="1"
                    value={faceEnhancerBlend}
                    onChange={(e) => setFaceEnhancerBlend(parseInt(e.target.value))}
                    className="w-full accent-emerald-500 h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer"
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {/* CARD 5: FRAME ENHANCER */}
        {selectedProcessors.includes("frame_enhancer") && (
          <div className="bg-zinc-950/60 border border-cyan-500/30 rounded-xl overflow-hidden shadow-lg shadow-cyan-950/20 transition-all">
            <div
              onClick={() => toggleExpand("frame_enhancer")}
              className="px-3.5 py-2.5 bg-zinc-900/70 hover:bg-zinc-900 cursor-pointer flex items-center justify-between border-b border-zinc-800"
            >
              <div className="flex items-center gap-2">
                <Layers size={13} className="text-cyan-400" />
                <span className="text-xs font-black text-white tracking-wider">
                  {getProcessorTitle("frame_enhancer")}
                </span>
              </div>
              <div className="flex items-center gap-2 text-zinc-400">
                <span className="text-[10px] font-mono text-zinc-500">{frameEnhancerModel}</span>
                {expandedCards["frame_enhancer"] ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </div>
            </div>

            {expandedCards["frame_enhancer"] && (
              <div className="p-3.5 space-y-3 animate-fade-in">
                <div>
                  <label className="text-[10px] font-bold text-zinc-400 block mb-1">Modelo de Super Resolução</label>
                  <div className="relative">
                    <select
                      value={frameEnhancerModel}
                      onChange={(e) => setFrameEnhancerModel(e.target.value)}
                      className="w-full bg-zinc-900 border border-zinc-800 text-xs px-2.5 py-1.5 rounded-lg appearance-none font-bold text-zinc-200 outline-none cursor-pointer focus:border-cyan-500"
                    >
                      <option value="real_esrgan_x4plus">real_esrgan_x4plus</option>
                      <option value="real_esrgan_x2plus">real_esrgan_x2plus</option>
                      <option value="span_kendata_x4">span_kendata_x4</option>
                      <option value="nomos8k_sc_x4">nomos8k_sc_x4</option>
                    </select>
                    <ChevronDown size={12} className="absolute right-2.5 top-2.5 text-zinc-500 pointer-events-none" />
                  </div>
                </div>

                <div className="space-y-1">
                  <div className="flex justify-between text-xs font-bold">
                    <span className="text-zinc-300">Blend</span>
                    <span className="text-cyan-400 font-mono font-bold">{frameEnhancerBlend}%</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    step="1"
                    value={frameEnhancerBlend}
                    onChange={(e) => setFrameEnhancerBlend(parseInt(e.target.value))}
                    className="w-full accent-cyan-500 h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer"
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {/* CARD 6: FRAME COLORIZER (Colorização de Vídeos Antigos) */}
        {selectedProcessors.includes("frame_colorizer") && (
          <div className="bg-zinc-950/60 border border-amber-500/30 rounded-xl overflow-hidden shadow-lg shadow-amber-950/20 transition-all">
            <div
              onClick={() => toggleExpand("frame_colorizer")}
              className="px-3.5 py-2.5 bg-zinc-900/70 hover:bg-zinc-900 cursor-pointer flex items-center justify-between border-b border-zinc-800"
            >
              <div className="flex items-center gap-2">
                <Palette size={13} className="text-amber-400" />
                <span className="text-xs font-black text-white tracking-wider">
                  {getProcessorTitle("frame_colorizer")}
                </span>
              </div>
              <div className="flex items-center gap-2 text-zinc-400">
                <span className="text-[10px] font-mono text-zinc-500">{frameColorizerModel}</span>
                {expandedCards["frame_colorizer"] ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </div>
            </div>

            {expandedCards["frame_colorizer"] && (
              <div className="p-3.5 space-y-3 animate-fade-in">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-[10px] font-bold text-zinc-400 block mb-1">Modelo</label>
                    <div className="relative">
                      <select
                        value={frameColorizerModel}
                        onChange={(e) => setFrameColorizerModel?.(e.target.value)}
                        className="w-full bg-zinc-900 border border-zinc-800 text-xs px-2.5 py-1.5 rounded-lg appearance-none font-bold text-zinc-200 outline-none cursor-pointer focus:border-amber-500"
                      >
                        <option value="ddcolor">DDColor (Realista)</option>
                        <option value="deoldify">DeOldify (Padrão)</option>
                        <option value="deoldify_artistic">DeOldify Artistic</option>
                      </select>
                      <ChevronDown size={12} className="absolute right-2.5 top-2.5 text-zinc-500 pointer-events-none" />
                    </div>
                  </div>

                  <div>
                    <label className="text-[10px] font-bold text-zinc-400 block mb-1">Resolução</label>
                    <div className="relative">
                      <select
                        value={frameColorizerSize}
                        onChange={(e) => setFrameColorizerSize?.(e.target.value)}
                        className="w-full bg-zinc-900 border border-zinc-800 text-xs px-2.5 py-1.5 rounded-lg appearance-none font-bold text-zinc-200 outline-none cursor-pointer focus:border-amber-500"
                      >
                        <option value="512x512">512x512</option>
                        <option value="384x384">384x384</option>
                        <option value="256x256">256x256</option>
                        <option value="192x192">192x192</option>
                      </select>
                      <ChevronDown size={12} className="absolute right-2.5 top-2.5 text-zinc-500 pointer-events-none" />
                    </div>
                  </div>
                </div>

                <div className="space-y-1">
                  <div className="flex justify-between text-xs font-bold">
                    <span className="text-zinc-300">Intensidade da Cor (Blend)</span>
                    <span className="text-amber-400 font-mono font-bold">{frameColorizerBlend}%</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    step="1"
                    value={frameColorizerBlend}
                    onChange={(e) => setFrameColorizerBlend?.(parseInt(e.target.value))}
                    className="w-full accent-amber-500 h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer"
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {/* CARD 7: BACKGROUND REMOVER (Remoção e Fundo Verde) */}
        {selectedProcessors.includes("background_remover") && (
          <div className="bg-zinc-950/60 border border-teal-500/30 rounded-xl overflow-hidden shadow-lg shadow-teal-950/20 transition-all">
            <div
              onClick={() => toggleExpand("background_remover")}
              className="px-3.5 py-2.5 bg-zinc-900/70 hover:bg-zinc-900 cursor-pointer flex items-center justify-between border-b border-zinc-800"
            >
              <div className="flex items-center gap-2">
                <Scissors size={13} className="text-teal-400" />
                <span className="text-xs font-black text-white tracking-wider">
                  {getProcessorTitle("background_remover")}
                </span>
              </div>
              <div className="flex items-center gap-2 text-zinc-400">
                <span className="text-[10px] font-mono text-zinc-500">{backgroundRemoverModel}</span>
                {expandedCards["background_remover"] ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </div>
            </div>

            {expandedCards["background_remover"] && (
              <div className="p-3.5 space-y-3 animate-fade-in">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-[10px] font-bold text-zinc-400 block mb-1">Modelo de Segmentação</label>
                    <div className="relative">
                      <select
                        value={backgroundRemoverModel}
                        onChange={(e) => setBackgroundRemoverModel?.(e.target.value)}
                        className="w-full bg-zinc-900 border border-zinc-800 text-xs px-2.5 py-1.5 rounded-lg appearance-none font-bold text-zinc-200 outline-none cursor-pointer focus:border-teal-500"
                      >
                        <option value="birefnet_general">BiRefNet General</option>
                        <option value="birefnet_portrait">BiRefNet Portrait</option>
                        <option value="rmbg_1.4">RMBG 1.4</option>
                      </select>
                      <ChevronDown size={12} className="absolute right-2.5 top-2.5 text-zinc-500 pointer-events-none" />
                    </div>
                  </div>

                  <div>
                    <label className="text-[10px] font-bold text-zinc-400 block mb-1">Fundo Substituto</label>
                    <div className="relative">
                      <select
                        value={backgroundRemoverColor}
                        onChange={(e) => setBackgroundRemoverColor?.(e.target.value)}
                        className="w-full bg-zinc-900 border border-zinc-800 text-xs px-2.5 py-1.5 rounded-lg appearance-none font-bold text-zinc-200 outline-none cursor-pointer focus:border-teal-500"
                      >
                        <option value="transparent">Transparente (PNG/Alpha)</option>
                        <option value="black">Preto (#000000)</option>
                        <option value="white">Branco (#ffffff)</option>
                        <option value="green">Chroma Key (#00ff00)</option>
                      </select>
                      <ChevronDown size={12} className="absolute right-2.5 top-2.5 text-zinc-500 pointer-events-none" />
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* CARD 8: FACE DEBUGGER (Inspeção de Landmarks e Caixas) */}
        {selectedProcessors.includes("face_debugger") && (
          <div className="bg-zinc-950/60 border border-violet-500/30 rounded-xl overflow-hidden shadow-lg shadow-violet-950/20 transition-all">
            <div
              onClick={() => toggleExpand("face_debugger")}
              className="px-3.5 py-2.5 bg-zinc-900/70 hover:bg-zinc-900 cursor-pointer flex items-center justify-between border-b border-zinc-800"
            >
              <div className="flex items-center gap-2">
                <Eye size={13} className="text-violet-400" />
                <span className="text-xs font-black text-white tracking-wider">
                  {getProcessorTitle("face_debugger")}
                </span>
              </div>
              <div className="flex items-center gap-2 text-zinc-400">
                <span className="text-[10px] font-mono text-zinc-500">{faceDebuggerItems.length} itens</span>
                {expandedCards["face_debugger"] ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </div>
            </div>

            {expandedCards["face_debugger"] && (
              <div className="p-3.5 space-y-2.5 animate-fade-in">
                <label className="text-[10px] font-bold text-zinc-400 block">Camadas de Depuração Visíveis</label>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { id: "bounding-box", label: "Bounding Box (Caixa)" },
                    { id: "face-landmark-5", label: "Landmarks 5 Pontos" },
                    { id: "face-landmark-68", label: "Landmarks 68 Pontos" },
                    { id: "face-mask", label: "Máscara Facial" },
                  ].map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => toggleDebuggerItem(item.id)}
                      className={`px-2.5 py-1.5 rounded-lg border text-left text-[10px] font-bold transition-all cursor-pointer flex items-center justify-between ${
                        faceDebuggerItems.includes(item.id)
                          ? "bg-violet-600/20 border-violet-500/50 text-violet-300"
                          : "bg-zinc-900 border-zinc-800 text-zinc-500 hover:text-zinc-300"
                      }`}
                    >
                      <span>{item.label}</span>
                      <span className={`w-1.5 h-1.5 rounded-full ${faceDebuggerItems.includes(item.id) ? "bg-violet-400" : "bg-zinc-700"}`} />
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* CARD 9: AGE MODIFIER */}
        {selectedProcessors.includes("age_modifier") && (
          <div className="bg-zinc-950/60 border border-purple-500/30 rounded-xl overflow-hidden shadow-lg shadow-purple-950/20 transition-all">
            <div
              onClick={() => toggleExpand("age_modifier")}
              className="px-3.5 py-2.5 bg-zinc-900/70 hover:bg-zinc-900 cursor-pointer flex items-center justify-between border-b border-zinc-800"
            >
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-purple-500 shadow-sm shadow-purple-500" />
                <span className="text-xs font-black text-white tracking-wider">
                  {getProcessorTitle("age_modifier")}
                </span>
              </div>
              <div className="flex items-center gap-2 text-zinc-400">
                <span className="text-[10px] font-mono text-zinc-500">{ageModifierModel}</span>
                {expandedCards["age_modifier"] ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </div>
            </div>

            {expandedCards["age_modifier"] && (
              <div className="p-3.5 space-y-3 animate-fade-in">
                <div className="space-y-1">
                  <div className="flex justify-between text-xs font-bold">
                    <span className="text-zinc-300">Modificador de Idade</span>
                    <span className="text-purple-400 font-mono font-bold">
                      {ageModifierDirection > 0 ? `+${ageModifierDirection} anos` : ageModifierDirection < 0 ? `${ageModifierDirection} anos` : "Neutro"}
                    </span>
                  </div>
                  <input
                    type="range"
                    min="-50"
                    max="50"
                    step="1"
                    value={ageModifierDirection}
                    onChange={(e) => setAgeModifierDirection(parseInt(e.target.value))}
                    className="w-full accent-purple-500 h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer"
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {/* CARD 10: FACE EDITOR */}
        {selectedProcessors.includes("face_editor") && (
          <div className="bg-zinc-950/60 border border-amber-500/30 rounded-xl overflow-hidden shadow-lg shadow-amber-950/20 transition-all">
            <div
              onClick={() => toggleExpand("face_editor")}
              className="px-3.5 py-2.5 bg-zinc-900/70 hover:bg-zinc-900 cursor-pointer flex items-center justify-between border-b border-zinc-800"
            >
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-amber-500 shadow-sm shadow-amber-500" />
                <span className="text-xs font-black text-white tracking-wider">
                  {getProcessorTitle("face_editor")}
                </span>
              </div>
              <div className="flex items-center gap-2 text-zinc-400">
                <span className="text-[10px] font-mono text-zinc-500">live_portrait</span>
                {expandedCards["face_editor"] ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </div>
            </div>

            {expandedCards["face_editor"] && (
              <div className="p-3.5 space-y-3 animate-fade-in">
                <div className="space-y-1">
                  <div className="flex justify-between text-xs font-bold">
                    <span className="text-zinc-300">Intensidade do Sorriso</span>
                    <span className="text-amber-400 font-mono font-bold">{faceEditorSmile}</span>
                  </div>
                  <input
                    type="range"
                    min="-10"
                    max="10"
                    step="1"
                    value={faceEditorSmile}
                    onChange={(e) => setFaceEditorSmile(parseInt(e.target.value))}
                    className="w-full accent-amber-500 h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer"
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {/* CARD 11: EXPRESSION RESTORER */}
        {selectedProcessors.includes("expression_restorer") && (
          <div className="bg-zinc-950/60 border border-pink-500/30 rounded-xl overflow-hidden shadow-lg shadow-pink-950/20 transition-all">
            <div
              onClick={() => toggleExpand("expression_restorer")}
              className="px-3.5 py-2.5 bg-zinc-900/70 hover:bg-zinc-900 cursor-pointer flex items-center justify-between border-b border-zinc-800"
            >
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-pink-500 shadow-sm shadow-pink-500" />
                <span className="text-xs font-black text-white tracking-wider">
                  {getProcessorTitle("expression_restorer")}
                </span>
              </div>
              <div className="flex items-center gap-2 text-zinc-400">
                <span className="text-[10px] font-mono text-zinc-500">live_portrait</span>
                {expandedCards["expression_restorer"] ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </div>
            </div>

            {expandedCards["expression_restorer"] && (
              <div className="p-3.5 space-y-3 animate-fade-in">
                <div className="space-y-1">
                  <div className="flex justify-between text-xs font-bold">
                    <span className="text-zinc-300">Restoration Factor</span>
                    <span className="text-pink-400 font-mono font-bold">{(expressionRestorerFactor * 100).toFixed(0)}%</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={expressionRestorerFactor}
                    onChange={(e) => setExpressionRestorerFactor(parseFloat(e.target.value))}
                    className="w-full accent-pink-500 h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer"
                  />
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
