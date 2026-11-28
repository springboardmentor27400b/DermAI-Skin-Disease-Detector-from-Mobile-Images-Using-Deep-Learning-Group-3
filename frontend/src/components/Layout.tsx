import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { can } from "../lib/permissions";
import { ACCOUNT_LABEL, themeForRole } from "../lib/roles";
import { useTheme } from "../lib/theme";
import Disclaimer from "./Disclaimer";
import Icon, { Logo } from "./Icon";
import Notifications from "./Notifications";

export const initials = (name: string) => name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join("");

function crumb(path: string): string {
  if (path === "/cases/new") return "New case";
  if (path.startsWith("/cases/")) return "Case";
  if (path.startsWith("/analysis/")) return "Analysis";
  return ({ "/dashboard": "Dashboard", "/cases": "Cases", "/history": "History", "/profile": "Profile", "/admin": "Administration" } as Record<string, string>)[path] ?? "";
}

function NotificationMenu() {
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => { setOpen(false); }, [pathname]);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    const onClick = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClick);
    return () => {
      window.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClick);
    };
  }, [open]);

  return (
    <div ref={boxRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-label="Notifications"
        className="flex items-center gap-2 rounded-full bg-accent-soft px-3 py-1.5 text-xs font-semibold text-accent-dark transition-colors hover:bg-accent hover:text-white"
      >
        <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 0 1-3.46 0" />
        </svg>
        <span>Notifications</span>
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="Notifications"
          className="fixed inset-x-3 top-14 z-50 max-h-[75vh] overflow-y-auto rounded-xl border border-line bg-white p-4 shadow-xl md:absolute md:inset-x-auto md:right-0 md:top-full md:mt-2 md:w-[34rem]"
        >
          <Notifications />
        </div>
      )}
    </div>
  );
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { user, logout } = useAuth();
  const { pathname } = useLocation();
  if (!user) return null;
  const casesLabel = { patient: "My cases", dermatologist: user.is_verified ? "All cases" : "My cases", researcher: "Shared cases", ml_engineer: "Case data", admin: "Case audit" }[user.role];
  const items = [
    { to: "/dashboard", label: "Dashboard", icon: "dashboard", active: pathname === "/dashboard" },
    { to: "/cases", label: casesLabel, icon: "cases", active: pathname.startsWith("/cases") && pathname !== "/cases/new" },
    ...(can(user, "create_case") ? [{ to: "/cases/new", label: "New case", icon: "plus", active: pathname === "/cases/new" }] : []),
    { to: "/history", label: "History", icon: "history", active: pathname === "/history" },
    { to: "/profile", label: "Profile", icon: "user", active: pathname === "/profile" },
    ...(can(user, "manage_users") ? [{ to: "/admin", label: "Administration", icon: "shield", active: pathname === "/admin" }] : []),
  ];
  const row = (active: boolean) =>
    `group flex items-center gap-3 rounded px-3 py-2 text-sm font-medium transition-colors ${active ? "bg-accent-soft text-accent-dark" : "text-ink hover:bg-canvas hover:text-accent-dark"}`;

  return (
    <div className="flex h-full flex-col">
      <Link to="/" onClick={onNavigate} className="flex items-center gap-3 px-5 py-5">
        <Logo />
        <span className="leading-tight"><span className="block font-bold tracking-tight">DermAI</span><span className="block text-xs text-mute">Image workspace</span></span>
      </Link>
      <nav aria-label="Workspace" className="flex-1 overflow-y-auto px-3">
        <p className="px-3 pb-2 pt-3 text-[11px] font-semibold uppercase tracking-widest text-mute">Workspace</p>
        <ul className="space-y-1">
          {items.map((i) => (
            <li key={i.to}><NavLink to={i.to} onClick={onNavigate} aria-current={i.active ? "page" : undefined} className={row(i.active)}><Icon name={i.icon} className="transition-transform group-hover:scale-110" />{i.label}</NavLink></li>
          ))}
        </ul>
        <p className="px-3 pb-2 pt-6 text-[11px] font-semibold uppercase tracking-widest text-mute">Site</p>
        <Link to="/" onClick={onNavigate} className={row(false)}><Icon name="home" className="transition-transform group-hover:scale-110" />Home page</Link>
      </nav>
      <div className="border-t border-line p-3">
        <Link to="/profile" onClick={onNavigate} className="flex items-center gap-3 rounded px-2 py-2 hover:bg-canvas">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent text-sm font-semibold text-white" aria-hidden="true">{initials(user.full_name)}</span>
          <span className="min-w-0 leading-tight"><span className="block truncate text-sm font-medium">{user.full_name}</span><span className="block truncate text-xs text-mute">{ACCOUNT_LABEL[user.role]}</span></span>
        </Link>
        <button onClick={logout} className="mt-1 flex w-full items-center gap-3 rounded px-3 py-2 text-sm text-mute hover:bg-canvas hover:text-ink"><Icon name="logout" />Sign out</button>
      </div>
    </div>
  );
}

export default function Layout() {
  const { user } = useAuth();
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  useTheme(themeForRole(user?.role));

  useEffect(() => { setOpen(false); }, [pathname]);
  useEffect(() => {
    if (!open) return;
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [open]);

  const showNotifications = Boolean(user && user.role !== "researcher" && user.role !== "ml_engineer");

  return (
    <div className="min-h-screen md:flex">
      <aside className="hidden w-64 shrink-0 border-r border-line bg-white md:sticky md:top-0 md:block md:h-screen"><SidebarContent /></aside>

      <div className="sticky top-0 z-30 flex items-center gap-3 border-b border-line bg-white px-4 py-3 md:hidden">
        <button onClick={() => setOpen(true)} aria-label="Open menu" aria-expanded={open} className="rounded p-1.5 hover:bg-canvas"><Icon name="menu" /></button>
        <span className="font-bold tracking-tight text-accent">DermAI</span>
        <span className="ml-auto text-sm text-mute">{crumb(pathname)}</span>
        {showNotifications && <NotificationMenu />}
      </div>
      {open && (
        <div className="fixed inset-0 z-40 md:hidden" role="dialog" aria-modal="true" aria-label="Menu">
          <button className="absolute inset-0 bg-ink/40" aria-label="Close menu" onClick={() => setOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-72 max-w-[85%] bg-white shadow-xl">
            <button onClick={() => setOpen(false)} aria-label="Close menu" className="absolute right-3 top-4 rounded p-1.5 hover:bg-canvas"><Icon name="close" /></button>
            <SidebarContent onNavigate={() => setOpen(false)} />
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="relative z-30 hidden items-center justify-between border-b border-line bg-white/70 px-8 py-3 text-sm md:flex">
          <p className="text-mute">DermAI <span aria-hidden="true">/</span> <span className="font-medium text-ink">{crumb(pathname)}</span></p>
          {showNotifications ? (
            <NotificationMenu />
          ) : (
            user && <span className="rounded-full bg-accent-soft px-3 py-1 text-xs font-semibold text-accent-dark">{ACCOUNT_LABEL[user.role]}</span>
          )}
        </div>
        {user?.role === "dermatologist" && !user.is_verified && (
          <div role="status" className="border-b border-amber/30 bg-amber-soft px-4 py-2 text-center text-sm text-amber">
            Your clinician account is awaiting administrator verification. Until then you can only see your own cases.
          </div>
        )}
        <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 md:px-8"><Outlet /></main>
        <footer className="border-t border-line bg-white"><div className="mx-auto max-w-5xl px-4 py-4 md:px-8"><Disclaimer /></div></footer>
      </div>
    </div>
  );
}