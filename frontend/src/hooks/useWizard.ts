import { useState, useCallback } from "react";
import type { VideoDiagnosticReport } from "../types";

/**
 * Estado do assistente de diagnóstico de vídeo (wizard).
 *
 * Extraído de `page.tsx` (linhas 284-286 originais) como passo 3 da
 * decomposição P1-1. Encapsula o ciclo de vida do `VideoDiagnosticWizard`:
 *  - `isOpen` / `isDiagnosing` controlam visibilidade
 *  - `report` armazena o resultado da análise
 *  - `open` / `close` / `setReport` / `setLoading` para manipulação direta
 *
 * Mantido simples porque a lógica de chamada ao backend (`POST
 * /api/video/diagnose`) já vive no `VideoDiagnosticWizard.tsx`. Aqui só
 * gerenciamos estado.
 */
export interface UseWizardReturn {
  isOpen: boolean;
  isDiagnosing: boolean;
  report: VideoDiagnosticReport | null;
  setIsOpen: (open: boolean) => void;
  setLoading: (loading: boolean) => void;
  setReport: (report: VideoDiagnosticReport | null) => void;
  reset: () => void;
}

export function useWizard(): UseWizardReturn {
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [isDiagnosing, setIsDiagnosing] = useState<boolean>(false);
  const [report, setReport] = useState<VideoDiagnosticReport | null>(null);

  const setLoading = useCallback((loading: boolean) => setIsDiagnosing(loading), []);
  const setIsOpenCb = useCallback((v: boolean) => setIsOpen(v), []);
  const reset = useCallback(() => {
    setIsOpen(false);
    setIsDiagnosing(false);
    setReport(null);
  }, []);

  return { isOpen, isDiagnosing, report, setIsOpen: setIsOpenCb, setLoading, setReport, reset };
}
