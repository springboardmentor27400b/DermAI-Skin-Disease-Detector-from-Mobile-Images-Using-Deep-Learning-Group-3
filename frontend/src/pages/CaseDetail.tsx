import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import AuthedImage from "../components/AuthedImage";
import Compare from "../components/Compare";
import FollowUp from "../components/FollowUp";
import ImageUploader from "../components/ImageUploader";
import Notes from "../components/Notes";
import PredictionPanel from "../components/PredictionPanel";
import QualityMeters, { QualityBadge } from "../components/QualityMeters";
import { api, ApiError, downloadFile } from "../lib/api";
import { useAuth } from "../lib/auth";
import { describePrediction, imageCode } from "../lib/constants";
import { can, canViewFiles, showCase, showImage } from "../lib/permissions";
import type { CaseDetail as Case, ImageRec, Prediction } from "../lib/types";

function Field({ label, value }: { label: string; value: string | number | null | undefined }) {
  return <div><dt className="text-xs text-mute">{label}</dt><dd className="text-sm">{value ?? "—"}</dd></div>;
}

export default function CaseDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const { user } = useAuth();
  const [c, setC] = useState<Case | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sel, setSel] = useState<number[]>([]);
  const [comparing, setComparing] = useState(false);
  const [reportErr, setReportErr] = useState<string | null>(null);

  const load = useCallback(() => {
    api<Case>(`/cases/${id}`).then(setC).catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load"));
  }, [id]);
  useEffect(load, [load]);

  if (error) return <p role="alert" className="text-danger">{error}</p>;
  if (!c || !user) return <p className="text-mute">Loading…</p>;

  const see = (f: string) => showImage(user, f);
  const files = canViewFiles(user);
  const canCompare = can(user, "compare") && c.images.length >= 2;
  const chosen = c.images.filter((i) => sel.includes(i.id));
  const caseInfo: [string, string | number | null | undefined][] = [
    ["Case ID", c.case_code],
    ...(showCase(user, "patient_age") ? ([["Age", c.patient_age], ["Gender", c.patient_gender]] as [string, string | number | null | undefined][]) : []),
    ...(showCase(user, "body_location") ? ([["Body location", c.body_location]] as [string, string | null | undefined][]) : []),
    ...(showCase(user, "medical_history") ? ([["Relevant medical history", c.medical_history], ["Known allergies", c.known_allergies]] as [string, string | null | undefined][]) : []),
  ];

  function toggle(img: ImageRec) {
    setComparing(false);
    setSel((s) => (s.includes(img.id) ? s.filter((x) => x !== img.id) : [...s, img.id].slice(-2)));
  }
  async function removeImage(img: ImageRec) {
    if (!confirm("Delete this image permanently?")) return;
    await api(`/images/${img.id}`, { method: "DELETE" }); setSel((s) => s.filter((x) => x !== img.id)); load();
  }
  async function report(format: "pdf" | "json" | "csv", imageId?: number) {
    setReportErr(null);
    try { await downloadFile(`/cases/${c!.id}/report?format=${format}${imageId ? `&image_id=${imageId}` : ""}`, `DermAI-${c!.case_code}.${format}`); }
    catch (e) { setReportErr(e instanceof ApiError ? e.message : "Could not generate the report."); }
  }
  async function removeCase() {
    if (!confirm("Delete this case and all its images permanently?")) return;
    await api(`/cases/${c!.id}`, { method: "DELETE" }); nav("/cases");
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="h-page tabular-nums">{c.case_code}</h1>
          <p className="text-sm text-mute">{c.created_at && `Created ${new Date(c.created_at).toLocaleString()}`}{showCase(user, "owner_name") && c.owner_name && ` · patient ${c.owner_name}`}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-mute">Report</span>
          {(["pdf", "json", "csv"] as const).map((f) => <button key={f} className="btn-ghost py-1 uppercase" onClick={() => report(f)}>{f}</button>)}
          {c.permissions.delete && <button className="btn-danger" onClick={removeCase}>Delete case</button>}
        </div>
      </div>
      {reportErr && <p role="alert" className="text-sm text-danger">{reportErr}</p>}

      <dl className="panel grid grid-cols-2 gap-4 p-5 sm:grid-cols-4">
        {caseInfo.map(([l, v]) => <div key={l} className={l.startsWith("Relevant") || l.startsWith("Known") ? "col-span-2" : ""}><Field label={l} value={v} /></div>)}
      </dl>
      {user.role === "researcher" || user.role === "ml_engineer" ? <p className="-mt-4 text-sm text-mute">De-identified view. Personal details are not shown.</p> : null}
      {user.role === "admin" && <p className="-mt-4 text-sm text-mute">Operational view for auditing and support. Clinical details and images are not shown.</p>}

      {c.permissions.upload && <ImageUploader caseId={c.id} defaultLocation={c.body_location ?? null} onUploaded={load} />}

      <section>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-semibold">Analysis history <span className="text-sm font-normal text-mute">({c.images.length})</span></h2>
          {canCompare && (
            <div className="flex items-center gap-3 text-sm">
              <span className="text-mute">{sel.length < 2 ? `Tick two images to compare (${sel.length}/2)` : "Two images selected"}</span>
              <button className="btn-primary py-1" disabled={sel.length !== 2} onClick={() => setComparing(true)}>Compare</button>
            </div>
          )}
        </div>
        {comparing && chosen.length === 2 && <div className="mb-4"><Compare items={[chosen[0], chosen[1]]} onClose={() => setComparing(false)} /></div>}
        {see("prediction_result") && <div className="mb-4"><FollowUp images={c.images} /></div>}
        {c.images.length === 0 ? <p className="text-mute">No images yet.</p> : (
          <ul className="space-y-4">
            {[...c.images].reverse().map((img) => (
              <li key={img.id} className="panel p-4">
                <div className={files ? "grid gap-4 md:grid-cols-[auto_1fr]" : ""}>
                  {files && (
                    <div className="flex flex-wrap gap-3">
                      <figure><AuthedImage id={img.id} variant="original" alt="Original upload" className="h-32 w-32 rounded border border-line" /><figcaption className="mt-1 text-xs text-mute">Original</figcaption></figure>
                      <figure>{img.analysis_status === "rejected_quality"
                        ? <div className="flex h-32 w-32 items-center justify-center rounded border border-dashed border-line px-2 text-center text-xs text-mute">Not processed (poor quality)</div>
                        : <AuthedImage id={img.id} variant="processed" alt="Preprocessed image" className="h-32 w-32 rounded border border-line" />}
                        <figcaption className="mt-1 text-xs text-mute">Preprocessed</figcaption></figure>
                      {see("prediction_result") && (img.prediction_result as unknown as Prediction | null)?.explain && (
                        <figure><AuthedImage id={img.id} variant="cam" alt="Attention map" className="h-32 w-32 rounded border border-line" /><figcaption className="mt-1 text-xs text-mute">Attention map</figcaption></figure>
                      )}
                      {see("lesion_info") && img.lesion_info && (
                        <figure><AuthedImage id={img.id} variant="lesion" alt="Lesion detection overlay" className="h-32 w-32 rounded border border-line" />
                          <figcaption className="mt-1 text-xs text-mute">{img.lesion_info.found ? `Lesion${img.lesion_info.lesion_count > 1 ? `s (${img.lesion_info.lesion_count})` : ""}` : "Lesion not located"}</figcaption></figure>
                      )}
                    </div>
                  )}
                  <div className="min-w-0">
                    <div className="mb-3 flex flex-wrap items-center gap-2">
                      {see("quality_label") && <QualityBadge label={img.quality_label} />}
                      <span className="rounded bg-canvas px-2 py-0.5 text-xs capitalize">{img.analysis_status?.replace("_", " ")}</span>
                      {canCompare && <label className="ml-auto flex items-center gap-2 text-sm"><input type="checkbox" checked={sel.includes(img.id)} onChange={() => toggle(img)} />Compare</label>}
                    </div>
                    <dl className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4">
                      {see("image_id") && <Field label="Image ID" value={imageCode(img.id)} />}
                      {see("capture_date") && <Field label="Capture date" value={img.capture_date} />}
                      {see("body_location") && <Field label="Body location" value={img.body_location} />}
                      {see("image_source") && <Field label="Image source" value={img.image_source} />}
                      {!see("capture_date") && img.created_at && <Field label="Recorded" value={new Date(img.created_at).toLocaleDateString()} />}
                      {see("model_version") && <Field label="Model version" value={img.model_version} />}
                      {see("prediction_result") && <div className="col-span-2"><Field label="Prediction result" value={describePrediction(img.prediction_result)} /></div>}
                    </dl>
                    {see("prediction_result") && img.prediction_result && <PredictionPanel prediction={img.prediction_result} showModel={see("model_version")} />}
                    {see("blur_score") && img.blur_score != null ? (
                      <details className="mt-3">
                        <summary className="cursor-pointer text-sm font-medium text-accent">Image quality details</summary>
                        <div className="mt-3 grid gap-4 sm:grid-cols-2">
                          <QualityMeters q={{ blur_score: img.blur_score, brightness: img.brightness ?? 0, contrast: img.contrast ?? 0 }} />
                          <div className="text-sm">
                            {img.width && <p className="text-mute">{img.width}×{img.height} · {img.file_format}{img.file_size_bytes ? ` · ${(img.file_size_bytes / 1024).toFixed(0)} KB` : ""}</p>}
                            {!!img.quality_issues?.length && <ul className="mt-2 list-disc space-y-1 pl-5">{img.quality_issues.map((i) => <li key={i}>{i}</li>)}</ul>}
                          </div>
                        </div>
                      </details>
                    ) : !!img.quality_issues?.length && <ul className="mt-3 list-disc space-y-1 pl-5 text-sm">{img.quality_issues.map((i) => <li key={i}>{i}</li>)}</ul>}
                    {files && see("prediction_result") && img.analysis_status === "completed" && <Link to={`/analysis/${img.id}`} className="mt-3 mr-4 inline-block text-xs font-semibold text-accent underline">Open analysis screen</Link>}
                    <button className="mt-3 mr-4 text-xs text-accent underline" onClick={() => report("pdf", img.id)}>Download report (PDF) for this image</button>
                    {c.permissions.delete && <button className="mt-3 text-xs text-danger underline" onClick={() => removeImage(img)}>Delete image</button>}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-3 text-sm text-mute">See every analysis in <Link to="/history" className="font-semibold text-accent underline">History</Link>.</p>
      </section>

      {c.permissions.add_notes && <Notes caseId={c.id} notes={c.notes} initial={c.clinical_notes ?? null} user={user} onAdded={load} />}
    </div>
  );
}

