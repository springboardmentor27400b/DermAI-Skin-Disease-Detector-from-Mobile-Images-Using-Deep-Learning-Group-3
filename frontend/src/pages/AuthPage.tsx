import { useRef, useState, type FormEvent, type KeyboardEvent, type TouchEvent } from "react";
import { Navigate, useSearchParams } from "react-router-dom";
import Disclaimer from "../components/Disclaimer";
import RoleFields, { emptyProfile, profilePayload } from "../components/RoleFields";
import { ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { ACCOUNT_LABEL, ROLE_DEFS } from "../lib/roles";
import { useTheme } from "../lib/theme";
import type { User } from "../lib/types";

type Mode = "login" | "signup";
const SWIPE_PX = 60;

export default function AuthPage() {
  const { user, login, register } = useAuth();
  const [params] = useSearchParams();
  const [idx, setIdx] = useState(Math.max(0, ROLE_DEFS.findIndex((r) => r.key === params.get("role"))));
  const [staff, setStaff] = useState(params.get("role") === "staff");
  const [mode, setMode] = useState<Mode>(params.get("mode") === "signup" ? "signup" : "login");
  const [f, setF] = useState({ full_name: "", email: "", password: "", ...emptyProfile });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const touchX = useRef<number | null>(null);

  const role = ROLE_DEFS[idx];
  useTheme(staff ? "clinician" : role.theme);
  if (user) return <Navigate to="/dashboard" replace />;

  const select = (i: number) => { setIdx((i + ROLE_DEFS.length) % ROLE_DEFS.length); setStaff(false); setError(null); };
  const switchMode = (m: Mode) => { setMode(m); setError(null); };

  function onTouchStart(e: TouchEvent) {
    touchX.current = (e.target as HTMLElement).closest("input,textarea,select,button,a") ? null : e.touches[0].clientX;
  }
  function onTouchEnd(e: TouchEvent) {
    if (touchX.current === null) return;
    const dx = e.changedTouches[0].clientX - touchX.current;
    touchX.current = null;
    if (dx > SWIPE_PX) select(idx - 1);
    else if (dx < -SWIPE_PX) select(idx + 1);
  }
  function onTabKey(e: KeyboardEvent) {
    if (e.key === "ArrowRight") { e.preventDefault(); select(idx + 1); }
    if (e.key === "ArrowLeft") { e.preventDefault(); select(idx - 1); }
  }

  // Convenience check so people use the right entry; real access control is enforced by the API.
  const guard = (u: User): string | null => {
    const ok = staff ? u.role === "admin" || u.role === "ml_engineer" : u.role === role.key;
    return ok ? null : `This account is registered as ${ACCOUNT_LABEL[u.role]}. ${u.role === "admin" || u.role === "ml_engineer" ? "Use “Staff sign in” below." : "Swipe or use the arrows to that role and sign in there."}`;
  };

  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError(null);
    try {
      if (mode === "login" || staff) await login(f.email, f.password, guard);
      else await register({ full_name: f.full_name, email: f.email, password: f.password, role: role.key, ...profilePayload(role.key, f) });
    } catch (err) { setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again."); }
    finally { setBusy(false); }
  }

  const heading = staff ? "Staff sign in" : mode === "login" ? `Sign in as ${/^[aeiou]/i.test(role.noun) ? "an" : "a"} ${role.noun}` : `Create your ${role.noun} account`;

  return (
    <div className="grid min-h-screen grid-cols-[minmax(0,1fr)] md:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]" onTouchStart={onTouchStart} onTouchEnd={onTouchEnd}>
      {/* Hero / role carousel */}
      <section className="flex flex-col bg-hero p-6 text-hero-fg transition-colors duration-500 md:sticky md:top-0 md:h-screen md:p-12" aria-label="Choose your role">
        <span className="text-xl font-bold tracking-tight">DermAI</span>

        <div className="my-8 flex-1 overflow-hidden md:my-12">
          {staff ? (
            <div>
              <h1 className="text-3xl font-semibold leading-tight tracking-tight md:text-4xl">Administration and model evaluation.</h1>
              <p className="mt-4 max-w-md text-hero-mute">Sign in with the account your administrator created for you.</p>
            </div>
          ) : (
            <div className="flex h-full transition-transform duration-500 ease-out" style={{ transform: `translateX(-${idx * 100}%)` }}>
              {ROLE_DEFS.map((r, i) => (
                <div key={r.key} className="w-full shrink-0 pr-4" aria-hidden={i !== idx}>
                  <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-hero-mute">{r.label}</p>
                  <h1 className="text-3xl font-semibold leading-tight tracking-tight md:text-4xl">{r.headline}</h1>
                  <p className="mt-4 max-w-md text-hero-mute">{r.blurb}</p>
                  <ul className="mt-6 hidden max-w-md space-y-2 text-sm sm:block">
                    {r.points.map((p) => <li key={p} className="flex gap-2"><span aria-hidden="true" className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-current opacity-60" />{p}</li>)}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </div>

        <div>
          {!staff && (
            <div className="flex items-center gap-2">
              <button type="button" onClick={() => select(idx - 1)} aria-label="Previous role" className="flex h-10 w-10 items-center justify-center rounded-full border border-hero-fg/30 transition duration-150 hover:scale-105 hover:bg-hero-fg/10 active:scale-95 md:h-11 md:w-11">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M15 6l-6 6 6 6" /></svg>
              </button>
              <div role="tablist" aria-label="Role" className="flex flex-1 gap-1 rounded-full border border-hero-fg/30 p-1" onKeyDown={onTabKey}>
                {ROLE_DEFS.map((r, i) => (
                  <button key={r.key} role="tab" type="button" aria-selected={i === idx} tabIndex={i === idx ? 0 : -1} onClick={() => select(i)}
                    className={`flex-1 rounded-full px-2 py-1.5 text-xs font-semibold transition-colors sm:text-sm ${i === idx ? "bg-accent text-white" : "hover:bg-hero-fg/10"}`}>{r.short}</button>
                ))}
              </div>
              <button type="button" onClick={() => select(idx + 1)} aria-label="Next role" className="flex h-10 w-10 items-center justify-center rounded-full border border-hero-fg/30 transition duration-150 hover:scale-105 hover:bg-hero-fg/10 active:scale-95 md:h-11 md:w-11">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M9 6l6 6-6 6" /></svg>
              </button>
            </div>
          )}
          <p className="mt-4 text-xs text-hero-mute">Screening and research support only. Not a standalone medical diagnosis.</p>
        </div>
      </section>

      {/* Form */}
      <section className="flex justify-center bg-canvas px-6 py-10 transition-colors duration-500 md:items-center md:px-12">
        <form onSubmit={submit} className="w-full max-w-md" aria-live="polite">
          {!staff && (
            <div role="tablist" aria-label="Sign in or create account" className="mb-6 grid grid-cols-2 border-b border-line">
              {(["login", "signup"] as Mode[]).map((m) => (
                <button key={m} type="button" role="tab" aria-selected={mode === m} onClick={() => switchMode(m)}
                  className={`-mb-px border-b-2 px-2 py-2.5 text-sm font-semibold ${mode === m ? "border-accent text-accent" : "border-transparent text-mute hover:text-ink"}`}>
                  {m === "login" ? "Sign in" : "Create account"}
                </button>
              ))}
            </div>
          )}
          <h2 className="text-2xl font-semibold tracking-tight">{heading}</h2>

          <div className="mt-6 space-y-4">
            {mode === "signup" && !staff && (
              <div><label className="label" htmlFor="full_name">Full name</label>
                <input id="full_name" required minLength={2} autoComplete="name" className="input" value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} /></div>
            )}
            <div><label className="label" htmlFor="email">Email</label>
              <input id="email" type="email" required autoComplete="username" className="input" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></div>
            <div><label className="label" htmlFor="password">Password</label>
              <input id="password" type="password" required minLength={mode === "signup" ? 8 : undefined} autoComplete={mode === "signup" ? "new-password" : "current-password"} className="input" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} />
              {mode === "signup" && !staff && <p className="hint">At least 8 characters with upper and lower case letters and a digit.</p>}</div>
            {mode === "signup" && !staff && <RoleFields role={role.key} values={f} onChange={(v) => setF({ ...f, ...v })} id={`su-${role.key}`} />}
          </div>

          {mode === "signup" && role.key === "dermatologist" && !staff && (
            <p className="mt-4 rounded border border-line bg-accent-soft px-3 py-2 text-sm">An administrator verifies clinician accounts. Until then you can use DermAI with your own cases, and you will see other users’ cases once verified.</p>
          )}
          {error && <p role="alert" className="mt-4 rounded bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
          <button className="btn-primary mt-6 w-full" disabled={busy}>{busy ? "Please wait…" : mode === "login" || staff ? "Sign in" : "Create account"}</button>

          <p className="mt-5 text-sm text-mute">
            {staff
              ? <button type="button" className="font-semibold text-accent underline" onClick={() => { setStaff(false); setError(null); }}>Back to role selection</button>
              : <>Administrator or data scientist? <button type="button" className="font-semibold text-accent underline" onClick={() => { setStaff(true); setMode("login"); setError(null); }}>Staff sign in</button></>}
          </p>
          <Disclaimer className="mt-8" />
        </form>
      </section>
    </div>
  );
}

