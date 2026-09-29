/**
 * Lightweight i18n for the YouFace cockpit (R16 of gauntlet).
 *
 * Why a hand-rolled mini-i18n instead of next-intl / react-i18next:
 *   - Zero runtime dependencies (no extra npm package).
 *   - No need for plural/gender/ICU rules yet — just key→string.
 *   - Translations are co-located with the consuming code.
 *   - Locale is persisted in localStorage so users don't have to re-pick.
 *
 * Adding a new language:
 *   1. Create `frontend/src/i18n/locales/<code>.ts` exporting a dict.
 *   2. Add the code to the `SUPPORTED_LOCALES` list below.
 *   3. (No code changes needed elsewhere — the picker just renders more options.)
 *
 * Adding a new string:
 *   1. Add the key to `en.ts`.
 *   2. Add the translation to all other locale files.
 *   3. Use `t("your.key")` in any component.
 */

import { useEffect, useState, useCallback } from "react";
import en from "./locales/en";
import pt from "./locales/pt-BR";

export type LocaleCode = "en" | "pt-BR";

export const SUPPORTED_LOCALES: ReadonlyArray<{
  code: LocaleCode;
  label: string;
}> = [
  { code: "en", label: "English" },
  { code: "pt-BR", label: "Português (Brasil)" },
] as const;

export const DEFAULT_LOCALE: LocaleCode = "en";

const TRANSLATIONS: Record<LocaleCode, Record<string, string>> = {
  "en": en,
  "pt-BR": pt,
};

const STORAGE_KEY = "youface.locale";

function detectInitialLocale(): LocaleCode {
  if (typeof window === "undefined") {
    return DEFAULT_LOCALE;
  }
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored && stored in TRANSLATIONS) {
      return stored as LocaleCode;
    }
  } catch {
    /* localStorage might be unavailable in private mode */
  }
  // Fall back to navigator language if it matches one of ours.
  const navLang = typeof navigator !== "undefined" ? navigator.language : "";
  if (navLang.startsWith("pt")) {
    return "pt-BR";
  }
  return DEFAULT_LOCALE;
}

/**
 * Replace `{name}` placeholders with values from the supplied dict.
 * Example: `t("hello.world", { name: "Yuri" })` with `en["hello.world"] = "Hi {name}"`
 * returns `"Hi Yuri"`.
 */
function interpolate(template: string, values?: Record<string, string | number>): string {
  if (!values) return template;
  return template.replace(/\{(\w+)\}/g, (_, key) => {
    return key in values ? String(values[key]) : `{${key}}`;
  });
}

/**
 * Hook returning `{ locale, setLocale, t }`.
 *
 * `t(key, values?)` returns the translated string. If the key is missing in
 * the active locale, falls back to English; if still missing, returns the
 * key itself (so missing translations are visible during development).
 */
export function useLocale() {
  const [locale, setLocaleState] = useState<LocaleCode>(DEFAULT_LOCALE);

  useEffect(() => {
    setLocaleState(detectInitialLocale());
  }, []);

  const setLocale = useCallback((next: LocaleCode) => {
    setLocaleState(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* ignore */
    }
  }, []);

  const t = useCallback(
    (key: string, values?: Record<string, string | number>): string => {
      const active = TRANSLATIONS[locale] || {};
      const fallback = TRANSLATIONS[DEFAULT_LOCALE] || {};
      const raw = active[key] ?? fallback[key] ?? key;
      return interpolate(raw, values);
    },
    [locale],
  );

  return { locale, setLocale, t, supported: SUPPORTED_LOCALES };
}

/**
 * Stand-alone translator for non-component contexts (e.g. error toasts
 * outside React tree). Reads the current locale from localStorage each
 * call so it stays in sync without React state.
 */
export function t(
  key: string,
  values?: Record<string, string | number>,
): string {
  const code = detectInitialLocale();
  const active = TRANSLATIONS[code] || {};
  const fallback = TRANSLATIONS[DEFAULT_LOCALE] || {};
  const raw = active[key] ?? fallback[key] ?? key;
  return interpolate(raw, values);
}

export type Translator = (
  key: string,
  values?: Record<string, string | number>,
) => string;
