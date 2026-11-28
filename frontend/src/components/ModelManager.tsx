import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../lib/api";
import type { ModelVersion } from "../lib/types";

const f3 = (v: number | null) => (v == null ? "-" : v.toFixed(3));

/** Model registry for administrators (brief section 18): versions, evaluation, deploy / roll back, re-analyse stored images. */
export default function ModelManager() {
  const [rows, setRows] = useState<ModelVersion[]>([]);
  const [msg, setMsg] = useState<{ ok: boolean; t: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => { api<ModelVersion[]>("/models/versions").then(setRows).catch(() => setRows([])); }, []);
  useEffect(load, [load]);

  async function run(label: string, path: string) {
    setBusy(true); setMsg(null);
    try { const r = await api<Record<string, unknown>>(path, { method: "POST" }); setMsg({ ok: true, t: `${label} done${"processed" in r ? `: ${r.processed} analysed, ${r.failed} failed` : ""}.` }); load(); }
    catch (e) { setMsg({ ok: false, t: e instanceof ApiError ? e.message : `${label} failed.` }); }
    finally { setBusy(false); }
  }

  return (
    <section>
      <h2 className="mb-3 text-lg font-semibold">Models</h2>
      {rows.length === 0 ? <p className="text-sm text-mute">No model versions found in the models folder. Export one with ml/export_model.py.</p> : (
        <div className="panel overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-line text-mute"><tr>{["Version", "Architecture", "Macro-F1", "Bal. acc.", "AUC", "Maps", "Risk", ""].map((h) => <th key={h} className="px-3 py-2 font-medium">{h}</th>)}</tr></thead>
            <tbody className="divide-y divide-line">
              {rows.map((r) => (
                <tr key={r.version}>
                  <td className="px-3 py-2 font-medium">{r.version} {r.active && <span className="ml-1 rounded bg-ok-soft px-1.5 py-0.5 text-xs text-ok">active</span>}</td>
                  <td className="px-3 py-2">{r.members ? `ensemble (${r.members.join(" + ")})` : r.arch}</td>
                  <td className="px-3 py-2 tabular-nums">{f3(r.macro_f1)}</td><td className="px-3 py-2 tabular-nums">{f3(r.balanced_accuracy)}</td><td className="px-3 py-2 tabular-nums">{f3(r.macro_auc)}</td>
                  <td className="px-3 py-2">{r.explainability ? "yes" : "no"}</td><td className="px-3 py-2">{r.risk_protocol ? "yes" : "no"}</td>
                  <td className="px-3 py-2 text-right">{!r.active && <button className="btn-ghost py-1" disabled={busy} onClick={() => confirm(`Deploy ${r.version}? New analyses will use it.`) && run("Activation", `/models/activate?version=${encodeURIComponent(r.version)}`)}>Deploy / roll back</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {rows.some((r) => r.training && Object.values(r.training).some((v) => v != null)) && (
        <details className="mt-3 text-sm">
          <summary className="cursor-pointer font-medium text-accent">Training history per version</summary>
          <ul className="mt-2 space-y-1 text-xs text-mute">
            {rows.map((r) => {
              const t = r.training ?? {};
              return <li key={r.version}><span className="font-medium text-ink">{r.version}</span>: {r.trained_at?.slice(0, 10) ?? "date unknown"} · {r.preprocessing ?? "recipe unknown"}
                {t.best_epoch != null && ` · best epoch ${t.best_epoch} of ${t.epochs ?? "?"}`}{t.n_train != null && ` · ${t.n_train} training images`}{t.imbalance && ` · imbalance ${t.imbalance}`}{t.aug && ` · aug ${t.aug}`}
                {t.lr != null && ` · lr ${t.lr}`}{t.seed != null && ` · seed ${t.seed}`}{` · split fingerprint ${t.folds_sha256 ?? "not recorded"}`}</li>;
            })}
          </ul>
          <p className="mt-1 text-xs text-mute">Two versions with the same split fingerprint were trained and tested on the same patient folds.</p>
        </details>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button className="btn-ghost" disabled={busy} onClick={() => run("Reload", "/models/reload")}>Reload models</button>
        <button className="btn-ghost" disabled={busy} onClick={() => run("Re-analysis of pending images", "/models/reanalyze")}>Analyse pending images</button>
        <button className="btn-ghost" disabled={busy} onClick={() => confirm("Re-run every stored image with the active model? Earlier results are replaced.") && run("Re-analysis of all images", "/models/reanalyze?all_images=true")}>Re-analyse all</button>
        {msg && <span role={msg.ok ? "status" : "alert"} className={`text-sm ${msg.ok ? "text-ok" : "text-danger"}`}>{msg.t}</span>}
      </div>
      <p className="mt-2 text-xs text-mute">Each result keeps the model version that produced it. Rolling back changes new analyses only until you re-analyse.</p>
    </section>
  );
}

