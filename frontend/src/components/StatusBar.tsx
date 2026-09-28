import React from "react";
import { Cpu, RefreshCw } from "lucide-react";
import { HardwareTelemetry } from "../types";
import type { ConnectionMode } from "../hooks/useJobs";
import { ConnectionModeBadge } from "./ConnectionModeBadge";

interface StatusBarProps {
  telemetry?: HardwareTelemetry | null;
  hardwareInfo?: string;
  isBackendConnected: boolean;
  onRefreshHardware?: () => void;
  connectionMode?: ConnectionMode;
}

export const StatusBar: React.FC<StatusBarProps> = ({
  telemetry,
  hardwareInfo,
  isBackendConnected,
  onRefreshHardware,
  connectionMode,
}) => {
  return (
    <footer className="h-8 border-t border-zinc-900 bg-zinc-950/95 backdrop-blur-md px-4 flex items-center justify-between flex-shrink-0 z-30 font-mono select-none">
      {/* Esquerda: Status da Conexão com o Motor Backend */}
      <div className="flex items-center gap-2 text-xs">
        <div
          className="flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-zinc-900/80 border border-zinc-800/80 cursor-default"
          title="Status da conexão de rede HTTP/SSE com a API FastAPI do FaceFusion no backend (porta 8000)"
        >
          <span className="flex h-2 w-2 relative">
            <span
              className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                isBackendConnected ? "bg-emerald-400" : "bg-red-400"
              }`}
            />
            <span
              className={`relative inline-flex rounded-full h-2 w-2 ${
                isBackendConnected ? "bg-emerald-500" : "bg-red-500"
              }`}
            />
          </span>
          <span className="font-bold text-[11px] text-zinc-300">
            Engine: {isBackendConnected ? "Online" : "Offline"}
          </span>
        </div>

        <span className="text-zinc-700">|</span>

        {connectionMode && <ConnectionModeBadge mode={connectionMode} />}

        <span className="text-zinc-700">|</span>

        <span className="text-[11px] text-zinc-500 hidden sm:inline">
          FaceFusion Core v3.8.2
        </span>
      </div>

      {/* Direita: Telemetria com Largura Fixa Rigorosa (Zero Jitter / Sem Tremulação) */}
      <div className="flex items-center">
        {telemetry ? (
          <div className="w-[550px] flex items-center justify-between bg-zinc-900/80 border border-zinc-800/80 px-2.5 py-0.5 rounded-md text-[11px] tabular-nums">
            {/* CPU - largura fixa */}
            <div
              className="w-[74px] flex items-center justify-start gap-1 text-zinc-300 overflow-hidden"
              title={`CPU (${telemetry.cpu.cores || 0} threads lógicas): ${telemetry.cpu.usage_percent}% em uso`}
            >
              <span className="text-[10px] font-bold text-zinc-500">CPU</span>
              <span className={`font-bold tabular-nums ${telemetry.cpu.usage_percent > 80 ? "text-red-400" : "text-zinc-200"}`}>
                {Number(telemetry.cpu.usage_percent).toFixed(1)}%
              </span>
            </div>

            <span className="text-zinc-700 select-none">|</span>

            {/* RAM - largura fixa */}
            <div
              className="w-[128px] flex items-center justify-start gap-1 text-zinc-300 overflow-hidden"
              title={`Memória RAM: ${telemetry.ram.used_gb} GB usados de ${telemetry.ram.total_gb} GB (${telemetry.ram.usage_percent}%)`}
            >
              <span className="text-[10px] font-bold text-zinc-500">RAM</span>
              <span className={`font-bold tabular-nums ${telemetry.ram.usage_percent > 85 ? "text-amber-400" : "text-zinc-200"}`}>
                {Number(telemetry.ram.used_gb).toFixed(1)}G{" "}
                <span className="text-zinc-500 font-normal">
                  ({Number(telemetry.ram.usage_percent).toFixed(1)}%)
                </span>
              </span>
            </div>

            <span className="text-zinc-700 select-none">|</span>

            {/* GPU - largura fixa */}
            <div
              className="w-[126px] flex items-center justify-start gap-1.5 text-zinc-300 overflow-hidden"
              title={`${telemetry.gpu.name}: ${telemetry.gpu.usage_percent ?? 0}% de processamento gráfico ativo`}
            >
              <Cpu size={12} className="text-red-500 flex-shrink-0" />
              <span className="text-[10px] font-bold text-zinc-500">GPU</span>
              <span className="font-bold tabular-nums text-zinc-200">
                {telemetry.gpu.usage_percent !== null && telemetry.gpu.usage_percent !== undefined
                  ? `${telemetry.gpu.usage_percent}%`
                  : "0%"}
              </span>
              {telemetry.gpu.temperature_c !== null && telemetry.gpu.temperature_c !== undefined && (
                <span className="text-amber-400 font-bold text-[10px] px-1 py-0.2 bg-amber-500/10 rounded tabular-nums">
                  {telemetry.gpu.temperature_c}°C
                </span>
              )}
            </div>

            <span className="text-zinc-700 select-none">|</span>

            {/* VRAM - largura fixa */}
            <div
              className="w-[138px] flex items-center justify-start gap-1 text-zinc-300 overflow-hidden"
              title={`Memória de Vídeo Dedicada (VRAM): ${telemetry.gpu.vram_used_gb} GB usados de ${telemetry.gpu.vram_total_gb} GB (${telemetry.gpu.vram_usage_percent}%)`}
            >
              <span className="text-[10px] font-bold text-zinc-500">VRAM</span>
              <span className={`font-bold tabular-nums ${telemetry.gpu.vram_usage_percent > 85 ? "text-red-400" : "text-emerald-400"}`}>
                {Number(telemetry.gpu.vram_used_gb).toFixed(1)}G
              </span>
              <span className="text-zinc-500 font-normal text-[10px] tabular-nums">
                /{Number(telemetry.gpu.vram_total_gb).toFixed(0)}G ({Number(telemetry.gpu.vram_usage_percent).toFixed(0)}%)
              </span>
            </div>

            {onRefreshHardware && (
              <button
                onClick={onRefreshHardware}
                className="text-zinc-500 hover:text-zinc-300 transition-colors ml-1 cursor-pointer flex-shrink-0"
                title="Atualizar telemetria manualmente"
              >
                <RefreshCw size={11} />
              </button>
            )}
          </div>
        ) : (
          <div className="w-[550px] flex items-center gap-2 px-2.5 py-0.5 rounded-md bg-zinc-900/70 border border-zinc-800 text-[11px] text-zinc-400">
            <Cpu size={12} className="text-red-500 flex-shrink-0" />
            <span className="truncate">{hardwareInfo || "Buscando telemetria..."}</span>
          </div>
        )}
      </div>
    </footer>
  );
};
