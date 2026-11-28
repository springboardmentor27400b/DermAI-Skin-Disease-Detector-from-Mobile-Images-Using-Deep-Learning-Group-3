import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { initials } from "../components/Layout";
import RoleFields, { profileFromUser, profilePayload } from "../components/RoleFields";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { ACCOUNT_LABEL } from "../lib/roles";
import type { Stats, User } from "../lib/types";

const Item = ({ label, children }: { label: string; children: ReactNode }) => (
  <div><dt className="text-xs text-mute">{label}</dt><dd className="mt-0.5 whitespace-pre-wrap text-sm">{children || <span className="text-mute">Not provided</span>}</dd></div>
);

function roleDetails(u: User): ReactNode {
  if (u.role === "patient") return <><Item label="Age">{u.age}</Item><Item label="Gender"><span className="capitalize">{u.gender}</span></Item><div className="sm:col-span-2"><Item label="Relevant medical history">{u.medical_history}</Item></div><div className="sm:col-span-2"><Item label="Known allergies">{u.known_allergies}</Item></div><div className="sm:col-span-2"><Item label="Research use">{u.research_consent ? "You share your de-identified cases with researchers and data scientists." : "Your cases are not shared for research."}</Item></div></>;
  if (u.role === "dermatologist") return <><Item label="Hospital / clinic">{u.institution}</Item><Item label="Specialisation">{u.specialization}</Item><Item label="Licence / registration no.">{u.license_number}</Item><Item label="Verification">{u.is_verified ? "Verified by an administrator" : "Awaiting administrator verification"}</Item></>;
  if (u.role === "researcher") return <><Item label="Institution">{u.institution}</Item><Item label="Research area">{u.research_area}</Item><Item label="ORCID iD">{u.orcid && <a className="text-accent underline" href={`https://orcid.org/${u.orcid}`} target="_blank" rel="noreferrer">{u.orcid}</a>}</Item></>;
  return <Item label="Institution">{u.institution}</Item>;
}

function ChangePassword() {
  const [f, setF] = useState({ current_password: "", new_password: "" });
  const [msg, setMsg] = useState<{ ok: boolean; t: string } | null>(null);
  async function submit(e: FormEvent) {
    e.preventDefault(); setMsg(null);
    try { await api("/auth/change-password", { json: f }); setF({ current_password: "", new_password: "" }); setMsg({ ok: true, t: "Password changed." }); }
    catch (err) { setMsg({ ok: false, t: err instanceof ApiError ? err.message : "Could not change the password." }); }
  }
  return (
    <details className="panel p-5">
      <summary className="cursor-pointer text-sm font-semibold">Change password</summary>
      <form onSubmit={submit} className="mt-4 grid gap-4 sm:grid-cols-2">
        <div><label className="label" htmlFor="cp">Current password</label><input id="cp" type="password" required autoComplete="current-password" className="input" value={f.current_password} onChange={(e) => setF({ ...f, current_password: e.target.value })} /></div>
        <div><label className="label" htmlFor="np">New password</label><input id="np" type="password" required minLength={8} autoComplete="new-password" className="input" value={f.new_password} onChange={(e) => setF({ ...f, new_password: e.target.value })} /></div>
        <div className="sm:col-span-2 flex items-center gap-3"><button className="btn-primary">Update password</button>{msg && <span role={msg.ok ? "status" : "alert"} className={`text-sm ${msg.ok ? "text-ok" : "text-danger"}`}>{msg.t}</span>}</div>
      </form>
    </details>
  );
}

