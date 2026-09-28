import { useState, useEffect, useCallback } from "react";
import { formatApiUrl } from "../utils/api";

/**
 * Estado das configurações do sistema (paths, memory, threads, log, providers).
 *
 * Extraído de `page.tsx` (linhas 296-302 originais) como passo 2 da
 * decomposição P1-1. Encapsula:
 *  - 6 campos de configuração espelhados de `GET /api/config`
 *  - flag de "salvando" para UX
 *  - fetch inicial automático quando `apiUrl` muda
 *  - save action para `POST /api/config`
 *
 * Os setters locais (`setConfigTempPath` etc) foram preservados como wrappers
 * finos em `page.tsx` para zero call-site churn.
 */
export interface ConfigState {
  temp_path: string;
  jobs_path: string;
  video_memory_strategy: string;
  execution_thread_count: number;
  log_level: string;
  execution_providers: string[];
  is_saving: boolean;
  is_loaded: boolean;
}

const DEFAULTS: ConfigState = {
  temp_path: ".temp",
  jobs_path: ".jobs",
  video_memory_strategy: "balanced",
  execution_thread_count: 4,
  log_level: "info",
  execution_providers: [],
  is_saving: false,
  is_loaded: false,
};

export interface UseConfigReturn {
  config: ConfigState;
  set: <K extends keyof ConfigState>(key: K, value: ConfigState[K]) => void;
  patch: (partial: Partial<ConfigState>) => void;
  save: () => Promise<boolean>;
  refresh: () => Promise<void>;
}

export function useConfig(apiUrl: string): UseConfigReturn {
  const [config, setConfig] = useState<ConfigState>(DEFAULTS);

  const set = useCallback(
    <K extends keyof ConfigState>(key: K, value: ConfigState[K]) => {
      setConfig(prev => ({ ...prev, [key]: value }));
    },
    []
  );

  const patch = useCallback((partial: Partial<ConfigState>) => {
    setConfig(prev => ({ ...prev, ...partial }));
  }, []);

  const refresh = useCallback(async () => {
    if (!apiUrl && apiUrl !== "") return;
    try {
      const url = formatApiUrl(apiUrl, "/api/config");
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setConfig(prev => ({
          ...prev,
          temp_path: data.temp_path ?? prev.temp_path,
          jobs_path: data.jobs_path ?? prev.jobs_path,
          video_memory_strategy: data.video_memory_strategy ?? prev.video_memory_strategy,
          execution_thread_count: data.execution_thread_count ?? prev.execution_thread_count,
          log_level: data.log_level ?? prev.log_level,
          execution_providers: data.execution_providers ?? prev.execution_providers,
          is_loaded: true,
        }));
      }
    } catch {
      // network error: keep defaults, will retry on next refresh
    }
  }, [apiUrl]);

  const save = useCallback(async (): Promise<boolean> => {
    if (!apiUrl && apiUrl !== "") return false;
    setConfig(prev => ({ ...prev, is_saving: true }));
    try {
      const url = formatApiUrl(apiUrl, "/api/config");
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          temp_path: config.temp_path,
          jobs_path: config.jobs_path,
          video_memory_strategy: config.video_memory_strategy,
          execution_thread_count: config.execution_thread_count,
          log_level: config.log_level,
          execution_providers: config.execution_providers,
        }),
      });
      return res.ok;
    } catch {
      return false;
    } finally {
      setConfig(prev => ({ ...prev, is_saving: false }));
    }
  }, [apiUrl, config.temp_path, config.jobs_path, config.video_memory_strategy, config.execution_thread_count, config.log_level, config.execution_providers]);

  // Auto-fetch on mount and when apiUrl changes
  useEffect(() => {
    refresh();
  }, [refresh]);

  return { config, set, patch, save, refresh };
}
