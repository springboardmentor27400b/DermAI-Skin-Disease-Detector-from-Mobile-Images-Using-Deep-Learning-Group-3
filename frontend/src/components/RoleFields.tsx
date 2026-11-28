import type { Role, User } from "../lib/types";

export interface ProfileValues {
  age: string; gender: string; medical_history: string; known_allergies: string;
  institution: string; license_number: string; specialization: string; research_area: string; orcid: string;
  research_consent: boolean;
}
export const emptyProfile: ProfileValues = {
  age: "", gender: "", medical_history: "", known_allergies: "",
  institution: "", license_number: "", specialization: "", research_area: "", orcid: "", research_consent: false,
};
export const profileFromUser = (u: User): ProfileValues => ({
  age: u.age?.toString() ?? "", gender: u.gender ?? "", medical_history: u.medical_history ?? "", known_allergies: u.known_allergies ?? "",
  institution: u.institution ?? "", license_number: u.license_number ?? "", specialization: u.specialization ?? "",
  research_area: u.research_area ?? "", orcid: u.orcid ?? "", research_consent: !!u.research_consent,
});

const FIELDS: Record<string, (keyof ProfileValues)[]> = {
  patient: ["age", "gender", "medical_history", "known_allergies", "research_consent"],
  dermatologist: ["institution", "license_number", "specialization"],
  researcher: ["institution", "research_area", "orcid"],
};

/** Only the fields that belong to the role, empty ones left out, age as a number. */
export function profilePayload(role: Role, v: ProfileValues, keepEmpty = false): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const k of FIELDS[role] ?? []) {
    if (k === "research_consent") { out[k] = v.research_consent; continue; }
    const val = (v[k] as string).trim();
    if (!val && !keepEmpty) continue;
    out[k] = k === "age" ? (val ? Number(val) : null) : val || null;
  }
  return out;
}

const SPECIALIZATIONS = ["Dermatology", "Dermatopathology", "Dermatologic surgery", "Pediatric dermatology", "Oncology", "General practice"];

interface Props { role: Role; values: ProfileValues; onChange: (v: ProfileValues) => void; id?: string }

export default function RoleFields({ role, values, onChange, id = "pf" }: Props) {
  const set = (k: keyof ProfileValues) => (e: { target: { value: string } }) => onChange({ ...values, [k]: e.target.value });
  const i = (k: string) => `${id}-${k}`;

  if (role === "patient")
    return (
      <>
        <div className="grid gap-4 sm:grid-cols-2">
          <div><label className="label" htmlFor={i("age")}>Age</label>
            <input id={i("age")} type="number" min={0} max={120} className="input" value={values.age} onChange={set("age")} /></div>
          <div><label className="label" htmlFor={i("gender")}>Gender</label>
            <select id={i("gender")} className="input" value={values.gender} onChange={set("gender")}>
              <option value="">Prefer not to say</option><option value="female">Female</option><option value="male">Male</option><option value="other">Other</option>
            </select></div>
        </div>
        <div><label className="label" htmlFor={i("mh")}>Relevant medical history <span className="font-normal text-mute">(optional)</span></label>
          <textarea id={i("mh")} rows={2} className="input" value={values.medical_history} onChange={set("medical_history")} placeholder="e.g. eczema, previous skin cancer" /></div>
        <div><label className="label" htmlFor={i("al")}>Known allergies <span className="font-normal text-mute">(optional)</span></label>
          <textarea id={i("al")} rows={2} className="input" value={values.known_allergies} onChange={set("known_allergies")} placeholder="e.g. latex, penicillin" />
          <p className="hint">These pre-fill your new cases. Do not include your address, phone number or other identifying details.</p></div>
        <label className="flex items-start gap-3 rounded border border-line bg-accent-soft/50 p-3 text-sm">
          <input type="checkbox" className="mt-1" checked={values.research_consent} onChange={(e) => onChange({ ...values, research_consent: e.target.checked })} />
          <span><span className="font-medium">Share my de-identified cases for research</span>
            <span className="hint block">Optional. Researchers and data scientists would see your photos and results without your name, age, history or notes. You can change this at any time.</span></span>
        </label>
      </>
    );

  if (role === "dermatologist")
    return (
      <>
        <div><label className="label" htmlFor={i("inst")}>Hospital / clinic</label>
          <input id={i("inst")} required className="input" value={values.institution} onChange={set("institution")} /></div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div><label className="label" htmlFor={i("lic")}>Licence / registration no.</label>
            <input id={i("lic")} required className="input" value={values.license_number} onChange={set("license_number")} /></div>
          <div><label className="label" htmlFor={i("spec")}>Specialisation</label>
            <input id={i("spec")} list={i("spec-list")} className="input" value={values.specialization} onChange={set("specialization")} />
            <datalist id={i("spec-list")}>{SPECIALIZATIONS.map((s) => <option key={s} value={s} />)}</datalist></div>
        </div>
      </>
    );

  return (
    <>
      <div><label className="label" htmlFor={i("inst")}>Institution</label>
        <input id={i("inst")} required className="input" value={values.institution} onChange={set("institution")} /></div>
      <div><label className="label" htmlFor={i("area")}>Research area <span className="font-normal text-mute">(optional)</span></label>
        <input id={i("area")} className="input" value={values.research_area} onChange={set("research_area")} placeholder="e.g. melanoma detection, skin-tone fairness" /></div>
      <div><label className="label" htmlFor={i("orcid")}>ORCID iD <span className="font-normal text-mute">(optional)</span></label>
        <input id={i("orcid")} className="input" pattern="\d{4}-\d{4}-\d{4}-\d{3}[\dX]" title="Format: 0000-0002-1825-0097" placeholder="0000-0000-0000-0000" value={values.orcid} onChange={set("orcid")} /></div>
    </>
  );
}

