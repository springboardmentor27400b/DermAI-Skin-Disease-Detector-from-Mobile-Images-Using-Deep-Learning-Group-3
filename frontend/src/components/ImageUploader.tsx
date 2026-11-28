import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../lib/api";
import { IMAGE_SOURCES, LOCATIONS } from "../lib/constants";
import type { ImageRec, QualityCheck } from "../lib/types";
import ImageEditor from "./ImageEditor";
import QualityMeters, { QualityBadge } from "./QualityMeters";

const today = () => new Date().toISOString().slice(0, 10);

/** Capture/select -> quality check -> details -> user confirmation -> upload. */
export default function ImageUploader({ caseId, defaultLocation, onUploaded }: { caseId: number; defaultLocation: string | null; onUploaded: (i: ImageRec) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [source, setSource] = useState("gallery");
  const [location, setLocation] = useState(defaultLocation ?? "");
  const [date, setDate] = useState(today());
  const [preview, setPreview] = useState<string | null>(null);
  const [quality, setQuality] = useState<QualityCheck | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState<"check" | "upload" | null>(null);
  const camRef = useRef<HTMLInputElement>(null);
  const galRef = useRef<HTMLInputElement>(null);

  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  function reset() { setEditing(false); setFile(null); setPreview(null); setQuality(null); setError(null); setDate(today()); }

  async function pick(f: File | undefined, src: "camera" | "gallery") {
    if (!f) return;
    reset();
    setFile(f); setSource(src); setPreview(URL.createObjectURL(f)); setBusy("check");
    try {
      const form = new FormData(); form.append("file", f);
      setQuality(await api<QualityCheck>("/images/check-quality", { form }));
    } catch (e) { setError(e instanceof ApiError ? e.message : "Quality check failed."); }
    finally { setBusy(null); }
  }

  async function upload() {
    if (!file) return;
    setBusy("upload"); setError(null);
    try {
      const form = new FormData();
      form.append("file", file); form.append("image_source", source); form.append("capture_date", date);
      if (location) form.append("body_location", location);
      onUploaded(await api<ImageRec>(`/cases/${caseId}/images`, { form })); reset();
    } catch (e) { setError(e instanceof ApiError ? e.message : "Upload failed."); }
    finally { setBusy(null); }
  }

  return (
    <div className="panel p-5">
      <h2 className="text-lg font-semibold">Capture or upload an image</h2>
      <p className="mt-1 text-sm text-mute">Use even, natural light. Keep the lesion in the centre, in focus, with some surrounding skin visible.</p>

      <input ref={camRef} type="file" accept="image/*" capture="environment" hidden onChange={(e) => { pick(e.target.files?.[0], "camera"); e.target.value = ""; }} />
      <input ref={galRef} type="file" accept="image/jpeg,image/png" hidden onChange={(e) => { pick(e.target.files?.[0], "gallery"); e.target.value = ""; }} />

      {!file && (
        <div className="mt-4 flex flex-wrap gap-2">
          <button className="btn-primary" onClick={() => camRef.current?.click()}>Take photo</button>
          <button className="btn-ghost" onClick={() => galRef.current?.click()}>Choose from gallery</button>
        </div>
      )}

      {error && <p role="alert" className="mt-4 rounded bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}

      {file && editing && (
        <div className="mt-5"><ImageEditor file={file} onCancel={() => setEditing(false)} onApply={(f) => { setEditing(false); pick(f, source === "camera" ? "camera" : "gallery"); }} /></div>
      )}
      {file && !editing && (
        <div className="mt-5 grid gap-5 sm:grid-cols-2">
          {preview && <img src={preview} alt="Selected skin image preview" className="aspect-square w-full rounded border border-line object-cover" />}
          <div>
            {busy === "check" && <p className="text-sm text-mute">Checking image quality…</p>}
            {quality && (
              <>
                <div className="mb-3 flex items-center gap-2">
                  <span className="text-sm font-medium">Quality</span><QualityBadge label={quality.label} />
                  <span className="ml-auto text-xs tabular-nums text-mute">{quality.width}×{quality.height}</span>
                </div>
                <QualityMeters q={quality} />
                {quality.issues.length > 0 && <ul className="mt-3 list-disc space-y-1 pl-5 text-sm">{quality.issues.map((i) => <li key={i}>{i}</li>)}</ul>}
                {!quality.acceptable_for_analysis && <p className="mt-3 text-sm font-medium text-danger">This image is too poor for analysis. Please retake it.</p>}
                <div className="mt-4 grid grid-cols-2 gap-3">
                  <div className="col-span-2"><label className="label" htmlFor="up-date">Capture date</label>
                    <input id="up-date" type="date" max={today()} className="input" value={date} onChange={(e) => setDate(e.target.value)} /></div>
                  <div><label className="label" htmlFor="up-src">Image source</label>
                    <select id="up-src" className="input" value={source} onChange={(e) => setSource(e.target.value)}>{IMAGE_SOURCES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}</select></div>
                  <div><label className="label" htmlFor="up-loc">Body location</label>
                    <select id="up-loc" className="input" value={location} onChange={(e) => setLocation(e.target.value)}><option value="">Not specified</option>{LOCATIONS.map((l) => <option key={l}>{l}</option>)}</select></div>
                </div>
              </>
            )}
            <div className="mt-5 flex flex-wrap gap-2">
              <button className="btn-primary" disabled={!quality?.acceptable_for_analysis || busy !== null} onClick={upload}>{busy === "upload" ? "Uploading…" : "Confirm and upload"}</button>
              <button className="btn-ghost" onClick={() => setEditing(true)} disabled={busy !== null}>Crop / rotate</button>
              <button className="btn-ghost" onClick={reset} disabled={busy === "upload"}>Retake</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

