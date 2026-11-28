import { useEffect, useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { LOCATIONS } from "../lib/constants";
import { can } from "../lib/permissions";
import type { PatientBrief } from "../lib/types";

export default function NewCase() {
  const nav = useNavigate();
  const { user } = useAuth();
  const self = user?.role === "patient" ? user : null;   // patients: pre-fill from their own health profile
  const [f, setF] = useState({
    patient_age: self?.age?.toString() ?? "", patient_gender: self?.gender ?? "", body_location: "",
    medical_history: self?.medical_history ?? "", known_allergies: self?.known_allergies ?? "", clinical_notes: "",
  });
  const [patient, setPatient] = useState<PatientBrief | null>(null);
  const [q, setQ] = useState(""); const [found, setFound] = useState<PatientBrief[]>([]);
  const [error, setError] = useState<string | null>(null); const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  const onBehalf = can(user, "create_for_patient");
  const clinician = user?.role === "dermatologist";

  useEffect(() => {
    if (!onBehalf || patient) return;
    const t = setTimeout(() => { api<PatientBrief[]>(`/patients?q=${encodeURIComponent(q)}`).then(setFound).catch(() => setFound([])); }, 250);
    return () => clearTimeout(t);
  }, [q, onBehalf, patient]);

  if (!can(user, "create_case")) return <Navigate to="/cases" replace />;

  function choose(p: PatientBrief | null) {
    setPatient(p);
    setF((cur) => p
      ? { ...cur, patient_age: p.age?.toString() ?? "", patient_gender: p.gender ?? "", medical_history: p.medical_history ?? "", known_allergies: p.known_allergies ?? "" }
      : { ...cur, patient_age: "", patient_gender: "", medical_history: "", known_allergies: "" });
  }

  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError(null);
    const entries = Object.entries(f).filter(([k, v]) => v !== "" && (clinician || k !== "clinical_notes"));
    const body: Record<string, unknown> = Object.fromEntries(entries.map(([k, v]) => [k, k === "patient_age" ? Number(v) : v]));
    if (patient) body.patient_id = patient.id;
    try { const c = await api<{ id: number }>("/cases", { json: body }); nav(`/cases/${c.id}`); }
    catch (err) { setError(err instanceof ApiError ? err.message : "Could not create the case."); setBusy(false); }
  }

  return (
    <form onSubmit={submit} className="mx-auto max-w-2xl">
      <h1 className="h-page">New case</h1>
      <p className="mt-1 text-sm text-mute">Do not enter names, contact details or other identifying information beyond what is needed. Use de-identified data where possible.</p>

      {clinician && (
        <section className="panel mt-6 p-5" aria-label="Patient">
          <h2 className="text-sm font-semibold">Patient</h2>
          {!onBehalf ? <p className="mt-2 text-sm text-mute">Once an administrator verifies your account you can open cases on behalf of patients. For now this case will be your own.</p>
            : patient ? (
              <div className="mt-2 flex flex-wrap items-center gap-3 text-sm"><span><span className="font-medium">{patient.full_name}</span> <span className="text-mute">{patient.email}</span></span>
                <button type="button" className="text-accent underline" onClick={() => choose(null)}>Change</button></div>
            ) : (
              <div className="mt-2">
                <label className="label" htmlFor="pq">Search patients by name or email</label>
                <input id="pq" className="input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Leave empty for a case without a patient account" />
                {found.length > 0 && <ul className="mt-2 max-h-44 divide-y divide-line overflow-y-auto rounded border border-line">{found.map((p) => (
                  <li key={p.id}><button type="button" onClick={() => choose(p)} className="flex w-full justify-between px-3 py-2 text-left text-sm hover:bg-canvas"><span className="font-medium">{p.full_name}</span><span className="text-mute">{p.email}</span></button></li>))}</ul>}
                <p className="hint">Choose a patient to open the case in their record, or continue without one for a de-identified case of your own.</p>
              </div>
            )}
        </section>
      )}

      <div className="panel mt-6 space-y-4 p-6">
        <div className="grid gap-4 sm:grid-cols-3">
          <div><label className="label" htmlFor="age">Age</label><input id="age" type="number" min={0} max={120} className="input" value={f.patient_age} onChange={set("patient_age")} /></div>
          <div><label className="label" htmlFor="g">Gender</label>
            <select id="g" className="input" value={f.patient_gender} onChange={set("patient_gender")}><option value="">Not specified</option><option value="female">Female</option><option value="male">Male</option><option value="other">Other</option><option value="unknown">Unknown</option></select></div>
          <div><label className="label" htmlFor="loc">Body location</label>
            <select id="loc" className="input" value={f.body_location} onChange={set("body_location")}><option value="">Not specified</option>{LOCATIONS.map((l) => <option key={l}>{l}</option>)}</select></div>
        </div>
        <div><label className="label" htmlFor="mh">Relevant medical history</label><textarea id="mh" rows={3} className="input" value={f.medical_history} onChange={set("medical_history")} /></div>
        <div><label className="label" htmlFor="al">Known allergies</label><textarea id="al" rows={2} className="input" value={f.known_allergies} onChange={set("known_allergies")} /></div>
        {clinician && <div><label className="label" htmlFor="cn">Clinical notes</label><textarea id="cn" rows={3} className="input" value={f.clinical_notes} onChange={set("clinical_notes")} /></div>}
      </div>
      {error && <p role="alert" className="mt-4 rounded bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
      <div className="mt-6 flex gap-2"><button className="btn-primary" disabled={busy}>{busy ? "Creating…" : "Create case"}</button><button type="button" className="btn-ghost" onClick={() => nav(-1)}>Cancel</button></div>
    </form>
  );
}

