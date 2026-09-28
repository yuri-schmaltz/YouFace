import React from "react";
import { Wifi, WifiOff, Loader2 } from "lucide-react";
import type { ConnectionMode } from "../hooks/useJobs";

interface ConnectionModeBadgeProps {
  mode: ConnectionMode;
  className?: string;
}

/**
 * Badge visual para o estado da conexão de jobs (SSE vs polling).
 *
 * Mostra 4 estados distintos:
 *  - connecting (cinza, Loader2 girando): ainda tentando abrir SSE
 *  - sse (verde, Wifi): EventSource ativo, updates em tempo real
 *  - polling (amarelo, Wifi): fallback polling ativo (2.5s)
 *  - offline (vermelho, WifiOff): nenhuma conexão estabelecida
 *
 * Tooltip explica o estado para o usuário.
 */
export const ConnectionModeBadge: React.FC<ConnectionModeBadgeProps> = ({
  mode,
  className = "",
}) => {
  const config: Record<ConnectionMode, {
    label: string;
    color: string;
    borderColor: string;
    bgColor: string;
    icon: React.ReactNode;
    title: string;
  }> = {
    connecting: {
      label: "Conectando…",
      color: "text-zinc-300",
      borderColor: "border-zinc-700",
      bgColor: "bg-zinc-800/60",
      icon: <Loader2 className="w-3 h-3 animate-spin" />,
      title: "Estabelecendo conexão SSE com o backend (stream /api/jobs/stream)",
    },
    sse: {
      label: "SSE",
      color: "text-emerald-300",
      borderColor: "border-emerald-700/60",
      bgColor: "bg-emerald-900/30",
      icon: <Wifi className="w-3 h-3" />,
      title: "Conectado via Server-Sent Events — updates em tempo real",
    },
    polling: {
      label: "Polling",
      color: "text-amber-300",
      borderColor: "border-amber-700/60",
      bgColor: "bg-amber-900/30",
      icon: <Wifi className="w-3 h-3" />,
      title: "Conectado via polling (2.5s) — fallback ativado por falha no SSE",
    },
    offline: {
      label: "Offline",
      color: "text-red-300",
      borderColor: "border-red-700/60",
      bgColor: "bg-red-900/30",
      icon: <WifiOff className="w-3 h-3" />,
      title: "Sem conexão com o backend — verifique se o servidor está rodando",
    },
  };
  const c = config[mode];

  return (
    <div
      className={`flex items-center gap-1.5 px-2 py-0.5 rounded-md border font-mono text-[11px] font-bold ${c.bgColor} ${c.borderColor} ${c.color} ${className}`}
      title={c.title}
    >
      {c.icon}
      <span>Jobs: {c.label}</span>
    </div>
  );
};
