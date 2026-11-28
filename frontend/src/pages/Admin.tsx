import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "../lib/api";
import ModelManager from "../components/ModelManager";
import { ACCOUNT_LABEL } from "../lib/roles";
import type { AuditLog, Role, User } from "../lib/types";

const ROLES: Role[] = ["patient", "dermatologist", "researcher", "ml_engineer", "admin"];

export default function Admin() {
  const [users, setUsers] = useState<User[]>([]); const [logs, setLogs] = useState<AuditLog[]>([]);
  const [f, setF] = useState({ full_name: "", email: "", password: "", role: "ml_engineer" as Role });
  const [error, setError] = useState<string | null>(null);
  const load = () => { api<User[]>("/admin/users").then(setUsers); api<AuditLog[]>("/admin/audit-logs?limit=50").then(setLogs); };
  useEffect(load, []);
  const pending = users.filter((u) => u.role === "dermatologist" && !u.is_verified);

  async function create(e: FormEvent) {
    e.preventDefault(); setError(null);
    try { await api("/admin/users", { json: f }); setF({ ...f, full_name: "", email: "", password: "" }); load(); }
    catch (err) { setError(err instanceof ApiError ? err.message : "Failed"); }
  }
  async function toggle(u: User) { await api(`/admin/users/${u.id}/active?active=${!u.is_active}`, { method: "PATCH" }).catch((e) => setError(e.message)); load(); }
  async function verify(u: User, verified: boolean) { await api(`/admin/users/${u.id}/verify?verified=${verified}`, { method: "PATCH" }).catch((e) => setError(e.message)); load(); }

  return (
    <div className="space-y-10">
      <h1 className="h-page">Administration</h1>
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}

      <section>
        <h2 className="mb-3 text-lg font-semibold">Clinician verification {pending.length > 0 && <span className="ml-1 rounded bg-amber-soft px-2 py-0.5 text-sm text-amber">{pending.length} pending</span>}</h2>
        {pending.length === 0 ? <p className="text-sm text-mute">No clinicians are waiting for verification.</p> : (
          <ul className="panel divide-y divide-line">
            {pending.map((u) => (
              <li key={u.id} className="flex flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 text-sm">
                <span className="font-semibold">{u.full_name}</span><span className="text-mute">{u.email}</span>
                <span>{u.institution}</span><span>Licence <span className="font-mono">{u.license_number}</span></span>{u.specialization && <span className="text-mute">{u.specialization}</span>}
                <button className="btn-primary ml-auto py-1" onClick={() => verify(u, true)}>Verify</button>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-2 text-xs text-mute">Check the licence number against the relevant medical council register before verifying. Verified clinicians can review every user’s cases.</p>
      </section>

      <ModelManager />

      <section>
        <h2 className="mb-3 text-lg font-semibold">Create user</h2>
        <form onSubmit={create} className="panel grid gap-3 p-4 sm:grid-cols-5">
          <input aria-label="Full name" placeholder="Full name" required className="input" value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} />
          <input aria-label="Email" placeholder="Email" type="email" required className="input" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} />
          <input aria-label="Password" placeholder="Password" type="password" required minLength={8} className="input" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} />
          <select aria-label="Role" className="input" value={f.role} onChange={(e) => setF({ ...f, role: e.target.value as Role })}>{ROLES.map((r) => <option key={r} value={r}>{ACCOUNT_LABEL[r]}</option>)}</select>
          <button className="btn-primary">Create</button>
        </form>
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Users</h2>
        <div className="panel overflow-x-auto"><table className="w-full text-left text-sm"><tbody className="divide-y divide-line">
          {users.map((u) => <tr key={u.id}><td className="px-4 py-2 font-medium">{u.full_name}</td><td className="px-4 py-2">{u.email}</td><td className="px-4 py-2">{ACCOUNT_LABEL[u.role]}</td>
            <td className="px-4 py-2">{u.role === "dermatologist" ? (u.is_verified ? <button className="text-xs text-mute underline" onClick={() => verify(u, false)}>Verified · revoke</button> : <span className="text-amber">Unverified</span>) : ""}</td>
            <td className="px-4 py-2 text-right"><button className="btn-ghost py-1" onClick={() => toggle(u)}>{u.is_active ? "Deactivate" : "Activate"}</button></td></tr>)}
        </tbody></table></div>
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Audit log</h2>
        <div className="panel overflow-x-auto"><table className="w-full text-left text-sm"><tbody className="divide-y divide-line">
          {logs.map((l) => <tr key={l.id}><td className="px-4 py-1.5 tabular-nums text-mute">{new Date(l.created_at).toLocaleString()}</td><td className="px-4 py-1.5 font-medium">{l.action}</td><td className="px-4 py-1.5 text-mute">{l.resource ?? ""}</td><td className="px-4 py-1.5 text-mute">{l.detail ?? ""}</td></tr>)}
        </tbody></table></div>
      </section>
    </div>
  );
}

