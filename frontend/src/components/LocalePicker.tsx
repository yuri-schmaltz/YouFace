"use client";

import { useLocale, SUPPORTED_LOCALES } from "../i18n";

/**
 * Dropdown to switch the active UI language.
 *
 * Renders a native <select> for simplicity (no external UI lib needed).
 * Reads/writes the choice to localStorage via useLocale().
 */
export function LocalePicker() {
  const { locale, setLocale, t } = useLocale();
  return (
    <label className="flex items-center gap-2 text-xs text-zinc-400">
      <span aria-hidden>🌐</span>
      <select
        value={locale}
        onChange={(e) => setLocale(e.target.value as never)}
        className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-xs"
        aria-label={t("nav.language")}
        data-testid="locale-picker"
      >
        {SUPPORTED_LOCALES.map((opt) => (
          <option key={opt.code} value={opt.code}>
            {opt.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export default LocalePicker;