export default function Profile() {
  const { user, refresh } = useAuth();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(user?.full_name ?? "");
  const [vals, setVals] = useState(user ? profileFromUser(user) : profileFromUser({} as User));
  const [stats, setStats] = useState<Stats | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { api<Stats>("/cases/stats").then(setStats).catch(() => {}); }, []);
  if (!user) return null;
  const hasFields = ["patient", "dermatologist", "researcher"].includes(user.role);
  const q = stats?.breakdowns.quality ?? {};

  function startEdit() { setName(user!.full_name); setVals(profileFromUser(user!)); setMsg(null); setEditing(true); }
  async function save(e: FormEvent) {
    e.preventDefault(); setBusy(true); setMsg(null);
    try {
      await api("/auth/me", { method: "PATCH", json: { full_name: name, ...profilePayload(user!.role, vals, true) } });
      await refresh(); setEditing(false); setMsg({ ok: true, text: "Profile saved." });
    } catch (err) { setMsg({ ok: false, text: err instanceof ApiError ? err.message : "Could not save." }); }
    finally { setBusy(false); }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <section className="panel flex flex-wrap items-center gap-5 p-6">
        <span className="flex h-20 w-20 shrink-0 items-center justify-center rounded-full bg-accent text-2xl font-semibold text-white" aria-hidden="true">{initials(user.full_name)}</span>
        <div className="min-w-0 flex-1">
          <h1 className="h-page truncate">{user.full_name}</h1>
          <p className="text-sm text-mute">{user.email}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            <span className="rounded-full bg-accent-soft px-3 py-0.5 text-xs font-semibold text-accent-dark">{ACCOUNT_LABEL[user.role]}</span>
            {user.role === "dermatologist" && <span className={`rounded-full px-3 py-0.5 text-xs font-semibold ${user.is_verified ? "bg-ok-soft text-ok" : "bg-amber-soft text-amber"}`}>{user.is_verified ? "Verified clinician" : "Awaiting verification"}</span>}
          </div>
        </div>
        {!editing && <button className="btn-ghost" onClick={startEdit}>Edit profile</button>}
      </section>

      {msg && <p role={msg.ok ? "status" : "alert"} className={`text-sm ${msg.ok ? "text-ok" : "text-danger"}`}>{msg.text}</p>}

      {editing ? (
        <form onSubmit={save} className="panel space-y-4 p-6">
          <div><label className="label" htmlFor="pn">Full name</label><input id="pn" required minLength={2} className="input" value={name} onChange={(e) => setName(e.target.value)} /></div>
          {hasFields && <RoleFields role={user.role} values={vals} onChange={setVals} id="pr" />}
          {user.role === "dermatologist" && <p className="hint">Changing your licence number requires administrator re-verification.</p>}
          <div className="flex gap-2"><button className="btn-primary" disabled={busy}>{busy ? "Saving…" : "Save changes"}</button><button type="button" className="btn-ghost" onClick={() => setEditing(false)}>Cancel</button></div>
        </form>
      ) : (
        <>
          <section className="panel p-6"><h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-mute">Account</h2>
            <dl className="grid gap-4 sm:grid-cols-2">
              <Item label="Full name">{user.full_name}</Item><Item label="Email">{user.email}</Item>
              <Item label="Account type">{ACCOUNT_LABEL[user.role]}</Item><Item label="Status">{user.is_active ? "Active" : "Inactive"}</Item>
              <Item label="Member since">{new Date(user.created_at).toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" })}</Item><Item label="User ID">{`USR-${String(user.id).padStart(4, "0")}`}</Item>
            </dl></section>
          <section className="panel p-6"><h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-mute">{user.role === "patient" ? "Health profile" : user.role === "dermatologist" ? "Professional details" : user.role === "researcher" ? "Research details" : "Details"}</h2>
            <dl className="grid gap-4 sm:grid-cols-2">{roleDetails(user)}</dl></section>
          <section className="panel p-6"><h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-mute">Activity</h2>
            <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              {[["Cases", stats?.total_cases], ["Images", stats?.total_images], ...(stats?.breakdowns.quality ? [["Good or acceptable", (q.good ?? 0) + (q.acceptable ?? 0)], ["Poor quality", q.poor ?? 0]] : [])].map(([l, v]) => <div key={l as string}><dt className="text-xs text-mute">{l}</dt><dd className="text-2xl font-semibold tabular-nums">{stats ? v : "–"}</dd></div>)}
            </dl></section>
        </>
      )}
      <ChangePassword />
    </div>
  );
}

