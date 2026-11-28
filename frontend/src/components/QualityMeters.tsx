import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { QualityCheck } from "../lib/types";

type M = Pick<QualityCheck, "blur_score" | "brightness" | "contrast">;
interface Thresholds { blur: [number, number]; contrast: [number, number]; brightness_dark: [number, number]; brightness_bright: [number, number] }

// Fallback until the server's cut-offs arrive (they come from /images/quality-thresholds so ticks always match the check).
const DEFAULTS: Thresholds = { blur: [13, 33], contrast: [13, 18], brightness_dark: [35, 60], brightness_bright: [205, 225] };
let cached: Thresholds | null = null;

function useThresholds(): Thresholds {
  const [t, setT] = useState<Thresholds>(cached ?? DEFAULTS);
  useEffect(() => {
    if (cached) return;
    api<Thresholds>("/images/quality-thresholds").then((x) => { cached = x; setT(x); }).catch(() => {});
  }, []);
  return t;
}

function tone(v: number, poor: number, ok: number) {
  return v < poor ? "bg-danger" : v < ok ? "bg-amber" : "bg-ok";
}

export function QualityBadge({ label }: { label?: string | null }) {
  if (!label) return <span className="text-xs text-mute">No image</span>;
  const cls = label === "good" ? "bg-ok-soft text-ok" : label === "acceptable" ? "bg-amber-soft text-amber" : "bg-danger-soft text-danger";
  return <span className={`inline-block rounded px-2 py-0.5 text-xs font-semibold capitalize ${cls}`}>{label}</span>;
}

export default function QualityMeters({ q }: { q: M }) {
  const t = useThresholds();
  const meters = [
    { key: "blur_score", label: "Sharpness", max: 200, poor: t.blur[0], ok: t.blur[1] },
    { key: "brightness", label: "Brightness", max: 255, poor: t.brightness_dark[0], ok: t.brightness_dark[1] },
    { key: "contrast", label: "Contrast", max: 60, poor: t.contrast[0], ok: t.contrast[1] },
  ] as const;
  return (
    <div className="space-y-3">
      {meters.map((m) => {
        const v = q[m.key];
        const pct = Math.min(100, (v / m.max) * 100);
        return (
          <div key={m.key}>
            <div className="mb-1 flex justify-between text-xs">
              <span className="font-medium">{m.label}</span>
              <span className="tabular-nums text-mute">{v.toFixed(0)}</span>
            </div>
            <div className="relative h-2 rounded-sm bg-canvas" role="meter" aria-label={m.label} aria-valuenow={Math.round(v)} aria-valuemin={0} aria-valuemax={m.max}>
              <div className={`h-full rounded-sm ${tone(v, m.poor, m.ok)}`} style={{ width: `${pct}%` }} />
              <span className="absolute -top-0.5 h-3 w-px bg-ink/40" style={{ left: `${(m.poor / m.max) * 100}%` }} />
              <span className="absolute -top-0.5 h-3 w-px bg-ink/40" style={{ left: `${(m.ok / m.max) * 100}%` }} />
            </div>
          </div>
        );
      })}
      <p className="text-xs text-mute">Ticks mark the poor / acceptable thresholds.</p>
    </div>
  );
}

