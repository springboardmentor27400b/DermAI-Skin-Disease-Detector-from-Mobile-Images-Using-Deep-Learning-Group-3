import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { ActiveModel } from "../lib/types";

const pct = (v?: number) => (v == null ? "-" : v.toFixed(3));

/** Deployed model and its cross-validated performance. Shown to roles that may see evaluation data. */
export default function ModelPerformance() {
  const [m, setM] = useState<ActiveModel | null>(null);
  useEffect(() => { api<ActiveModel>("/models/active").then(setM).catch(() => {}); }, []);
  if (!m?.available) return null;
  const ev = m.evaluation;
  return (
    <section className="panel p-5" aria-labelledby="mp-h">
      <h2 id="mp-h" className="text-lg font-semibold">Deployed model</h2>
      <p className="mt-1 text-sm text-mute">
        {m.version} · {m.arch}{m.members ? ` (${m.members.map((x) => `${x.arch} ${(x.weight * 100).toFixed(0)}%`).join(", ")})` : ""} · {m.dataset}
        {m.explainability_available ? " · attention maps on" : " · no attention maps"}
      </p>
      {ev && (
        <dl className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-5">
          {([["Macro-F1", ev.macro_f1], ["Balanced accuracy", ev.balanced_accuracy], ["AUC (one-vs-rest)", ev.macro_auc_ovr], ["MCC", ev.mcc], ["Calibration error", ev.ece]] as const).map(([l, v]) => (
            <div key={l}><dt className="text-xs text-mute">{l}</dt><dd className="text-xl font-semibold tabular-nums">{pct(v)}</dd></div>
          ))}
        </dl>
      )}
      {ev?.source && <p className="mt-3 text-xs text-mute">{ev.source}. Not a clinical performance claim.</p>}
      {m.risk_protocol && <p className="mt-1 text-xs text-mute">Risk protocol {m.risk_protocol.protocol}: Low below {(m.risk_protocol.t_low * 100).toFixed(0)}% and High from {(m.risk_protocol.t_high * 100).toFixed(0)}% estimated skin-cancer likelihood.</p>}
    </section>
  );
}

