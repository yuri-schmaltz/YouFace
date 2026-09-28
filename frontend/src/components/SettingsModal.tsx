import React, { useState, useEffect } from "react";
import { Cpu, Terminal, Download, RefreshCw, CheckCircle, Trash2, Layers, AlertCircle, XCircle } from "lucide-react";
import { formatApiUrl } from "../utils/api";

interface SettingsModalProps {
  apiUrl: string;
  configTempPath: string;
  setConfigTempPath: (val: string) => void;
  configJobsPath: string;
  setConfigJobsPath: (val: string) => void;
  configMemoryStrategy: string;
  setConfigMemoryStrategy: (val: string) => void;
  configThreadCount: number;
  setConfigThreadCount: (val: number) => void;
  configLogLevel: string;
  setConfigLogLevel: (val: string) => void;
  configProviders: string[];
  setConfigProviders: (val: string[]) => void;
  availableProviders: string[];
  isSavingConfig: boolean;
  onSaveConfig: (e: React.FormEvent) => void;
  onExportDiagnostic: () => void;
  showToast: (type: "success" | "error" | "info" | "warning", title: string, message?: string) => void;
}

interface ModelStatusData {
  status: "idle" | "downloading" | "completed" | "error" | "cancelled";
  scope: string;
  current_model: string;
  downloaded: number;
  total: number;
  percent: number;
  error?: string | null;
  disk?: {
    count: number;
    size_gb: number;
  };
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  apiUrl,
  configTempPath,
  setConfigTempPath,
  configJobsPath,
  setConfigJobsPath,
  configMemoryStrategy,
  setConfigMemoryStrategy,
  configThreadCount,
  setConfigThreadCount,
  configLogLevel,
  setConfigLogLevel,
  configProviders,
  setConfigProviders,
  availableProviders,
  isSavingConfig,
  onSaveConfig,
  onExportDiagnostic,
  showToast,
}) => {
  const [isCleaning, setIsCleaning] = useState(false);
  
  // Model Download States
  const [downloadScope, setDownloadScope] = useState<"full" | "lite">("full");
  const [downloadProvider, setDownloadProvider] = useState<"github" | "huggingface">("github");
  const [modelStatus, setModelStatus] = useState<ModelStatusData | null>(null);
  const [isStartingDownload, setIsStartingDownload] = useState(false);

  // Polling de status dos modelos
  const fetchModelStatus = async () => {
    try {
      const url = formatApiUrl(apiUrl, "/api/models/status");
      const res = await fetch(url);
      if (res.ok) {
        const data: ModelStatusData = await res.json();
        setModelStatus(data);
      }
    } catch {
      // silencioso se desconectado
    }
  };

  useEffect(() => {
    fetchModelStatus();
    const interval = setInterval(() => {
      fetchModelStatus();
    }, 2000);
    return () => clearInterval(interval);
  }, [apiUrl]);

  const handleStartDownload = async () => {
    setIsStartingDownload(true);
    try {
      const url = formatApiUrl(apiUrl, "/api/models/download");
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          download_scope: downloadScope,
          download_provider: downloadProvider,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        showToast("info", "Download Iniciado", `Baixando modelos (${downloadScope}) em segundo plano.`);
        fetchModelStatus();
      } else {
        showToast("error", "Falha no Download", data.message || data.detail || "Erro ao iniciar download.");
      }
    } catch {
      showToast("error", "Erro de Rede", "Não foi possível disparar o download dos modelos.");
    } finally {
      setIsStartingDownload(false);
    }
  };

  const handleCancelDownload = async () => {
    try {
      const url = formatApiUrl(apiUrl, "/api/models/cancel");
      const res = await fetch(url, { method: "POST" });
      if (res.ok) {
        showToast("warning", "Download Cancelado", "O processo de download foi interrompido.");
        fetchModelStatus();
      }
    } catch {
      showToast("error", "Erro", "Não foi possível cancelar o download.");
    }
  };

  const handleCleanupCache = async () => {
    setIsCleaning(true);
    try {
      const url = formatApiUrl(apiUrl, "/api/media/cleanup");
      const res = await fetch(url, { method: "POST" });
      const data = await res.json();
      if (res.ok) {
        showToast("success", "Cache Limpo", data.message || "Arquivos temporários removidos.");
      } else {
        showToast("error", "Erro ao Limpar", data.detail || "Falha na limpeza.");
      }
    } catch {
      showToast("error", "Erro de Rede", "Não foi possível conectar ao servidor para limpeza.");
    } finally {
      setIsCleaning(false);
    }
  };

  const isDownloading = modelStatus?.status === "downloading";

  return (
    <div className="w-full space-y-4 animate-fade-in flex-1 overflow-y-auto lg:overflow-hidden flex flex-col p-4 md:p-6 select-none custom-scrollbar">
      {/* Grid Principal de 2 Colunas Otimizado Horizontalmente */}
      <form onSubmit={onSaveConfig} className="grid grid-cols-1 lg:grid-cols-12 gap-4 flex-1 min-h-0">
        {/* COLUNA ESQUERDA (5 Colunas): Model Manager & Logs */}
        <div className="lg:col-span-5 flex flex-col gap-4">
          {/* SEÇÃO 1: BAIXAR TODOS OS MODELOS DE IA */}
          <div className="bg-zinc-950/60 border border-red-500/30 rounded-xl p-4 space-y-3.5 shadow-lg shadow-red-950/10 flex-1 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between border-b border-zinc-900 pb-2.5 mb-3">
                <div className="flex items-center gap-2">
                  <div className="w-7 h-7 rounded-lg bg-red-500/10 border border-red-500/20 flex items-center justify-center text-red-400">
                    <Layers size={15} />
                  </div>
                  <div>
                    <h3 className="text-xs font-black text-white tracking-wide">
                      Download de Modelos de IA
                    </h3>
                    <p className="text-[10.5px] text-zinc-500">
                      Operação 100% autônoma e offline.
                    </p>
                  </div>
                </div>

                {modelStatus?.disk && (
                  <div className="flex items-center gap-1.5 bg-zinc-900/80 border border-zinc-800 px-2.5 py-0.5 rounded-lg text-[11px] font-mono">
                    <span className="text-emerald-400 font-bold">{modelStatus.disk.count} mod</span>
                    <span className="text-zinc-600">•</span>
                    <span className="text-zinc-300 font-bold">{modelStatus.disk.size_gb} GB</span>
                  </div>
                )}
              </div>

              {/* Opções de Escopo e Provedor */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-[11px] text-zinc-300 font-bold">Escopo (Download Scope)</label>
                  <select
                    value={downloadScope}
                    disabled={isDownloading}
                    onChange={(e) => setDownloadScope(e.target.value as "full" | "lite")}
                    className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-2.5 py-1.5 text-[11px] font-bold text-zinc-200 outline-none focus:border-red-500 transition-colors disabled:opacity-50 cursor-pointer"
                  >
                    <option value="full">Todos (Full - 245 mod)</option>
                    <option value="lite">Essenciais (Lite - 112 mod)</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="text-[11px] text-zinc-300 font-bold">Servidor Fonte</label>
                  <select
                    value={downloadProvider}
                    disabled={isDownloading}
                    onChange={(e) => setDownloadProvider(e.target.value as "github" | "huggingface")}
                    className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-2.5 py-1.5 text-[11px] font-bold text-zinc-200 outline-none focus:border-red-500 transition-colors disabled:opacity-50 cursor-pointer"
                  >
                    <option value="github">GitHub Releases Oficial</option>
                    <option value="huggingface">HuggingFace Mirror</option>
                  </select>
                </div>
              </div>

              {/* Status do Download em Execução */}
              {isDownloading && (
                <div className="bg-zinc-900/90 border border-zinc-800 rounded-xl p-3 space-y-2 shadow-inner mt-3 animate-fade-in">
                  <div className="flex items-center justify-between text-[11px] font-mono">
                    <div className="flex items-center gap-1.5 truncate max-w-[200px]">
                      <RefreshCw size={12} className="animate-spin text-red-500 flex-shrink-0" />
                      <span className="text-zinc-300 font-bold truncate">
                        {modelStatus?.current_model || "Baixando modelo..."}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-zinc-400 font-bold flex-shrink-0">
                      <span>{modelStatus?.downloaded}/{modelStatus?.total}</span>
                      <span className="text-red-400 font-black">{modelStatus?.percent}%</span>
                    </div>
                  </div>

                  <div className="w-full h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-red-600 to-red-500 transition-all duration-300 rounded-full shadow-md shadow-red-500/50"
                      style={{ width: `${modelStatus?.percent || 0}%` }}
                    />
                  </div>

                  <div className="flex justify-end">
                    <button
                      type="button"
                      onClick={handleCancelDownload}
                      className="text-[10px] text-red-400 hover:text-red-300 font-bold flex items-center gap-1 cursor-pointer transition-colors"
                    >
                      <XCircle size={11} /> Cancelar Download
                    </button>
                  </div>
                </div>
              )}

              {modelStatus?.status === "completed" && (
                <div className="flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/20 px-3 py-2 rounded-lg text-emerald-400 text-xs font-bold mt-3 animate-fade-in">
                  <CheckCircle size={14} />
                  <span>Modelos baixados e validados no disco!</span>
                </div>
              )}

              {modelStatus?.status === "error" && (
                <div className="flex items-center gap-2 bg-red-500/10 border border-red-500/20 px-3 py-2 rounded-lg text-red-400 text-xs font-bold mt-3 animate-fade-in">
                  <AlertCircle size={14} />
                  <span className="truncate">Erro: {modelStatus?.error}</span>
                </div>
              )}
            </div>

            {/* Botão de Disparo */}
            {!isDownloading && (
              <button
                type="button"
                onClick={handleStartDownload}
                disabled={isStartingDownload}
                className="w-full bg-gradient-to-r from-red-600 to-red-700 hover:from-red-500 hover:to-red-600 text-white font-bold py-2.5 rounded-lg text-xs tracking-wider uppercase transition-all shadow-md shadow-red-600/20 flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 active:scale-[0.99]"
              >
                {isStartingDownload ? <RefreshCw size={13} className="animate-spin" /> : <Download size={13} />}
                BAIXAR TODOS OS MODELOS ({downloadScope.toUpperCase()})
              </button>
            )}
          </div>

          {/* SEÇÃO 2: LOGS, MANUTENÇÃO & DIRETÓRIOS */}
          <div className="bg-zinc-950/40 border border-zinc-900 rounded-xl p-4 space-y-3">
            <div className="flex items-center justify-between border-b border-zinc-900 pb-2">
              <h3 className="text-xs font-bold text-white flex items-center gap-2">
                <Terminal size={15} className="text-red-500" /> Logs e Manutenção
              </h3>
              <button
                type="button"
                onClick={onExportDiagnostic}
                className="bg-zinc-900 hover:bg-zinc-850 text-zinc-300 border border-zinc-800 rounded-lg px-2.5 py-1 text-[11px] font-bold transition-all flex items-center gap-1.5 cursor-pointer shadow-sm"
                title="Exportar pacote zip com diagnóstico completo de logs e hardware"
              >
                <Download size={12} className="text-zinc-400" />
                Exportar Diagnóstico (ZIP)
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-[11px] text-zinc-400 font-semibold">Caminho Temporário (Temp Path)</label>
                <input
                  type="text"
                  value={configTempPath}
                  onChange={(e) => setConfigTempPath(e.target.value)}
                  placeholder="Ex: .temp"
                  className="w-full bg-zinc-900/60 border border-zinc-800 rounded-lg px-2.5 py-1.5 text-xs text-zinc-300 outline-none focus:border-red-500 transition-colors"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[11px] text-zinc-400 font-semibold">Pasta de Tarefas (Jobs Path)</label>
                <input
                  type="text"
                  value={configJobsPath}
                  onChange={(e) => setConfigJobsPath(e.target.value)}
                  placeholder="Ex: .jobs"
                  className="w-full bg-zinc-900/60 border border-zinc-800 rounded-lg px-2.5 py-1.5 text-xs text-zinc-300 outline-none focus:border-red-500 transition-colors"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[11px] text-zinc-400 font-semibold">Nível de Log (Log Level)</label>
                <select
                  value={configLogLevel}
                  onChange={(e) => setConfigLogLevel(e.target.value)}
                  className="w-full bg-zinc-900/60 border border-zinc-800 rounded-lg px-2.5 py-1.5 text-xs text-zinc-300 outline-none focus:border-red-500 transition-colors cursor-pointer"
                >
                  <option value="error">Error</option>
                  <option value="warning">Warning</option>
                  <option value="info">Info</option>
                  <option value="debug">Debug</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-[11px] text-zinc-400 font-semibold">Limpeza de Cache</label>
                <button
                  type="button"
                  onClick={handleCleanupCache}
                  disabled={isCleaning}
                  className="w-full bg-zinc-900/80 hover:bg-zinc-800 text-zinc-300 border border-zinc-800 rounded-lg px-2.5 py-1.5 text-xs font-bold transition-all flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50"
                >
                  <Trash2 size={12} className="text-amber-500" />
                  {isCleaning ? "Limpando..." : "Limpar Recortes Efêmeros"}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* COLUNA DIREITA (7 Colunas): Desempenho & Aceleração */}
        <div className="lg:col-span-7 flex flex-col gap-4">
          <div className="flex-1 flex flex-col justify-between gap-4">
            {/* SEÇÃO 3: DESEMPENHO E ACELERAÇÃO (CUDA / TENSORRT) */}
            <div className="bg-zinc-950/40 border border-zinc-900 rounded-xl p-4 space-y-3.5 flex-1">
              <div className="flex items-center justify-between border-b border-zinc-900 pb-2.5">
                <h3 className="text-xs font-bold text-white flex items-center gap-2">
                  <Cpu size={15} className="text-red-500" /> Desempenho e Aceleração de Hardware
                </h3>
                <span className="text-[10px] text-zinc-500 font-mono">
                  {availableProviders.includes("cuda") ? "⚡ Aceleração GPU Ativa" : "Modo CPU ativo"}
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-[11px] text-zinc-400 font-semibold">Estratégia de Memória</label>
                  <select
                    value={configMemoryStrategy}
                    onChange={(e) => setConfigMemoryStrategy(e.target.value)}
                    className="w-full bg-zinc-900/60 border border-zinc-800 rounded-lg px-2.5 py-1.5 text-xs text-zinc-300 outline-none focus:border-red-500 transition-colors cursor-pointer"
                  >
                    <option value="strict">Strict (Estrita / Economia Máxima)</option>
                    <option value="moderate">Moderate (Moderada / Equilibrada)</option>
                    <option value="tolerant">Tolerant (Tolerante / Desempenho Máximo)</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <label className="text-[11px] text-zinc-400 font-semibold">Threads de Execução</label>
                    <span className="text-xs font-mono font-bold text-red-400">{configThreadCount}</span>
                  </div>
                  <input
                    type="range"
                    min="1"
                    max="32"
                    value={configThreadCount}
                    onChange={(e) => setConfigThreadCount(parseInt(e.target.value))}
                    className="w-full accent-red-600 h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer mt-2"
                  />
                </div>
              </div>

              {/* Provedores de Execução (CUDA, TensorRT, CPU) */}
              <div className="space-y-2 pt-1">
                <label className="text-[11px] text-zinc-400 font-semibold block">Provedores de Execução (Execution Providers)</label>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  {availableProviders.map((provider) => {
                    const isChecked = configProviders.includes(provider);
                    const isGpu = provider === "cuda" || provider === "tensorrt";

                    return (
                      <label
                        key={provider}
                        className={`flex items-center gap-2 p-2.5 rounded-xl border text-xs cursor-pointer select-none transition-all ${
                          isChecked
                            ? isGpu
                              ? "bg-emerald-500/10 border-emerald-500/40 text-emerald-300 font-bold shadow-sm"
                              : "bg-red-600/10 border-red-500/40 text-white font-bold"
                            : "bg-zinc-900/40 border-zinc-800 text-zinc-400 hover:text-zinc-200"
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setConfigProviders([...configProviders, provider]);
                            } else {
                              setConfigProviders(configProviders.filter((p) => p !== provider));
                            }
                          }}
                          className="accent-emerald-500 w-3.5 h-3.5 rounded flex-shrink-0"
                        />
                        <div className="flex flex-col min-w-0">
                          <div className="flex items-center gap-1.5">
                            <span className="truncate uppercase tracking-wider font-extrabold text-[11px]">{provider}</span>
                            {provider === "cuda" && (
                              <span className="text-[8.5px] px-1 py-0.2 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-bold">
                                GPU
                              </span>
                            )}
                            {provider === "tensorrt" && (
                              <span className="text-[8.5px] px-1 py-0.2 rounded bg-purple-500/20 text-purple-400 border border-purple-500/30 font-bold">
                                Tensor
                              </span>
                            )}
                          </div>
                          <span className="text-[9.5px] text-zinc-500 font-normal truncate">
                            {provider === "cuda"
                              ? "NVIDIA CUDA Core"
                              : provider === "tensorrt"
                              ? "Motor TensorRT Ultra"
                              : "Processador Central"}
                          </span>
                        </div>
                      </label>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Botão de Salvar Configurações */}
            <div className="flex justify-end pt-1">
              <button
                type="submit"
                disabled={isSavingConfig}
                className="bg-gradient-to-r from-red-600 to-red-700 hover:from-red-500 hover:to-red-600 text-white font-bold px-6 py-2.5 rounded-xl text-xs transition-all shadow-lg shadow-red-600/30 flex items-center gap-2 cursor-pointer disabled:opacity-50"
              >
                {isSavingConfig ? <RefreshCw size={13} className="animate-spin" /> : null}
                Salvar Configurações
              </button>
            </div>
          </div>
        </div>
      </form>
    </div>
  );
};
