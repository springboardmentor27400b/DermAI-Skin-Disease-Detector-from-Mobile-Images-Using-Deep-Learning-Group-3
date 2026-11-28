import { useState, type FormEvent } from "react";
import { api, ApiError } from "../lib/api";
import { ACCOUNT_LABEL } from "../lib/roles";
import type { Note, User } from "../lib/types";

export default function Notes({ caseId, notes, initial, user, onAdded }: { caseId: number; notes: Note[]; initial: string | null; user: User; onAdded: () => void }) {
  const [text, setText] = useState(""); const [busy, setBusy] = useState(false); const [error, setError] = useState<string | null>(null);
  const clinician = user.role === "dermatologist" || user.role === "admin";

  async function add(e: FormEvent) {
    e.preventDefault(); if (!text.trim()) return;
    setBusy(true); setError(null);
    try { await api(`/cases/${caseId}/notes`, { json: { text } }); setText(""); onAdded(); }
    catch (err) { setError(err instanceof ApiError ? err.message : "Could not add the note."); }
    finally { setBusy(false); }
  }

  return (
    <section aria-labelledby="notes-h">
      <h2 id="notes-h" className="mb-3 text-lg font-semibold">{clinician ? "Clinical notes" : "Notes"}</h2>
      <ol className="space-y-3">
        {initial && <li className="panel p-4"><p className="text-xs text-mute">Entered when the case was created</p><p className="mt-1 whitespace-pre-wrap text-sm">{initial}</p></li>}
        {notes.map((n) => (
          <li key={n.id} className="panel p-4">
            <p className="text-xs text-mute"><span className="font-semibold text-ink">{n.author_name}</span> · {ACCOUNT_LABEL[n.author_role]} · {new Date(n.created_at).toLocaleString()}</p>
            <p className="mt-1 whitespace-pre-wrap text-sm">{n.text}</p>
          </li>
        ))}
        {!initial && notes.length === 0 && <li className="text-sm text-mute">No notes yet.</li>}
      </ol>
      <form onSubmit={add} className="mt-4">
        <label className="label" htmlFor="new-note">{clinician ? "Add a clinical note" : "Add a note"}</label>
        <textarea id="new-note" rows={3} className="input" value={text} onChange={(e) => setText(e.target.value)} />
        {error && <p role="alert" className="mt-2 text-sm text-danger">{error}</p>}
        <button className="btn-primary mt-2" disabled={busy || !text.trim()}>{busy ? "Adding…" : "Add note"}</button>
      </form>
    </section>
  );
}

