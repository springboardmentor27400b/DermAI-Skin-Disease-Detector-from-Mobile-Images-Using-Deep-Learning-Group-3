import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import AuthedImage from "../components/AuthedImage";
import Compare from "../components/Compare";
import { QualityBadge } from "../components/QualityMeters";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { describePrediction, imageCode } from "../lib/constants";
import { can, canViewFiles, showCase, showImage } from "../lib/permissions";
import type { HistoryItem } from "../lib/types";

export default function History() {
  const { user } = useAuth();
  const [items, setItems] = useState<HistoryItem[] | null>(null);
  const [flt, setFlt] = useState({ date_from: "", date_to: "", analysis_status: "", quality: "", image_source: "", model_version: "" });
  const [sel, setSel] = useState<number[]>([]);
  const [comparing, setComparing] = useState(false);

  useEffect(() => {
    const qs = new URLSearchParams(Object.entries(flt).filter(([, v]) => v));
    setItems(null);
    api<HistoryItem[]>(`/images/history?${qs}`).then(setItems);
  }, [flt]);
  if (!user) return null;

  const see = (f: string) => showImage(user, f);
  const files = canViewFiles(user);
  const compare = can(user, "compare");
  const chosen = (items ?? []).filter((i) => sel.includes(i.id));
  const toggle = (id: number) => { setComparing(false); setSel((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id].slice(-2))); };
  const set = (k: keyof typeof flt) => (e: { target: { value: string } }) => setFlt({ ...flt, [k]: e.target.value });

  const cols: { h: string; cell: (i: HistoryItem) => React.ReactNode }[] = [
    ...(files ? [{ h: "Image", cell: (i: HistoryItem) => <AuthedImage id={i.id} variant="original" alt="" className="h-12 w-12 rounded border border-line" /> }] : []),
    ...(see("image_id") ? [{ h: "Image ID", cell: (i: HistoryItem) => <span className="tabular-nums">{imageCode(i.id)}</span> }] : []),
    { h: "Case ID", cell: (i) => <Link className="font-semibold text-accent underline" to={`/cases/${i.case_id}`}>{i.case_code}</Link> },
    ...(showCase(user, "owner_name") ? [{ h: "Patient", cell: (i: HistoryItem) => i.owner_name ?? "—" }] : []),
    ...(see("capture_date") ? [{ h: "Captured", cell: (i: HistoryItem) => <span className="tabular-nums">{i.capture_date ?? "—"}</span> }] : [{ h: "Recorded", cell: (i: HistoryItem) => <span className="tabular-nums">{i.created_at ? new Date(i.created_at).toLocaleDateString() : "—"}</span> }]),
    ...(see("body_location") ? [{ h: "Location", cell: (i: HistoryItem) => i.body_location ?? "—" }] : []),
    ...(see("image_source") ? [{ h: "Source", cell: (i: HistoryItem) => <span className="capitalize">{i.image_source}</span> }] : []),
    ...(see("quality_label") ? [{ h: "Quality", cell: (i: HistoryItem) => <QualityBadge label={i.quality_label} /> }] : []),
    { h: "Status", cell: (i) => <span className="capitalize">{i.analysis_status?.replace("_", " ")}</span> },
    ...(see("model_version") ? [{ h: "Model", cell: (i: HistoryItem) => i.model_version ?? "—" }] : []),
    ...(see("prediction_result") ? [{ h: "Prediction", cell: (i: HistoryItem) => describePrediction(i.prediction_result) }] : []),
    ...(see("prediction_result") && files ? [{ h: "Analysis", cell: (i: HistoryItem) => <Link className="font-semibold text-accent underline" to={`/analysis/${i.id}`}>Open</Link> }] : []),
  ];

  return (
    <div className="space-y-6">
      <div><h1 className="h-page">Prediction history</h1>
        <p className="text-sm text-mute">{user.role === "admin" ? "Operational record of analyses for auditing and support." : compare ? "Every analysis you can access, newest first. Tick two to compare, even across cases." : "Every analysis you can access, newest first."}</p></div>

      <div className="panel grid gap-3 p-4 sm:grid-cols-3 lg:grid-cols-6">
        {see("capture_date") && <><div><label className="label" htmlFor="hf">Captured from</label><input id="hf" type="date" className="input" value={flt.date_from} onChange={set("date_from")} /></div>
          <div><label className="label" htmlFor="ht">Captured to</label><input id="ht" type="date" className="input" value={flt.date_to} onChange={set("date_to")} /></div></>}
        <div><label className="label" htmlFor="hs">Status</label>
          <select id="hs" className="input" value={flt.analysis_status} onChange={set("analysis_status")}><option value="">All</option><option value="pending">Pending</option><option value="rejected_quality">Rejected (quality)</option><option value="completed">Completed</option><option value="failed">Failed</option></select></div>
        {see("quality_label") && <div><label className="label" htmlFor="hq">Quality</label>
          <select id="hq" className="input" value={flt.quality} onChange={set("quality")}><option value="">All</option><option value="good">Good</option><option value="acceptable">Acceptable</option><option value="poor">Poor</option></select></div>}
        {see("image_source") && <div><label className="label" htmlFor="hsrc">Source</label>
          <select id="hsrc" className="input" value={flt.image_source} onChange={set("image_source")}><option value="">All</option><option value="camera">Camera</option><option value="gallery">Gallery</option><option value="dataset">Dataset</option></select></div>}
        {see("model_version") && <div><label className="label" htmlFor="hmv">Model version</label><input id="hmv" className="input" placeholder="e.g. v1.0" value={flt.model_version} onChange={set("model_version")} /></div>}
      </div>

      {compare && <div className="flex items-center gap-3 text-sm">
        <span className="text-mute">{sel.length < 2 ? `Selected ${sel.length}/2` : "Two images selected"}</span>
        <button className="btn-primary py-1" disabled={sel.length !== 2} onClick={() => setComparing(true)}>Compare</button>
      </div>}
      {comparing && chosen.length === 2 && <Compare items={[chosen[0], chosen[1]]} onClose={() => setComparing(false)} />}

      {items === null ? <p className="text-mute">Loading…</p> : items.length === 0 ? <div className="panel p-8 text-center text-mute">No analyses match.</div> : (
        <div className="panel overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-line text-mute"><tr>
              {compare && <th className="px-3 py-2"><span className="sr-only">Select</span></th>}
              {cols.map((c) => <th key={c.h} className="px-3 py-2 font-medium">{c.h}</th>)}
            </tr></thead>
            <tbody className="divide-y divide-line">
              {items.map((i) => (
                <tr key={i.id} className="hover:bg-canvas">
                  {compare && <td className="px-3 py-2"><input type="checkbox" aria-label={`Select analysis ${i.case_code} #${i.id}`} checked={sel.includes(i.id)} onChange={() => toggle(i.id)} /></td>}
                  {cols.map((c) => <td key={c.h} className="px-3 py-2">{c.cell(i)}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

