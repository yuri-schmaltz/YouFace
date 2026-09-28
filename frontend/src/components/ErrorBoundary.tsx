"use client";

import React from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

interface ErrorBoundaryProps {
  children: React.ReactNode;
  /** Optional fallback UI; defaults to a built-in full-page error. */
  fallback?: (error: Error, reset: () => void) => React.ReactNode;
  /** Optional callback for logging (e.g., to Sentry, console.error, etc.) */
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

/**
 * React Error Boundary. Renders a fallback UI when a child component throws
 * during render, preventing the whole cockpit from crashing.
 *
 * Use at the root (around the entire app) and optionally around subtrees
 * that have higher failure risk (e.g., video diagnostic wizard, job
 * processor settings).
 *
 * Limitations (per React):
 *  - Does NOT catch errors in event handlers, async code, or SSR
 *  - Does NOT catch errors in the boundary itself
 */
export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    // Log to console (production should integrate with Sentry/Datadog here)
    console.error("[ErrorBoundary] Caught error:", error, errorInfo);
    this.props.onError?.(error, errorInfo);
  }

  reset = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): React.ReactNode {
    if (this.state.hasError && this.state.error) {
      if (this.props.fallback) {
        return this.props.fallback(this.state.error, this.reset);
      }
      return <DefaultErrorFallback error={this.state.error} onReset={this.reset} />;
    }
    return this.props.children;
  }
}

interface DefaultErrorFallbackProps {
  error: Error;
  onReset: () => void;
}

function DefaultErrorFallback({ error, onReset }: DefaultErrorFallbackProps) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-950 p-4">
      <div className="max-w-lg w-full bg-zinc-900 border border-red-900/60 rounded-2xl p-6 space-y-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-red-900/30 rounded-lg">
            <AlertTriangle className="w-6 h-6 text-red-400" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-zinc-100">Algo deu errado</h1>
            <p className="text-xs text-zinc-500">
              O cockpit encontrou um erro inesperado. Você pode tentar recarregar.
            </p>
          </div>
        </div>

        <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-3">
          <p className="text-[11px] font-mono text-red-300 break-all">
            {error.name}: {error.message}
          </p>
          {error.stack && (
            <details className="mt-2">
              <summary className="text-[10px] text-zinc-500 cursor-pointer hover:text-zinc-300">
                Stack trace
              </summary>
              <pre className="text-[10px] font-mono text-zinc-600 mt-2 overflow-auto max-h-48">
                {error.stack}
              </pre>
            </details>
          )}
        </div>

        <div className="flex gap-2">
          <button
            onClick={onReset}
            className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-bold rounded-lg transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Tentar novamente
          </button>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-sm font-bold rounded-lg transition-colors"
          >
            Recarregar página
          </button>
        </div>
      </div>
    </div>
  );
}
