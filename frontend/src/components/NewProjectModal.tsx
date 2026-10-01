import React, { useState } from "react";
import { Sparkles, Folder, X, ChevronDown, Check, Video, Music, Sliders, Layers } from "lucide-react";
import { Project } from "../types";

interface NewProjectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreateProject: (projectData: {
    name: string;
    description: string;
    output_format: string;
    output_video_encoder: string;
    output_video_quality: string;
    output_audio_encoder: string;
    output_audio_quality: number;
    output_audio_volume: number;
    processors: string[];
  }) => Promise<void>;
  availableProcessors: string[];
}

export const NewProjectModal: React.FC<NewProjectModalProps> = ({
  isOpen,
  onClose,
  onCreateProject,
  availableProcessors,
}) => {
  // Gera nome padrão com data e hora atual
  const getDefaultProjectName = () => {
    const now = new Date();
    const pad = (n: number) => n.toString().padStart(2, "0");
    const year = now.getFullYear();
    const month = pad(now.getMonth() + 1);
    const day = pad(now.getDate());
    const hours = pad(now.getHours());
    const minutes = pad(now.getMinutes());
    return `Projeto_${year}-${month}-${day}_${hours}${minutes}`;
  };

  const [name, setName] = useState<string>(getDefaultProjectName());
  const [description, setDescription] = useState<string>("");
  const [outputFormat, setOutputFormat] = useState<string>("MP4");
  const [outputQuality, setOutputQuality] = useState<string>("High");
  const [outputVideoEncoder, setOutputVideoEncoder] = useState<string>("libx264");
  const [outputAudioEncoder, setOutputAudioEncoder] = useState<string>("aac");
  const [outputAudioQuality, setOutputAudioQuality] = useState<number>(80);
  const [outputAudioVolume, setOutputAudioVolume] = useState<number>(100);
  const [selectedProcessors, setSelectedProcessors] = useState<string[]>(["face_swapper"]);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!isOpen) return null;

  const toggleProcessor = (proc: string) => {
    setSelectedProcessors((prev) =>
      prev.includes(proc) ? prev.filter((p) => p !== proc) : [...prev, proc]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName) {
      setErrorMessage("Por favor, informe um nome para o projeto.");
      return;
    }
    setErrorMessage(null);
    setIsSubmitting(true);
    try {
      await onCreateProject({
        name: trimmedName,
        description: description.trim(),
        output_format: outputFormat.toLowerCase(),
        output_video_encoder: outputVideoEncoder,
        output_video_quality: outputQuality,
        output_audio_encoder: outputAudioEncoder,
        output_audio_quality: outputAudioQuality,
        output_audio_volume: outputAudioVolume,
        processors: selectedProcessors.length > 0 ? selectedProcessors : ["face_swapper"],
      });
      onClose();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setErrorMessage(message || "Erro ao criar projeto.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const formatLabels: Record<string, string> = {
    face_swapper: "Face Swapper",
    deep_swapper: "Deep Swapper",
    face_enhancer: "Face Enhancer",
    frame_enhancer: "Frame Enhancer",
    lip_syncer: "Lip Syncer",
    face_editor: "Face Editor",
    age_modifier: "Age Modifier",
    expression_restorer: "Expression Restorer",
    frame_colorizer: "Frame Colorizer",
    background_remover: "Background Remover",
    face_debugger: "Face Debugger",
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 animate-fade-in select-none">
      <div className="bg-zinc-950 border border-zinc-800/90 rounded-2xl w-full max-w-2xl overflow-hidden shadow-2xl shadow-black/80 flex flex-col max-h-[90vh] animate-scale-up">
        {/* Cabeçalho do Modal */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-900 bg-zinc-900/40">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center justify-center text-red-400 shadow-inner">
              <Sparkles size={20} />
            </div>
            <div>
              <h2 className="text-base font-black text-white tracking-tight flex items-center gap-2">
                Criar Novo Projeto
              </h2>
              <p className="text-xs text-zinc-400">
                Configure os parâmetros iniciais para criar a pasta em <span className="font-mono text-zinc-300">~/Vídeos/YouFace_Projects</span>.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors cursor-pointer"
            title="Fechar"
          >
            <X size={18} />
          </button>
        </div>

        {/* Corpo do Formulário */}
        <form onSubmit={handleSubmit} className="p-6 overflow-y-auto space-y-5 flex-1 pr-4">
          {errorMessage && (
            <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-xs text-red-400 font-bold">
              {errorMessage}
            </div>
          )}

          {/* Nome e Descrição */}
          <div className="space-y-3.5">
            <div>
              <label className="text-xs font-bold text-zinc-300 block mb-1.5 flex items-center gap-1.5">
                <Folder size={13} className="text-red-500" /> Nome do Projeto *
              </label>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Ex: Comercial_Verão_2026"
                className="w-full bg-zinc-900/90 border border-zinc-800 rounded-xl px-3.5 py-2 text-xs font-bold text-white placeholder-zinc-600 outline-none focus:border-red-500 transition-colors font-mono"
              />
              <span className="text-[10px] text-zinc-500 mt-1 block">
                Uma pasta com este nome será criada no seu diretório de Vídeos para organizar origem, destino e resultados.
              </span>
            </div>

            <div>
              <label className="text-xs font-bold text-zinc-400 block mb-1.5">
                Descrição / Notas (Opcional)
              </label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Ex: Teste com sincronização labial e restauração facial..."
                className="w-full bg-zinc-900/60 border border-zinc-800 rounded-xl px-3.5 py-2 text-xs text-zinc-300 placeholder-zinc-600 outline-none focus:border-red-500 transition-colors"
              />
            </div>
          </div>

          {/* Opções de Exportação de Vídeo */}
          <div className="space-y-2.5 pt-2 border-t border-zinc-900">
            <span className="text-xs font-black text-zinc-300 uppercase tracking-wider flex items-center gap-1.5">
              <Video size={13} className="text-red-500" /> Configurações de Saída de Vídeo
            </span>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="text-[10px] font-bold text-zinc-400 block mb-1">Formato</label>
                <div className="relative">
                  <select
                    value={outputFormat}
                    onChange={(e) => setOutputFormat(e.target.value)}
                    className="w-full bg-zinc-900 border border-zinc-800 text-xs px-2.5 py-1.5 rounded-lg appearance-none font-bold text-zinc-200 outline-none cursor-pointer focus:border-red-500"
                  >
                    <option value="MP4">MP4 (Universal)</option>
                    <option value="MOV">MOV (Apple / ProRes)</option>
                    <option value="MKV">MKV (Matroska)</option>
                    <option value="WEBM">WEBM (VP9 Web)</option>
                    <option value="AVI">AVI (Interleave)</option>
                    <option value="M4V">M4V (Apple)</option>
                    <option value="MPEG">MPEG (MPEG-2)</option>
                    <option value="WMV">WMV (Windows)</option>
                    <option value="MXF">MXF (Broadcast)</option>
                  </select>
                  <ChevronDown size={12} className="absolute right-2.5 top-2.5 text-zinc-500 pointer-events-none" />
                </div>
              </div>

              <div>
                <label className="text-[10px] font-bold text-zinc-400 block mb-1">Qualidade</label>
                <div className="relative">
                  <select
                    value={outputQuality}
                    onChange={(e) => setOutputQuality(e.target.value)}
                    className="w-full bg-zinc-900 border border-zinc-800 text-xs px-2.5 py-1.5 rounded-lg appearance-none font-bold text-zinc-200 outline-none cursor-pointer focus:border-red-500"
                  >
                    <option value="High">Alta (100% - CRF 18)</option>
                    <option value="Medium">Média (80% - CRF 23)</option>
                    <option value="Low">Baixa (50% - CRF 28)</option>
                  </select>
                  <ChevronDown size={12} className="absolute right-2.5 top-2.5 text-zinc-500 pointer-events-none" />
                </div>
              </div>

              <div>
                <label className="text-[10px] font-bold text-zinc-400 block mb-1">Encoder / Codec</label>
                <div className="relative">
                  <select
                    value={outputVideoEncoder}
                    onChange={(e) => setOutputVideoEncoder(e.target.value)}
                    className="w-full bg-zinc-900 border border-zinc-800 text-xs px-2.5 py-1.5 rounded-lg appearance-none font-bold text-zinc-200 outline-none cursor-pointer focus:border-red-500"
                  >
                    <option value="libx264">H.264 (CPU Padrão)</option>
                    <option value="h264_nvenc">NVIDIA NVENC H.264</option>
                    <option value="libx265">HEVC / H.265 (CPU)</option>
                    <option value="hevc_nvenc">NVIDIA NVENC HEVC</option>
                    <option value="libvpx-vp9">VP9 (WebM)</option>
                  </select>
                  <ChevronDown size={12} className="absolute right-2.5 top-2.5 text-zinc-500 pointer-events-none" />
                </div>
              </div>
            </div>
          </div>

          {/* Opções de Exportação de Áudio */}
          <div className="space-y-2.5 pt-2 border-t border-zinc-900">
            <span className="text-xs font-black text-zinc-300 uppercase tracking-wider flex items-center gap-1.5">
              <Music size={13} className="text-amber-400" /> Configurações de Saída de Áudio
            </span>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[10px] font-bold text-zinc-400 block mb-1">Codec de Áudio</label>
                <div className="relative">
                  <select
                    value={outputAudioEncoder}
                    onChange={(e) => setOutputAudioEncoder(e.target.value)}
                    className="w-full bg-zinc-900 border border-zinc-800 text-xs px-2.5 py-1.5 rounded-lg appearance-none font-bold text-zinc-200 outline-none cursor-pointer focus:border-amber-500"
                  >
                    <option value="aac">AAC (Padrão)</option>
                    <option value="libmp3lame">MP3 (LAME)</option>
                    <option value="libopus">Opus (HQ)</option>
                    <option value="flac">FLAC (Lossless)</option>
                    <option value="pcm_s16le">WAV (PCM 16-bit)</option>
                    <option value="none">Mudo (Sem Áudio)</option>
                  </select>
                  <ChevronDown size={12} className="absolute right-2.5 top-2.5 text-zinc-500 pointer-events-none" />
                </div>
              </div>

              <div>
                <div className="flex justify-between items-center mb-1">
                  <label className="text-[10px] font-bold text-zinc-400">Volume Inicial</label>
                  <span className="text-[10px] font-mono text-amber-400 font-bold">{outputAudioVolume}%</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="200"
                  step="5"
                  value={outputAudioVolume}
                  onChange={(e) => setOutputAudioVolume(parseInt(e.target.value))}
                  className="w-full accent-amber-500 h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer mt-1.5"
                />
              </div>
            </div>
          </div>

          {/* Processadores Iniciais Habilitados */}
          <div className="space-y-2.5 pt-2 border-t border-zinc-900">
            <span className="text-xs font-black text-zinc-300 uppercase tracking-wider flex items-center gap-1.5">
              <Layers size={13} className="text-red-500" /> Processadores Habilitados Inicialmente ({selectedProcessors.length})
            </span>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {availableProcessors.map((proc) => {
                const isSelected = selectedProcessors.includes(proc);
                return (
                  <button
                    key={proc}
                    type="button"
                    onClick={() => toggleProcessor(proc)}
                    className={`flex items-center gap-2 p-2 rounded-xl border text-xs font-bold transition-all text-left cursor-pointer ${
                      isSelected
                        ? "bg-red-600/15 border-red-500/50 text-white shadow-sm"
                        : "bg-zinc-900/50 border-zinc-800/80 text-zinc-400 hover:text-zinc-200"
                    }`}
                  >
                    <div
                      className={`w-3.5 h-3.5 rounded border flex items-center justify-center flex-shrink-0 ${
                        isSelected ? "bg-red-600 border-red-500 text-white" : "border-zinc-700"
                      }`}
                    >
                      {isSelected && <Check size={10} strokeWidth={3} />}
                    </div>
                    <span className="truncate">{formatLabels[proc] || proc}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Rodapé com Ações */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-zinc-900">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-xs font-bold text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900 transition-all cursor-pointer"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-5 py-2.5 rounded-xl text-xs font-bold bg-gradient-to-r from-red-600 to-red-700 hover:from-red-500 hover:to-red-600 text-white shadow-lg shadow-red-600/30 transition-all flex items-center gap-2 cursor-pointer disabled:opacity-50"
            >
              {isSubmitting ? (
                <span>Criando...</span>
              ) : (
                <>
                  <Sparkles size={14} />
                  <span>Criar Projeto e Ir para o Estúdio</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
