import type { Prediction } from "../lib/types";
import RiskBadge from "./RiskBadge";

/** AI-assisted result: top predictions with calibrated probabilities, risk category and the attention-map note. Worded as an estimate, never a diagnosis. */
export default function PredictionPanel({ prediction, showModel }: { prediction: Record<string, unknown>; showModel: boolean }) {
  const p = prediction as unknown as Prediction;
  if (!p.top_n?.length) return null;
  const ex = p.explain;
  return (
    <section className="mt-3 rounded border border-line bg-canvas p-4" aria-label="AI-assisted result">
      <p className="text-xs font-semibold uppercase tracking-wider text-mute">AI-assisted result</p>
      <p className="mt-1 text-sm">Most similar to <span className="font-semibold">{p.label_name}</span> <span className="tabular-nums text-mute">({(p.confidence * 100).toFixed(0)}% confidence)</span></p>
      {p.risk && (
        <div className="mt-3 rounded border border-line bg-white p-3">
          <div className="flex flex-wrap items-center gap-2"><span className="text-sm font-medium">Risk level</span><RiskBadge risk={p.risk} /></div>
          <p className="mt-2 text-sm">{p.risk.recommendation}</p>
          {p.risk.reasons.length > 0 && <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-mute">{p.risk.reasons.map((r) => <li key={r}>{r}</li>)}</ul>}
        </div>
      )}
      <ul className="mt-3 space-y-2">
        {p.top_n.map((t) => (
          <li key={t.label} className="text-sm">
            <div className="mb-1 flex justify-between"><span>{t.name}</span><span className="tabular-nums text-mute">{(t.probability * 100).toFixed(0)}%</span></div>
            <div className="h-2 rounded-sm bg-white"><div className="h-full rounded-sm bg-accent" style={{ width: `${t.probability * 100}%` }} /></div>
          </li>
        ))}
      </ul>
      {ex && (
        <p className="mt-3 text-xs text-mute">
          The attention map ({ex.method}) shows where the model looked. {ex.attention_in_lesion != null && <>About {(ex.attention_in_lesion * 100).toFixed(0)}% of its attention fell inside the detected lesion, which covers {((ex.lesion_share_of_crop ?? 0) * 100).toFixed(0)}% of the analysed area. </>}{ex.stability != null && <>Explanation stability (mirrored photo) is {ex.stability.toFixed(2)}, where 1 means the same regions are highlighted. </>}It does not show that the result is clinically correct.
        </p>
      )}
      {p.low_confidence && <p role="status" className="mt-3 rounded bg-amber-soft px-3 py-2 text-sm text-amber">The model is not confident about this image. Treat the result with extra caution and have it checked by a clinician.</p>}
      {p.caveats?.length > 0 && <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-mute">{p.caveats.map((c) => <li key={c}>{c}</li>)}</ul>}
      <p className="mt-3 text-xs text-mute">{p.disclaimer}</p>
      {showModel && <p className="mt-1 text-xs text-mute">Model {p.model?.version}{p.model?.arch ? ` (${p.model.arch})` : ""} · {new Date(p.analysed_at).toLocaleString()}</p>}
    </section>
  );
}

