const BASE = import.meta.env.VITE_API_URL ?? "/api";
const TOKEN_KEY = "dermai.token";

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (t: string) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

type Opts = { method?: string; json?: unknown; form?: FormData | URLSearchParams };

function messageFrom(body: any, fallback: string): string {
  const d = body?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((e) => e.msg ?? "").filter(Boolean).join("; ") || fallback;
  return fallback;
}

export async function api<T = unknown>(path: string, { method, json, form }: Opts = {}): Promise<T> {
  const headers: Record<string, string> = {};
  const token = tokenStore.get();
  if (token) headers.Authorization = `Bearer ${token}`;
  let body: BodyInit | undefined;
  if (json !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(json); }
  else if (form) body = form;

  const res = await fetch(`${BASE}${path}`, { method: method ?? (body ? "POST" : "GET"), headers, body });
  if (res.status === 401 && token) { tokenStore.clear(); window.dispatchEvent(new Event("dermai:logout")); }
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new ApiError(res.status, messageFrom(data, `Request failed (${res.status})`));
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

export async function fetchImageBlobUrl(imageId: number, variant: "original" | "processed" | "lesion" | "cam" | "saliency"): Promise<string> {
  const token = tokenStore.get();
  const res = await fetch(`${BASE}/images/${imageId}/file?variant=${variant}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new ApiError(res.status, "Image unavailable");
  return URL.createObjectURL(await res.blob());
}

/** Download a protected file (report) with the bearer token and hand it to the browser. */
export async function downloadFile(path: string, fallbackName: string): Promise<void> {
  const token = tokenStore.get();
  const res = await fetch(`${BASE}${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!res.ok) throw new ApiError(res.status, messageFrom(await res.json().catch(() => null), "Could not generate the report."));
  const name = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") ?? "")?.[1] ?? fallbackName;
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a"); a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

