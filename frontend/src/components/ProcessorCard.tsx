import React from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

/**
 * Reusable accordion wrapper for processor configuration cards.
 * Used inside ProcessorSettings to reduce duplication across the 11 cards.
 *
 * - Title bar: clickable, toggles expanded state via parent (`onToggle`)
 * - Indicator dot: red when active, expandable via `isExpanded`
 * - Subtitle: optional model name or status text shown on the right
 */
export interface ProcessorCardProps {
  procKey: string;
  title: string;
  isExpanded: boolean;
  onToggle: (procKey: string) => void;
  subtitle?: string;
  children: React.ReactNode;
}

export const ProcessorCard: React.FC<ProcessorCardProps> = ({
  procKey,
  title,
  isExpanded,
  onToggle,
  subtitle,
  children,
}) => {
  return (
    <div className="bg-zinc-950/60 border border-red-500/30 rounded-xl overflow-hidden shadow-lg shadow-red-950/20 transition-all">
      <div
        onClick={() => onToggle(procKey)}
        className="px-3.5 py-2.5 bg-zinc-900/70 hover:bg-zinc-900 cursor-pointer flex items-center justify-between border-b border-zinc-800"
      >
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse shadow-sm shadow-red-500" />
          <span className="text-xs font-black text-white tracking-wider">{title}</span>
        </div>
        <div className="flex items-center gap-2 text-zinc-400">
          {subtitle && <span className="text-[10px] font-mono text-zinc-500">{subtitle}</span>}
          {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </div>
      </div>
      {isExpanded && (
        <div className="p-3.5 space-y-3 animate-fade-in">{children}</div>
      )}
    </div>
  );
};
