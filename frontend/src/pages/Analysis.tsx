import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import AuthedImage from "../components/AuthedImage";
import PredictionPanel from "../components/PredictionPanel";
import QualityMeters, { QualityBadge } from "../components/QualityMeters";
import RiskBadge from "../components/RiskBadge";
import { api, ApiError, downloadFile } from "../lib/api";
import { useAuth } from "../lib/auth";
import { imageCode } from "../lib/constants";
import { canViewFiles, showImage } from "../lib/permissions";
import type { HistoryItem, Prediction } from "../lib/types";

type View = "original" | "processed" | "lesion" | "cam" | "saliency";
const VIEWS: { key: View; label: string; note: string }[] = [
  { key: "original", label: "Original", note: "The photo as uploaded." },
  { key: "processed", label: "Preprocessed", note: "Cropped around the lesion, hair removed, colour and contrast normalised: what the model sees." },
  { key: "lesion", label: "Lesion region", note: "Detected lesion outline and mask (green); white square = analysed crop; orange = other spots." },
  { key: "cam", label: "AI attention map", note: "Warm colours mark where the model looked for its prediction. Not proof of clinical correctness." },
  { key: "saliency", label: "Saliency map", note: "Bright pixels are those whose change would most alter the score of the predicted class. A second, independent view; not proof of correctness." },
];

/** Medical image analysis screen (brief section 14): every stage of one analysis, the prediction, risk level and report. */
export default function Analysis() {
  const { id } = useParams();
  const { user } = useAuth();
  const [img, setImg] = useState<HistoryItem | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [shown, setShown] = useState<View[]>(["original", "processed", "lesion", "cam", "saliency"]);
  const [reportErr, setReportErr] = useState<string | null>(null);

  useEffect(() => { api<HistoryItem>(`/images/${id}`).then(setImg).catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load")); }, [id]);
  if (error) return <p role="alert" className="text-danger">{error}</p>;
  if (!img || !user) return <p className="text-mute">Loading…</p>;
  if (!canViewFiles(user) || !showImage(user, "prediction_result"))
    return <p className="text-mute">Your account type cannot view analysis images. <Link className="font-semibold text-accent underline" to="/history">Back to history</Link></p>;

  const pred = img.prediction_result as unknown as Prediction | null;
  const hasCam = !!pred?.explain;
  const hasSal = !!pred?.saliency;
  const views = VIEWS.filter((v) => (v.key !== "cam" || hasCam) && (v.key !== "saliency" || hasSal));
  const toggle = (k: View) => setShown((s) => (s.includes(k) ? (s.length > 1 ? s.filter((x) => x !== k) : s) : [...s, k]));
  const visible = views.filter((v) => shown.includes(v.key));

  async function report() {
    setReportErr(null);
    try { await downloadFile(`/cases/${img!.case_id}/report?format=pdf&image_id=${img!.id}`, `DermAI-${img!.case_code}.pdf`); }
    catch (e) { setReportErr(e instanceof ApiError ? e.message : "Could not generate the report."); }
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="h-page">Analysis {showImage(user, "image_id") && <span className="tabular-nums">{imageCode(img.id)}</span>}</h1>
          <p className="text-sm text-mute"><Link className="font-semibold text-accent underline" to={`/cases/${img.case_id}`}>{img.case_code}</Link>
            {showImage(user, "capture_date") && img.capture_date && ` · captured ${img.capture_date}`}
            {showImage(user, "body_location") && img.body_location && ` · ${img.body_location}`}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {pred?.risk && <RiskBadge risk={pred.risk} large />}
          <button className="btn-ghost" onClick={report}>Download report (PDF)</button>
        </div>
      </div>
      {reportErr && <p role="alert" className="text-sm text-danger">{reportErr}</p>}

      <section aria-label="Image comparison">
        <div className="mb-3 flex flex-wrap items-center gap-2" role="group" aria-label="Choose images to compare">
          <span className="text-sm text-mute">Compare:</span>
          {views.map((v) => (
            <button key={v.key} type="button" aria-pressed={shown.includes(v.key)} onClick={() => toggle(v.key)}
              className={`rounded-full border px-3 py-1 text-sm font-medium ${shown.includes(v.key) ? "border-accent bg-accent text-white" : "border-line bg-white hover:border-accent/50"}`}>{v.label}</button>
          ))}
        </div>
        <div className={`grid gap-4 ${visible.length === 1 ? "max-w-md" : visible.length === 2 ? "sm:grid-cols-2" : "sm:grid-cols-2 lg:grid-cols-3"}`}>
          {visible.map((v) => (
            <figure key={v.key} className="panel p-3">
              {img.analysis_status === "rejected_quality" && v.key !== "original"
                ? <div className="flex aspect-square items-center justify-center rounded border border-dashed border-line px-3 text-center text-xs text-mute">Not processed (poor quality)</div>
                : <AuthedImage id={img.id} variant={v.key} alt={v.label} className="aspect-square w-full rounded border border-line" />}
              <figcaption className="mt-2 text-sm font-semibold">{v.label}</figcaption>
              <p className="text-xs text-mute">{v.note}</p>
            </figure>
          ))}
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
        <div>
          {pred ? <PredictionPanel prediction={img.prediction_result as Record<string, unknown>} showModel={showImage(user, "model_version")} />
            : <p className="panel p-5 text-sm text-mute">{img.analysis_status === "rejected_quality" ? "This image was rejected for quality and not analysed." : "No AI analysis has been run on this image yet."}</p>}
        </div>
        <section className="panel p-5">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-mute">Details</h2>
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <div><dt className="text-xs text-mute">Status</dt><dd className="capitalize">{img.analysis_status?.replace("_", " ")}</dd></div>
            {showImage(user, "model_version") && <div><dt className="text-xs text-mute">Model version</dt><dd>{img.model_version ?? "-"}</dd></div>}
            {pred && <div><dt className="text-xs text-mute">Analysis time</dt><dd>{new Date(pred.analysed_at).toLocaleString()}</dd></div>}
            {showImage(user, "image_source") && <div><dt className="text-xs text-mute">Image source</dt><dd className="capitalize">{img.image_source}</dd></div>}
            {img.lesion_info && <div><dt className="text-xs text-mute">Lesion</dt><dd>{img.lesion_info.found ? `${(img.lesion_info.area_fraction * 100).toFixed(0)}% of photo${img.lesion_info.lesion_count > 1 ? `, ${img.lesion_info.lesion_count} spots` : ""}` : "not located"}</dd></div>}
            {showImage(user, "quality_label") && <div><dt className="text-xs text-mute">Image quality</dt><dd><QualityBadge label={img.quality_label} /></dd></div>}
          </dl>
          {showImage(user, "blur_score") && img.blur_score != null && <div className="mt-4"><QualityMeters q={{ blur_score: img.blur_score, brightness: img.brightness ?? 0, contrast: img.contrast ?? 0 }} /></div>}
          {!!img.quality_issues?.length && <ul className="mt-3 list-disc space-y-1 pl-5 text-xs">{img.quality_issues.map((i) => <li key={i}>{i}</li>)}</ul>}
        </section>
      </div>
    </div>
  );
}

