import type { ImageRec, Prediction } from "../lib/types";
import RiskBadge from "./RiskBadge";

const RANK: Record<string, number> = { low: 0, moderate: 1, high: 2 };
const day = (i: ImageRec) => (i.capture_date ? new Date(i.capture_date) : i.created_at ? new Date(i.created_at) : null);
const pred = (i: ImageRec) => (i.prediction_result as unknown as Prediction | null) ?? null;

function change(a: Prediction, b: Prediction): string {
  const parts: string[] = [];
  parts.push(a.label === b.label ? `Same most-likely class (${b.label_name}).` : `Most-likely class changed from ${a.label_name} to ${b.label_name}.`);
  const ra = a.risk?.key, rb = b.risk?.key;
  if (ra && rb) {
    if (ra === rb) parts.push(`Risk level unchanged (${b.risk!.category}).`);
    else if (ra in RANK && rb in RANK) parts.push(RANK[rb] > RANK[ra] ? `Risk level moved up to ${b.risk!.category}: consider a clinical review.` : `Risk level moved down to ${b.risk!.category}.`);
    else parts.push(`Risk level is now ${b.risk!.category}.`);
  }
  const d = (b.confidence - a.confidence) * 100;
  if (Math.abs(d) >= 10) parts.push(`Confidence ${d > 0 ? "rose" : "fell"} by ${Math.abs(d).toFixed(0)} points.`);
  return parts.join(" ");
}

/** Follow-up timeline: analysed photos of one case in time order, with what changed since the previous one.
 *  A change between photos can also come from lighting, angle or distance, so it is never presented as a diagnosis. */
export default function FollowUp({ images }: { images: ImageRec[] }) {
  const rows = images.filter((i) => pred(i)).sort((x, y) => (day(x)?.getTime() ?? 0) - (day(y)?.getTime() ?? 0) || x.id - y.id);
  if (rows.length < 2) return null;
  return (
    <section aria-labelledby="fu-h" className="panel p-5">
      <h2 id="fu-h" className="text-lg font-semibold">Follow-up timeline</h2>
      <p className="mt-1 text-sm text-mute">How the AI-assisted result changed between photos of this case. Differences can also come from lighting, angle or distance.</p>
      <ol className="mt-4 space-y-4 border-l-2 border-line pl-5">
        {rows.map((img, k) => {
          const p = pred(img)!, prev = k ? pred(rows[k - 1]) : null, d = day(img), d0 = k ? day(rows[k - 1]) : null;
          const gap = d && d0 ? Math.round((d.getTime() - d0.getTime()) / 86_400_000) : null;
          return (
            <li key={img.id} className="relative">
              <span className="absolute -left-[27px] top-1.5 h-3 w-3 rounded-full border-2 border-accent bg-white" aria-hidden="true" />
              <p className="flex flex-wrap items-center gap-2 text-sm">
                <span className="font-semibold tabular-nums">{d ? d.toLocaleDateString() : "Date not recorded"}</span>
                {gap != null && gap > 0 && <span className="text-xs text-mute">{gap} day{gap === 1 ? "" : "s"} after the previous photo</span>}
                {p.risk && <RiskBadge risk={p.risk} />}
              </p>
              <p className="text-sm">Most similar to <span className="font-medium">{p.label_name}</span> <span className="tabular-nums text-mute">({(p.confidence * 100).toFixed(0)}% confidence)</span></p>
              {prev && <p className="mt-1 rounded bg-canvas px-3 py-2 text-xs">{change(prev, p)}</p>}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
