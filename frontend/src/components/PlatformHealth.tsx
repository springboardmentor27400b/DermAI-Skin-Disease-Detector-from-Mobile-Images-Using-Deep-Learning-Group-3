import { useEffect, useState } from "react";
import { api } from "../lib/api";

interface Metrics {
  uptime_seconds: number; requests_total: number; by_status: Record<string, number>; slow_requests_over_2s: number;
  users: number; cases: number; images: number; analysis_status: Record<string, number>; model_usage: Record<string, number>;
  failed_logins_total: number; blocked_logins_total: number; active_model: string | null;
  routes: Record<string, { count: number; mean_ms: number; max_ms: number }>;
}
interface Ready { status: string; checks: Record<string, string> }

const fmtUp = (s: number) => (s >= 86400 ? `${Math.floor(s / 86400)} d ${Math.floor((s % 86400) / 3600)} h` : s >= 3600 ? `${Math.floor(s / 3600)} h ${Math.floor((s % 3600) / 60)} min` : `${Math.floor(s / 60)} min`);

/** Platform health for administrators: readiness probe plus the request, usage and security counters from /api/metrics. */
export default function PlatformHealth() {
  const [m, setM] = useState<Metrics | null>(null);
  const [ready, setReady] = useState<Ready | "degraded" | null>(null);
  const load = () => {
    api<Metrics>("/metrics").then(setM).catch(() => setM(null));
    api<Ready>("/health/ready").then(setReady).catch(() => setReady("degraded"));   // the endpoint answers 503 when something is wrong
  };
  useEffect(() => { load(); const t = setInterval(load, 30_000); return () => clearInterval(t); }, []);
  if (!m) return null;
  const ok = ready !== "degraded" && ready?.status === "ok";
  const errors = m.by_status["5xx"] ?? 0;
  const slowest = Object.entries(m.routes).sort((a, b) => b[1].mean_ms - a[1].mean_ms).slice(0, 3);
  const tile = (label: string, value: string | number, warn = false) => (
    <div><dt className="text-xs text-mute">{label}</dt><dd className={`text-xl font-semibold tabular-nums ${warn ? "text-danger" : ""}`}>{value}</dd></div>
  );
  return (
    <section className="panel p-5" aria-labelledby="ph-h">
      <div className="flex flex-wrap items-center gap-3">
        <h2 id="ph-h" className="text-lg font-semibold">Platform health</h2>
        <span className={`rounded px-2 py-0.5 text-xs font-semibold ${ok ? "bg-ok-soft text-ok" : "bg-danger-soft text-danger"}`}>{ok ? "Ready" : "Degraded"}</span>
        {ready && ready !== "degraded" && <span className="text-xs text-mute">database {ready.checks.database} · storage {ready.checks.storage} · model {ready.checks.model}</span>}
        <button className="ml-auto text-xs font-semibold text-accent underline" onClick={load}>Refresh</button>
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-6">
        {tile("Uptime", fmtUp(m.uptime_seconds))}{tile("Requests", m.requests_total)}{tile("Server errors (5xx)", errors, errors > 0)}
        {tile("Slow requests (over 2 s)", m.slow_requests_over_2s, m.slow_requests_over_2s > 0)}{tile("Failed sign-ins", m.failed_logins_total)}{tile("Blocked sign-ins", m.blocked_logins_total, m.blocked_logins_total > 0)}
      </dl>
      {slowest.length > 0 && <p className="mt-3 text-xs text-mute">Slowest routes by mean time: {slowest.map(([r, v]) => `${r} ${v.mean_ms.toFixed(0)} ms`).join(" · ")}</p>}
      <p className="mt-1 text-xs text-mute">Active model {m.active_model ?? "none"} · analyses: {Object.entries(m.analysis_status).map(([k, v]) => `${k.replace("_", " ")} ${v}`).join(", ") || "none yet"}</p>
    </section>
  );
}
