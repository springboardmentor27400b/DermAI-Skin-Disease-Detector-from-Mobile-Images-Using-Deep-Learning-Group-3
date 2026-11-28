import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import type { Notice } from "../lib/types";

const TONE: Record<Notice["level"], string> = {
  informational: "bg-canvas text-mute", low: "bg-accent-soft text-accent-dark", medium: "bg-amber-soft text-amber", high: "bg-danger-soft text-danger",
};

/** Alerts derived from analyses the signed-in user can see. No "critical" level: an AI prediction is not a confirmed diagnosis.
 *  Read state is stored per user, so opening an alert (or "Mark all as read") clears it. */
export default function Notifications({ limit = 6 }: { limit?: number }) {
  const [items, setItems] = useState<Notice[] | null>(null);
  const [all, setAll] = useState(false);
  useEffect(() => { api<Notice[]>("/notifications").then(setItems).catch(() => setItems([])); }, []);
  if (items === null || items.length === 0) return null;

  const unread = items.filter((n) => !n.read).length;
  const shown = all ? items : items.slice(0, limit);
  function markRead(keys: string[]) {
    if (!keys.length) return;
    setItems((cur) => cur && cur.map((n) => (keys.includes(n.key) ? { ...n, read: true } : n)));
    api("/notifications/read", { json: { keys } }).catch(() => {});      // best effort: the list refreshes next visit anyway
  }

  return (
    <section aria-labelledby="notif-h">
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <h2 id="notif-h" className="text-lg font-semibold">Notifications <span className="text-sm font-normal text-mute">({unread} unread of {items.length})</span></h2>
        {unread > 0 && <button className="text-sm font-semibold text-accent underline" onClick={() => markRead(items.filter((n) => !n.read).map((n) => n.key))}>Mark all as read</button>}
      </div>
      <ul className="panel divide-y divide-line">
        {shown.map((n) => (
          <li key={n.key} className={`flex flex-wrap items-start gap-3 px-4 py-3 text-sm ${n.read ? "opacity-70" : ""}`}>
            <span className={`mt-0.5 rounded px-2 py-0.5 text-xs font-semibold capitalize ${TONE[n.level]}`}>{n.level}</span>
            <div className="min-w-0 flex-1">
              <p className={n.read ? "font-normal" : "font-semibold"}>{!n.read && <span className="mr-2 inline-block h-2 w-2 rounded-full bg-accent align-middle" aria-label="Unread" />}{n.title} <span className="font-normal text-mute">· {n.case_code}</span></p>
              <p className="text-mute">{n.message}</p>
            </div>
            <span className="flex items-center gap-3 text-xs">
              {n.created_at && <span className="tabular-nums text-mute">{new Date(n.created_at).toLocaleDateString()}</span>}
              <Link className="font-semibold text-accent underline" onClick={() => markRead([n.key])} to={n.image_id && n.level !== "medium" ? `/analysis/${n.image_id}` : `/cases/${n.case_id}`}>Open</Link>
            </span>
          </li>
        ))}
      </ul>
      {items.length > limit && <button className="mt-2 text-sm font-semibold text-accent underline" onClick={() => setAll(!all)}>{all ? "Show fewer" : `Show all ${items.length}`}</button>}
    </section>
  );
}
