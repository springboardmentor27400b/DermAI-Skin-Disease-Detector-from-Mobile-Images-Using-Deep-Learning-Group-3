import type { ReactNode } from "react";
import { useAuth } from "../lib/auth";
import { describePrediction, imageCode } from "../lib/constants";
import { canViewFiles, showImage } from "../lib/permissions";
import type { ImageRec } from "../lib/types";
import AuthedImage from "./AuthedImage";
import { QualityBadge } from "./QualityMeters";

export type CompareImage = ImageRec & { case_code?: string };

function delta(a?: number | null, b?: number | null): string {
  if (a == null || b == null) return "";
  const d = b - a;
  return Math.abs(d) < 0.5 ? "no change" : `${d > 0 ? "+" : "−"}${Math.abs(d).toFixed(0)}`;
}
const num = (v?: number | null) => (v == null ? "—" : v.toFixed(0));

/** Side-by-side comparison. Rows and images follow what the signed-in role may see. */
export default function Compare({ items, onClose }: { items: [CompareImage, CompareImage]; onClose: () => void }) {
  const { user } = useAuth();
  const [a, b] = [...items].sort((x, y) => (x.created_at ?? "").localeCompare(y.created_at ?? ""));
  const see = (f: string) => showImage(user, f);
  const files = canViewFiles(user);
  const hasCases = !!(a.case_code && b.case_code);
  const row = (label: string, va: ReactNode, vb: ReactNode, change?: string) => (
    <tr key={label} className="border-t border-line">
      <th scope="row" className="px-3 py-2 text-left font-medium text-mute">{label}</th>
      <td className="px-3 py-2">{va}</td><td className="px-3 py-2">{vb}</td>
      <td className="px-3 py-2 tabular-nums text-mute">{change ?? ""}</td>
    </tr>
  );
  const cap = (s?: string | null) => <span className="capitalize">{(s ?? "—").replace("_", " ")}</span>;
  const anyPrediction = !!(a.prediction_result || b.prediction_result);

  return (
    <section className="panel p-5" aria-label="Comparison of two analyses">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Compare analyses</h2>
        <button className="btn-ghost py-1" onClick={onClose}>Close</button>
      </div>
      {files && (
        <div className="grid gap-4 sm:grid-cols-2">
          {([["Earlier", a], ["Later", b]] as const).map(([tag, img]) => (
            <div key={img.id}>
              <p className="mb-2 text-sm font-semibold">{tag}{see("image_id") && ` · ${imageCode(img.id)}`}</p>
              <div className="grid grid-cols-2 gap-2">
                <figure><AuthedImage id={img.id} variant="original" alt={`${tag} original`} className="aspect-square w-full rounded border border-line" /><figcaption className="mt-1 text-xs text-mute">Original</figcaption></figure>
                <figure>{img.analysis_status === "rejected_quality"
                  ? <div className="flex aspect-square items-center justify-center rounded border border-dashed border-line text-center text-xs text-mute">Not processed</div>
                  : <AuthedImage id={img.id} variant="processed" alt={`${tag} preprocessed`} className="aspect-square w-full rounded border border-line" />}
                  <figcaption className="mt-1 text-xs text-mute">Preprocessed</figcaption></figure>
              </div>
            </div>
          ))}
        </div>
      )}
      <div className="mt-5 overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead><tr className="text-mute"><th className="px-3 py-2 font-medium"><span className="sr-only">Field</span></th><th className="px-3 py-2 font-medium">Earlier</th><th className="px-3 py-2 font-medium">Later</th><th className="px-3 py-2 font-medium">Change</th></tr></thead>
          <tbody>
            {hasCases && row("Case ID", a.case_code, b.case_code)}
            {see("image_id") && row("Image ID", imageCode(a.id), imageCode(b.id))}
            {see("capture_date") && row("Capture date", a.capture_date ?? "—", b.capture_date ?? "—")}
            {see("body_location") && row("Body location", a.body_location ?? "—", b.body_location ?? "—")}
            {see("image_source") && row("Image source", cap(a.image_source), cap(b.image_source))}
            {see("quality_label") && row("Quality", <QualityBadge label={a.quality_label} />, <QualityBadge label={b.quality_label} />)}
            {see("blur_score") && row("Sharpness", num(a.blur_score), num(b.blur_score), delta(a.blur_score, b.blur_score))}
            {see("brightness") && row("Brightness", num(a.brightness), num(b.brightness), delta(a.brightness, b.brightness))}
            {see("contrast") && row("Contrast", num(a.contrast), num(b.contrast), delta(a.contrast, b.contrast))}
            {see("analysis_status") && row("Analysis status", cap(a.analysis_status), cap(b.analysis_status))}
            {see("model_version") && row("Model version", a.model_version ?? "—", b.model_version ?? "—", a.model_version && b.model_version && a.model_version !== b.model_version ? "model changed" : "")}
            {see("prediction_result") && row("Prediction result", describePrediction(a.prediction_result), describePrediction(b.prediction_result))}
          </tbody>
        </table>
      </div>
      {see("prediction_result") && !anyPrediction && (
        <p className="mt-3 text-sm text-mute">Prediction comparison becomes available once the classifier is added (Milestone 2). For now you can compare image quality, source and capture details.</p>
      )}
    </section>
  );
}

