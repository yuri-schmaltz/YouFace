/**
 * Utilitário para resolver a URL base da API com suporte a rede local (LAN).
 * Evita fixar 'localhost' quando o cockpit é acessado a partir de outros dispositivos.
 */
let cachedApiUrl: string | null = null;

export function getInitialApiUrl(): string {
  if (typeof window === "undefined") {
    return "http://127.0.0.1:8000";
  }
  if (window.location.port === "8000") {
    return "";
  }
  return `${window.location.protocol}//${window.location.hostname}:8000`;
}

export async function resolveApiUrl(): Promise<string> {
  if (cachedApiUrl !== null) {
    return cachedApiUrl;
  }

  if (typeof window === "undefined") {
    return "http://127.0.0.1:8000";
  }

  try {
    const res = await fetch("/config.json");
    if (res.ok) {
      const data = await res.json();
      // Caminho relativo preferido (mesma origem / reverse proxy) — P2-3 do SWOT.
      if (typeof data.apiUrl === "string" && data.apiUrl === "") {
        cachedApiUrl = "";
        return cachedApiUrl;
      }
      if (data.apiUrl) {
        // Se a apiUrl configurada for localhost mas o usuário estiver acessando via IP da LAN
        try {
          const parsed = new URL(data.apiUrl);
          if ((parsed.hostname === "localhost" || parsed.hostname === "127.0.0.1") && window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1") {
            cachedApiUrl = `${window.location.protocol}//${window.location.hostname}:${parsed.port || "8000"}`;
            return cachedApiUrl;
          }
        } catch {
          // fallback to data.apiUrl
        }
        cachedApiUrl = data.apiUrl;
        return cachedApiUrl;
      }
    }
  } catch {
    // Fallback relativo se servido na mesma porta, ou porta 8000 no mesmo host
  }

  // Se o frontend está rodando na mesma porta da API (export estático no FastAPI)
  if (window.location.port === "8000" || window.location.port === "") {
    cachedApiUrl = "";
    return "";
  }

  cachedApiUrl = `${window.location.protocol}//${window.location.hostname}:8000`;
  return cachedApiUrl;
}

export function formatApiUrl(baseUrl: string, path: string): string {
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  if (!baseUrl || baseUrl === "") {
    return cleanPath;
  }
  return `${baseUrl.replace(/\/+$/, "")}${cleanPath}`;
}
